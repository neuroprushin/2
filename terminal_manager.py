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
import asyncio

# Import platform-specific modules
if platform.system() != 'Windows':
    import termios
    import fcntl
    import pty
else:
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
        self.output_queue = queue.Queue()

    def start(self, cols, rows):
        if self.is_windows:
            self._start_windows_terminal()
        else:
            self._start_unix_terminal(cols, rows)

    def _start_windows_terminal(self):
        try:
            # Use powershell.exe for better terminal experience
            self.process = subprocess.Popen(
                ['powershell.exe'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            )

            # Start reading threads
            self.running = True
            
            # Thread for stdout
            self.stdout_thread = Thread(target=self._read_windows_pipe, args=(self.process.stdout,))
            self.stdout_thread.daemon = True
            self.stdout_thread.start()
            
            # Thread for stderr
            self.stderr_thread = Thread(target=self._read_windows_pipe, args=(self.process.stderr,))
            self.stderr_thread.daemon = True
            self.stderr_thread.start()
            
            # Thread for processing output
            self.output_thread = Thread(target=self._process_output)
            self.output_thread.daemon = True
            self.output_thread.start()

        except Exception as e:
            print(f"Failed to start Windows terminal: {e}")
            self.cleanup()

    def _read_windows_pipe(self, pipe):
        while self.running and self.process and self.process.poll() is None:
            try:
                # Read one character at a time to prevent blocking
                char = pipe.read(1)
                if char:
                    self.output_queue.put(char)
                else:
                    time.sleep(0.001)  # Tiny sleep to prevent CPU hogging
            except Exception as e:
                print(f"Error reading from pipe: {e}")
                break

    def _process_output(self):
        buffer = io.BytesIO()
        last_emit_time = 0
        
        while self.running:
            try:
                # Get data from queue with timeout
                try:
                    data = self.output_queue.get(timeout=0.1)
                    buffer.write(data)
                except queue.Empty:
                    # If no new data and buffer has content, process it
                    if buffer.tell() > 0 and time.time() - last_emit_time > 0.05:
                        self._emit_buffer(buffer)
                        last_emit_time = time.time()
                    continue

                # Process buffer if it's getting large or enough time has passed
                if buffer.tell() > 1024 or time.time() - last_emit_time > 0.05:
                    self._emit_buffer(buffer)
                    last_emit_time = time.time()

            except Exception as e:
                print(f"Error processing output: {e}")
                break

    def _emit_buffer(self, buffer):
        if buffer.tell() > 0:
            buffer.seek(0)
            try:
                data = buffer.getvalue()
                decoded = data.decode('utf-8', errors='replace')
                if decoded:
                    self.socket.emit('terminal_output', decoded)
            except Exception as e:
                print(f"Error decoding output: {e}")
            buffer.seek(0)
            buffer.truncate()

    def write(self, data):
        if self.is_windows:
            if self.process and self.process.poll() is None:
                try:
                    # Ensure proper line endings for Windows
                    data = data.replace('\n', '\r\n')
                    self.process.stdin.write(data.encode('utf-8'))
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