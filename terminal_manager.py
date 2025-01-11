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

# Import platform-specific modules
if platform.system() != 'Windows':
    import termios
    import fcntl
    import pty
else:
    from winpty import PtyProcess
    import msvcrt

class TerminalManager:
    def __init__(self, socket):
        self.socket = socket
        self.fd = None
        self.pid = None
        self.process = None
        self.thread = None
        self.running = False
        self.is_windows = platform.system() == 'Windows'
        self.winpty = None
        self.output_queue = queue.Queue()

    def start(self, cols, rows):
        if self.is_windows:
            self._start_windows_terminal(cols, rows)
        else:
            self._start_unix_terminal(cols, rows)

    def _start_windows_terminal(self, cols, rows):
        try:
            # Create a winpty terminal with specified dimensions
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            env['COLORTERM'] = 'truecolor'
            
            self.winpty = PtyProcess.spawn(
                'powershell.exe',
                dimensions=(rows, cols),
                env=env,
                cwd=os.getcwd()
            )

            # Start reading thread
            self.running = True
            self.thread = Thread(target=self._read_windows_output)
            self.thread.daemon = True
            self.thread.start()

        except Exception as e:
            print(f"Failed to start Windows terminal: {e}")
            self.cleanup()

    def _read_windows_output(self):
        buffer = []
        while self.running and self.winpty and self.winpty.isalive():
            try:
                # Read output with a timeout
                char = self.winpty.read(1)
                if char:
                    buffer.append(char)
                    # If we have a newline or buffer is getting large, emit it
                    if char == '\n' or len(buffer) >= 1024:
                        output = ''.join(buffer)
                        if output:
                            self.socket.emit('terminal_output', output)
                        buffer = []
                else:
                    # If there's anything in the buffer, emit it
                    if buffer:
                        output = ''.join(buffer)
                        if output:
                            self.socket.emit('terminal_output', output)
                        buffer = []
                    time.sleep(0.01)  # Small sleep to prevent CPU hogging
            except EOFError:
                break
            except Exception as e:
                print(f"Error reading from Windows terminal: {e}")
                break

        # Emit any remaining buffer content
        if buffer:
            output = ''.join(buffer)
            if output:
                self.socket.emit('terminal_output', output)
        self.cleanup()

    def write(self, data):
        if self.is_windows:
            if self.winpty and self.winpty.isalive():
                try:
                    # Ensure proper line endings for Windows
                    data = data.replace('\n', '\r\n').replace('\r\r\n', '\r\n')
                    self.winpty.write(data)
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
            if self.winpty and self.winpty.isalive():
                try:
                    self.winpty.setwinsize(rows, cols)
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
            if self.winpty:
                try:
                    self.winpty.terminate(force=True)
                except:
                    pass
                self.winpty = None
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