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
            
            # Start PowerShell in the PTY
            self.pty.spawn('powershell.exe -NoLogo')
            
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
                    try:
                        # Process the data
                        self._process_windows_output(data)
                    except Exception as e:
                        print(f"Error processing terminal output: {e}")
                time.sleep(0.001)  # Tiny sleep to prevent CPU hogging
            except Exception as e:
                print(f"Error reading from Windows terminal: {e}")
                time.sleep(0.1)  # Sleep on error to prevent rapid retries
                continue  # Continue instead of breaking to make the terminal more resilient
        
        # Flush any remaining output
        self._flush_output_buffer()
        self.cleanup()

    def _process_windows_output(self, data):
        """Process and buffer the terminal output"""
        current_time = time.time()
        
        # Add data to buffer
        self.output_buffer.append(data)
        
        # Emit if buffer is getting large or enough time has passed
        if len(''.join(self.output_buffer)) > 1024 or (current_time - self.last_emit_time) > 0.05:
            self._flush_output_buffer()

    def _flush_output_buffer(self):
        """Flush the output buffer to the client"""
        if self.output_buffer:
            try:
                # Join all buffered data
                output = ''.join(self.output_buffer)
                
                # Clean up common terminal control sequences
                output = self._clean_terminal_output(output)
                
                # Only emit if we have actual content
                if output.strip():
                    self.socket.emit('terminal_output', output)
                
                # Reset buffer and update time
                self.output_buffer = []
                self.last_emit_time = time.time()
            except Exception as e:
                print(f"Error flushing output buffer: {e}")
                self.output_buffer = []  # Clear buffer on error

    def _clean_terminal_output(self, output):
        """Clean up terminal output by handling control sequences"""
        # Remove common terminal control sequences that might make output messy
        output = output.replace('\r\n', '\n')  # Normalize line endings
        output = output.replace('\r', '\n')    # Convert lone \r to \n
        
        # Remove common terminal control sequences
        control_sequences = [
            '\x1b[?25l',  # Hide cursor
            '\x1b[?25h',  # Show cursor
            '\x1b[H',     # Home position
            '\x1b[2J',    # Clear screen
            '\x1b[K',     # Clear line
        ]
        
        for seq in control_sequences:
            output = output.replace(seq, '')
        
        return output

    def write(self, data):
        if self.is_windows:
            if self.pty:
                try:
                    # Normalize line endings for Windows
                    data = data.replace('\n', '\r\n')
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
                    self.pty.resize(rows, cols)
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