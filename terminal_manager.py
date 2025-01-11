import os
import select
import struct
import signal
import platform
import subprocess
import threading
import queue
from threading import Thread, Event
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
        self.running = False
        self.is_windows = platform.system() == 'Windows'
        self.winpty = None
        self.read_thread = None
        self.process_thread = None
        self.output_queue = queue.Queue()
        self.output_ready = Event()

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
            
            # Thread for reading from the terminal
            self.read_thread = Thread(target=self._read_windows_output)
            self.read_thread.daemon = True
            self.read_thread.start()
            
            # Thread for processing and emitting output
            self.process_thread = Thread(target=self._process_output)
            self.process_thread.daemon = True
            self.process_thread.start()

        except Exception as e:
            print(f"Failed to start Windows terminal: {e}")
            self.cleanup()

    def _read_windows_output(self):
        """Thread that reads from the terminal and puts data into the queue"""
        while self.running and self.winpty and self.winpty.isalive():
            try:
                # Read a chunk of data
                data = self.winpty.read()
                if data:
                    self.output_queue.put(data)
                    self.output_ready.set()
                else:
                    time.sleep(0.01)
            except EOFError:
                break
            except Exception as e:
                print(f"Error reading from Windows terminal: {e}")
                break
        self.running = False
        self.output_ready.set()  # Wake up processing thread

    def _process_output(self):
        """Thread that processes and emits the output"""
        while self.running or not self.output_queue.empty():
            try:
                # Wait for data with timeout
                self.output_ready.wait(timeout=0.1)
                self.output_ready.clear()
                
                # Process all available data
                while not self.output_queue.empty():
                    data = self.output_queue.get_nowait()
                    if data:
                        self.socket.emit('terminal_output', data)
                    self.output_queue.task_done()
                    
            except Exception as e:
                print(f"Error processing terminal output: {e}")
                
            if not self.running and self.output_queue.empty():
                break
                
        self.cleanup()

    def write(self, data):
        if self.is_windows:
            if self.winpty and self.winpty.isalive():
                try:
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
        self.output_ready.set()  # Wake up processing thread
        
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