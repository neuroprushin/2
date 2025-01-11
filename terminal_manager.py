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
                env=env
            )

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
        read_timeout = 0.1  # 100ms timeout
        
        while self.running and self.winpty and self.winpty.isalive():
            try:
                # Try to read with timeout
                data = None
                try:
                    data = self.winpty.read(timeout=read_timeout)
                except TimeoutError:
                    continue
                
                if data:
                    try:
                        self.socket.emit('terminal_output', data)
                    except Exception as e:
                        print(f"Error emitting terminal output: {e}")
                time.sleep(0.01)  # Small sleep to prevent CPU hogging
                
            except EOFError:
                break
            except Exception as e:
                print(f"Error reading from Windows terminal: {e}")
                time.sleep(0.1)  # Sleep on error to prevent rapid retries
        
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