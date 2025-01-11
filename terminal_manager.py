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

class TerminalManager:
    def __init__(self, socket):
        self.socket = socket
        self.fd = None
        self.pid = None
        self.process = None
        self.thread = None
        self.running = False
        self.is_windows = platform.system() == 'Windows'

    def start(self, cols, rows):
        if self.is_windows:
            self._start_windows_terminal()
        else:
            self._start_unix_terminal(cols, rows)

    def _start_windows_terminal(self):
        try:
            # Use powershell.exe for better terminal experience
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.process = subprocess.Popen(
                ['powershell.exe'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                bufsize=0
            )

            # Make stdout and stderr non-blocking
            for pipe in [self.process.stdout, self.process.stderr]:
                if pipe:
                    fd = pipe.fileno()
                    flags = subprocess.msvcrt.get_osfhandle(fd)
                    subprocess.msvcrt.setmode(fd, os.O_BINARY)

            # Start reading thread
            self.running = True
            self.thread = Thread(target=self._read_windows_output)
            self.thread.daemon = True
            self.thread.start()

        except Exception as e:
            print(f"Failed to start Windows terminal: {e}")
            self.cleanup()

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

    def _read_windows_output(self):
        stdout_buffer = io.BytesIO()
        stderr_buffer = io.BytesIO()
        
        try:
            while self.running and self.process and self.process.poll() is None:
                # Read from stdout without blocking
                try:
                    stdout_data = self.process.stdout.read1(1024) if hasattr(self.process.stdout, 'read1') else self.process.stdout.read(1024)
                    if stdout_data:
                        stdout_buffer.write(stdout_data)
                except (IOError, OSError):
                    pass

                # Read from stderr without blocking
                try:
                    stderr_data = self.process.stderr.read1(1024) if hasattr(self.process.stderr, 'read1') else self.process.stderr.read(1024)
                    if stderr_data:
                        stderr_buffer.write(stderr_data)
                except (IOError, OSError):
                    pass

                # Process buffers
                if stdout_buffer.tell() > 0:
                    stdout_buffer.seek(0)
                    try:
                        data = stdout_buffer.getvalue()
                        decoded = data.decode('cp437', errors='replace')
                        if decoded:
                            self.socket.emit('terminal_output', decoded)
                    except Exception as e:
                        print(f"Error decoding stdout: {e}")
                    stdout_buffer = io.BytesIO()

                if stderr_buffer.tell() > 0:
                    stderr_buffer.seek(0)
                    try:
                        data = stderr_buffer.getvalue()
                        decoded = data.decode('utf-8', errors='replace')
                        if decoded:
                            self.socket.emit('terminal_output', decoded)
                    except Exception as e:
                        print(f"Error decoding stderr: {e}")
                    stderr_buffer = io.BytesIO()

                time.sleep(0.01)  # Prevent CPU hogging

        except Exception as e:
            print(f"Error reading from Windows terminal: {e}")
        finally:
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

    def write(self, data):
        if self.is_windows:
            if self.process and self.process.poll() is None:
                try:
                    # Ensure proper line endings for Windows
                    data = data.replace('\n', '\r\n')
                    self.process.stdin.write(data.encode('cp437'))
                    self.process.stdin.flush()
                except Exception as e:
                    print(f"Failed to write to Windows terminal: {e}")
        else:
            if self.fd is not None:
                try:
                    os.write(self.fd, data.encode())
                except Exception as e:
                    print(f"Failed to write to terminal: {e}")

    def resize_terminal(self, cols, rows):
        if not self.is_windows and self.fd is not None:
            try:
                size = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, size)
            except Exception as e:
                print(f"Failed to resize terminal: {e}")

    def cleanup(self):
        self.running = False
        
        if self.is_windows:
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except:
                    try:
                        self.process.kill()
                    except:
                        pass
                self.process = None
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