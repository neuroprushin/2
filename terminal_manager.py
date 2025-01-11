import os
import select
import struct
import signal
import platform
import subprocess
import threading
import queue
from threading import Thread
import time
import io
import re

# Import platform-specific modules
if platform.system() != 'Windows':
    import termios
    import fcntl
    import pty
else:
    from winpty import PTY

class TerminalManager:
    def __init__(self, socket):
        self.socket = socket
        self.fd = None
        self.pid = None
        self.process = None
        self.running = False
        self.is_windows = platform.system() == 'Windows'
        self.pty = None
        self.read_thread = None
        self.output_buffer = []
        self.last_emit_time = 0

    def start(self, cols, rows):
        if self.is_windows:
            self._start_windows_terminal(cols, rows)
        else:
            self._start_unix_terminal(cols, rows)

    def _start_windows_terminal(self, cols, rows):
        try:
            # Create PTY with dimensions
            self.pty = PTY(rows, cols)
            
            # Start PowerShell with proper window size
            startup_command = (
                'powershell.exe -NoLogo '
                '-Command "'
                '$Host.UI.RawUI.WindowSize = New-Object System.Management.Automation.Host.Size($Host.UI.RawUI.WindowSize.Width, $Host.UI.RawUI.WindowSize.Height); '
                '$Host.UI.RawUI.BufferSize = New-Object System.Management.Automation.Host.Size($Host.UI.RawUI.BufferSize.Width, $Host.UI.RawUI.BufferSize.Height)"'
            )
            self.pty.spawn(startup_command)
            
            # Start reading thread
            self.running = True
            self.read_thread = Thread(target=self._read_windows_output)
            self.read_thread.daemon = True
            self.read_thread.start()

        except Exception as e:
            print(f"Failed to start Windows terminal: {e}")
            self.cleanup()

    def _read_windows_output(self):
        """Thread that reads from the terminal and emits output"""
        while self.running and self.pty:
            try:
                # Read available data
                data = self.pty.read()
                if data:
                    # Clean and emit immediately
                    self.socket.emit('terminal_output', data)
                time.sleep(0.001)  # Tiny sleep to prevent CPU hogging
            except Exception as e:
                if 'EOF' not in str(e):  # Don't print EOF errors
                    print(f"Error reading from Windows terminal: {e}")
                time.sleep(0.1)  # Sleep on error to prevent rapid retries
                if 'EOF' in str(e):
                    break
                continue
        
        self.cleanup()

    def _clean_terminal_output(self, output):
        """Clean up terminal output by handling control sequences"""
        if self.is_windows:
            # Remove the chcp command output
            if 'Active code page:' in output:
                output = output.split('\n', 1)[1] if '\n' in output else ''
            
            # Normalize line endings
            output = output.replace('\r\n', '\n')
            output = output.replace('\r', '\n')
            
            # Remove null bytes
            output = output.replace('\x00', '')
            
            # Remove duplicate empty lines
            while '\n\n\n' in output:
                output = output.replace('\n\n\n', '\n\n')
            
            return output.strip()
        return output

    def _strip_ansi(self, text):
        """Remove ANSI escape sequences"""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def write(self, data):
        if self.is_windows:
            if self.pty:
                try:
                    # Ensure input is processed as a single operation
                    with threading.Lock():
                        self.pty.write(data)
                except Exception as e:
                    print(f"Failed to write to Windows terminal: {e}")
        else:
            if self.fd is not None:
                try:
                    os.write(self.fd, data.encode())
                except Exception as e:
                    print(f"Failed to write to terminal: {e}")

    def resize_terminal(self, cols, rows):
        if self.is_windows:
            if self.pty:
                try:
                    # For Windows, we need to recreate the PTY with new dimensions
                    old_pty = self.pty
                    self.pty = PTY(rows, cols)
                    
                    # Transfer the process to the new PTY if possible
                    if hasattr(old_pty, 'conin_pipe'):
                        self.pty.conin_pipe = old_pty.conin_pipe
                        self.pty.conout_pipe = old_pty.conout_pipe
                    
                    # Update PowerShell's window size
                    resize_command = (
                        '$Host.UI.RawUI.WindowSize = '
                        f'New-Object System.Management.Automation.Host.Size({cols}, {rows}); '
                        '$Host.UI.RawUI.BufferSize = '
                        f'New-Object System.Management.Automation.Host.Size({cols}, {rows})'
                    )
                    self.pty.write(resize_command + '\r\n')
                    
                except Exception as e:
                    print(f"Failed to resize Windows terminal: {e}")
        else:
            if self.fd is not None:
                try:
                    size = struct.pack('HHHH', rows, cols, 0, 0)
                    fcntl.ioctl(self.fd, termios.TIOCSWINSZ, size)
                except Exception as e:
                    print(f"Failed to resize terminal: {e}")

    def cleanup(self):
        self.running = False
        
        if self.is_windows:
            if self.pty:
                try:
                    self.pty.close()
                except:
                    pass
                self.pty = None
        else:
            if self.pid:
                try:
                    os.kill(self.pid, signal.SIGTERM)
                except:
                    pass
            
            if self.fd is not None:
                try:
                    os.close(self.fd)
                except:
                    pass
            
            self.fd = None
            self.pid = None

    def _start_unix_terminal(self, cols, rows):
        # Choose shell based on environment
        shell = os.environ.get('SHELL', '/bin/bash')
        
        # Create PTY and fork process
        self.pid, self.fd = pty.fork()
        
        if self.pid == 0:  # Child process
            # Set up environment
            os.environ['TERM'] = 'xterm-256color'
            os.environ['COLORTERM'] = 'truecolor'
            
            try:
                os.execvp(shell, [shell])
            except Exception as e:
                print(f"Failed to execute shell: {e}")
                os._exit(1)
        else:  # Parent process
            try:
                # Set terminal size
                self.resize_terminal(cols, rows)
                
                # Start reading thread
                self.running = True
                self.thread = Thread(target=self._read_unix_output)
                self.thread.daemon = True
                self.thread.start()
            except Exception as e:
                print(f"Failed to initialize terminal: {e}")
                self.cleanup()

    def _read_unix_output(self):
        max_read_bytes = 1024 * 20
        
        while self.running and self.fd is not None:
            try:
                r, _, _ = select.select([self.fd], [], [], 0.1)
                if r:
                    output = os.read(self.fd, max_read_bytes)
                    if output:
                        # Emit the output to the client
                        self.socket.emit('terminal_output', output.decode(errors='replace'))
                    else:
                        # EOF reached
                        break
            except Exception as e:
                print(f"Error reading from Unix terminal: {e}")
                break
        
        self.cleanup()

    # ... rest of the Unix terminal methods stay the same ... 