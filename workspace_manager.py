import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Union
import json
import mmap
from pathlib import Path
import string

class WorkspaceManager:
    # File size thresholds and constants
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    PREVIEW_SIZE = 10 * 1024  # 10KB for previews
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks for large file reading
    LAZY_LOAD_THRESHOLD = 1000  # Number of files before switching to lazy loading
    MAX_TOKENS_PER_REQUEST = 30000  # Maximum tokens per request
    TOKEN_BUFFER = 1000  # Buffer to account for system messages and formatting
    
    # File type configurations
    BINARY_EXTENSIONS = {
        # Compiled files
        '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe', '.bin', '.o', '.obj', '.lib', '.a', '.dylib',
        # Image files
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.tiff', '.webp', '.heic',
        # Audio/Video files
        '.mp3', '.wav', '.ogg', '.mp4', '.avi', '.mov', '.flv', '.mkv', '.m4a', '.m4v',
        # Archive files
        '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.iso',
        # Document files
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        # Database files
        '.db', '.sqlite', '.sqlite3', '.mdb',
        # Font files
        '.ttf', '.otf', '.woff', '.woff2', '.eot',
        # Other binary files
        '.class', '.jar', '.war', '.ear', '.pkl', '.h5', '.dat'
    }
    SKIP_EXTENSIONS = BINARY_EXTENSIONS
    SKIP_FOLDERS = {
        '.git',
        'node_modules',
        '__pycache__',
        'venv',
        '.venv',
        'env',
        '.env',
        'dist',
        'build',
        'target',  # Common for Java/Rust
        'vendor',  # Common for PHP/Go
        '.idea',   # JetBrains IDEs
        '.vscode', # VS Code
        'coverage',
        '.next',   # Next.js
        '.nuxt',   # Nuxt.js
        '.output', # Various build outputs
        'tmp',
        'temp'
    }  # Folders to always ignore
    LARGE_FILE_THRESHOLD = 1 * 1024 * 1024  # 1MB
    
    def __init__(self, workspace_root: str):
        """Initialize workspace manager with root directory"""
        self.workspace_root = workspace_root
        os.makedirs(workspace_root, exist_ok=True)
        
        # Enhanced caching system
        self._content_cache: Dict[str, Tuple[str, float, int]] = {}  # path -> (content, mtime, size)
        self._structure_cache: Dict[str, Tuple[List[dict], float]] = {}  # workspace -> (structure, mtime)
        self._chunk_cache: Dict[str, Dict[int, str]] = {}  # path -> {chunk_index: content}
        self._gitignore_patterns: List[str] = []
        self._load_gitignore()
        
    def _load_gitignore(self):
        """Load .gitignore patterns if the file exists"""
        gitignore_path = os.path.join(self.workspace_root, '.gitignore')
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, 'r') as f:
                    patterns = []
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Convert glob patterns to regex patterns
                            pattern = line.replace('.', r'\.').replace('*', '.*').replace('?', '.')
                            if not line.startswith('/'):
                                pattern = f'.*{pattern}'
                            if not line.endswith('/'):
                                pattern = f'{pattern}($|/.*)'
                            patterns.append(pattern)
                    self._gitignore_patterns = patterns
            except Exception as e:
                print(f"Warning: Could not read .gitignore file: {e}")

    def _should_ignore(self, path: str) -> bool:
        """Check if a path should be ignored based on gitignore patterns"""
        if not self._gitignore_patterns:
            return False
        
        import re
        normalized_path = path.replace('\\', '/')
        return any(re.match(pattern, normalized_path) for pattern in self._gitignore_patterns)
    
    def _is_cache_valid(self, path: str, cache_entry: Tuple[Union[str, List[dict]], float]) -> bool:
        """Check if cached content is still valid"""
        try:
            current_mtime = os.path.getmtime(path)
            return current_mtime == cache_entry[1]
        except OSError:
            return False
    
    def _get_file_content(self, file_path: str, start_chunk: int = 0, num_chunks: int = 1) -> str:
        """Get file content with chunked reading support"""
        try:
            file_size = os.path.getsize(file_path)
            
            # For small files, read entire content
            if file_size < self.LARGE_FILE_THRESHOLD:
                if file_path in self._content_cache:
                    content, mtime, size = self._content_cache[file_path]
                    if os.path.getmtime(file_path) == mtime and size == file_size:
                        return content
                
                try:
                    # Try UTF-8 first
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        self._content_cache[file_path] = (content, os.path.getmtime(file_path), file_size)
                        return content
                except UnicodeDecodeError:
                    # Try latin-1 if UTF-8 fails
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                        self._content_cache[file_path] = (content, os.path.getmtime(file_path), file_size)
                        return content
            
            # For large files, use chunked reading
            if file_path not in self._chunk_cache:
                self._chunk_cache[file_path] = {}
            
            chunks = []
            for i in range(start_chunk, start_chunk + num_chunks):
                if i in self._chunk_cache[file_path]:
                    chunks.append(self._chunk_cache[file_path][i])
                    continue
                
                offset = i * self.CHUNK_SIZE
                if offset >= file_size:
                    break
                
                try:
                    # Try UTF-8 first
                    with open(file_path, 'r', encoding='utf-8') as f:
                        f.seek(offset)
                        chunk = f.read(self.CHUNK_SIZE)
                        self._chunk_cache[file_path][i] = chunk
                        chunks.append(chunk)
                except UnicodeDecodeError:
                    # Try latin-1 if UTF-8 fails
                    with open(file_path, 'r', encoding='latin-1') as f:
                        f.seek(offset)
                        chunk = f.read(self.CHUNK_SIZE)
                        self._chunk_cache[file_path][i] = chunk
                        chunks.append(chunk)
            
            return ''.join(chunks)
            
        except (IOError, UnicodeDecodeError) as e:
            print(f"Error reading file {file_path}: {str(e)}")  # Debug log
            return ''
    
    def get_directory_structure(self, dir_path: str, depth: int = 1) -> List[dict]:
        """Get directory structure with lazy loading support"""
        try:
            # Use the provided path directly if it's absolute, otherwise join with workspace root
            abs_path = dir_path if os.path.isabs(dir_path) else os.path.join(self.workspace_root, dir_path)
            base_dir = os.path.basename(dir_path) if os.path.isabs(dir_path) else dir_path
            result = []
            
            for entry in os.scandir(abs_path):
                # Skip hidden files, .git directory, and other ignored directories
                if entry.name.startswith('.') or (entry.is_dir() and entry.name in self.SKIP_FOLDERS):
                    continue
                    
                # Get path relative to current directory instead of workspace root
                rel_path = os.path.relpath(entry.path, abs_path)
                
                # Skip if path matches gitignore patterns
                if self._should_ignore(rel_path):
                    continue
                
                if entry.is_file() and not any(rel_path.endswith(ext) for ext in self.SKIP_EXTENSIONS):
                    result.append({
                        'type': 'file',
                        'path': rel_path.replace('\\', '/'),
                        'size': entry.stat().st_size
                    })
                elif entry.is_dir() and depth > 0:
                    children = self.get_directory_structure(entry.path, depth - 1) if depth > 1 else []
                    result.append({
                        'type': 'directory',
                        'path': rel_path.replace('\\', '/'),
                        'has_children': bool(children) or any(True for _ in os.scandir(entry.path)),
                        'children': children
                    })
            
            return sorted(result, key=lambda x: (x['type'] != 'directory', x['path'].lower()))
            
        except OSError:
            return []
    
    def get_workspace_structure(self, workspace_dir: str) -> List[dict]:
        """Get workspace structure with lazy loading for large directories"""
        try:
            # Check if we have a valid cached structure
            if workspace_dir in self._structure_cache:
                structure, mtime = self._structure_cache[workspace_dir]
                if os.path.getmtime(workspace_dir) == mtime:
                    return structure
            
            # Count total files to determine if we should use lazy loading
            total_files = 0
            print(f"\nCounting files in {workspace_dir}:")
            for root, dirs, files in os.walk(workspace_dir):
                # Skip .git and other ignored directories
                original_dirs = set(dirs)
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in self.SKIP_FOLDERS]
                if len(original_dirs) != len(dirs):
                    print(f"Skipped directories in {root}: {original_dirs - set(dirs)}")
                
                # Filter files based on gitignore and skip patterns
                for file in files:
                    if (not file.startswith('.') and 
                        not file.endswith(tuple(self.SKIP_EXTENSIONS))):
                        rel_path = os.path.relpath(os.path.join(root, file), workspace_dir)
                        if not self._should_ignore(rel_path):
                            total_files += 1
                            print(f"Counting file: {rel_path}")
                        else:
                            print(f"Ignoring file (gitignore): {rel_path}")
                    else:
                        print(f"Ignoring file (hidden/extension): {file}")
            
            print(f"\nTotal files counted: {total_files}")
            
            if total_files > self.LAZY_LOAD_THRESHOLD:
                # Use lazy loading - only get top-level structure
                structure = self.get_directory_structure(workspace_dir, depth=1)
            else:
                # Get full structure for smaller workspaces
                structure = self.get_directory_structure(workspace_dir, depth=float('inf'))
            
            self._structure_cache[workspace_dir] = (structure, os.path.getmtime(workspace_dir))
            return structure
            
        except OSError:
            return []
    
    def expand_directory(self, dir_path: str, workspace_dir: str, page_size: int = 100, page: int = 1) -> dict:
        """Expand a directory node for lazy loading with pagination support
        
        Args:
            dir_path: Directory path to expand
            workspace_dir: The workspace directory containing the files
            page_size: Number of items per page
            page: Page number (1-based)
            
        Returns:
            Dictionary containing:
            - items: List of files and directories in the current page
            - total_items: Total number of items
            - has_more: Whether there are more items
        """
        try:
            # Ensure we have absolute paths
            if os.path.isabs(dir_path):
                abs_path = dir_path
                # Verify the path is within workspace directory
                if not os.path.abspath(abs_path).startswith(os.path.abspath(workspace_dir)):
                    raise ValueError("Path is outside workspace directory")
            else:
                abs_path = os.path.join(workspace_dir, dir_path)
            
            print(f"Expanding directory: {abs_path}")  # Debug log
            
            if not os.path.exists(abs_path):
                print(f"Directory not found: {abs_path}")  # Debug log
                raise ValueError(f"Directory not found: {dir_path}")
            
            if not os.path.isdir(abs_path):
                print(f"Not a directory: {abs_path}")  # Debug log
                raise ValueError(f"Not a directory: {dir_path}")
            
            # Get all entries first
            entries = []
            start_idx = (page - 1) * page_size
            
            try:
                with os.scandir(abs_path) as it:
                    for entry in it:
                        try:
                            # Skip hidden files and ignored directories
                            if entry.name.startswith('.') or (entry.is_dir() and entry.name in self.SKIP_FOLDERS):
                                print(f"Skipping {entry.name} (hidden/ignored)")  # Debug log
                                continue
                            
                            # Get path relative to current directory
                            entry_rel_path = os.path.relpath(entry.path, abs_path)
                            
                            # Skip if path matches gitignore patterns
                            if self._should_ignore(entry_rel_path):
                                print(f"Skipping {entry_rel_path} (gitignore)")  # Debug log
                                continue
                            
                            if entry.is_file() and not any(entry_rel_path.endswith(ext) for ext in self.SKIP_EXTENSIONS):
                                print(f"Adding file: {entry_rel_path}")  # Debug log
                                entries.append({
                                    'type': 'file',
                                    'path': entry_rel_path.replace('\\', '/'),
                                    'size': entry.stat().st_size
                                })
                            elif entry.is_dir():
                                # For directories, check if they have children without loading them all
                                has_children = False
                                try:
                                    with os.scandir(entry.path) as dir_it:
                                        for child in dir_it:
                                            if not child.name.startswith('.') and not (child.is_dir() and child.name in self.SKIP_FOLDERS):
                                                has_children = True
                                                break
                                except OSError as e:
                                    print(f"Error checking directory contents: {e}")  # Debug log
                                    pass
                                
                                print(f"Adding directory: {entry_rel_path} (has_children={has_children})")  # Debug log
                                entries.append({
                                    'type': 'directory',
                                    'path': entry_rel_path.replace('\\', '/'),
                                    'has_children': has_children
                                })
                        except OSError as e:
                            print(f"Error processing entry {entry.name}: {e}")  # Debug log
                            continue
            except OSError as e:
                print(f"Error scanning directory {abs_path}: {e}")  # Debug log
                raise
            
            # Sort entries (directories first, then alphabetically)
            entries.sort(key=lambda x: (x['type'] != 'directory', x['path'].lower()))
            
            # Get total count and slice for current page
            total_items = len(entries)
            page_entries = entries[start_idx:start_idx + page_size]
            
            print(f"Directory expansion results: {len(page_entries)} items (total: {total_items})")  # Debug log
            
            return {
                'items': page_entries,
                'total_items': total_items,
                'has_more': (start_idx + page_size) < total_items
            }
            
        except Exception as e:
            print(f"Error in expand_directory: {str(e)}")  # Debug log
            raise
    
    def clear_cache(self, file_path: Optional[str] = None):
        """Clear cache entries"""
        if file_path:
            self._content_cache.pop(file_path, None)
            self._chunk_cache.pop(file_path, None)
        else:
            self._content_cache.clear()
            self._structure_cache.clear()
            self._chunk_cache.clear() 
    
    def get_workspace_context(self, workspace_dir: str) -> str:
        """Get a description of the workspace context"""
        structure = self.get_workspace_structure(workspace_dir)
        files_content = self.get_workspace_files(workspace_dir)
        
        context = "Workspace Structure:\n"
        for item in structure:
            prefix = "📁 " if item['type'] == 'directory' else " "
            context += f"{prefix}{item['path']}\n"
        
        context += "\nFile Relationships and Dependencies:\n"
        # Analyze imports and dependencies
        dependencies = self._analyze_dependencies(files_content)
        for file, deps in dependencies.items():
            if deps:
                context += f"{file} depends on: {', '.join(deps)}\n"
        
        return context
    
    def get_workspace_files(self, workspace_dir: str, query: str = None) -> Dict[str, str]:
        """Get contents of relevant files in the workspace.
        
        Args:
            workspace_dir: Path to workspace directory
            query: Optional query to filter relevant files
            
        Returns:
            Dictionary mapping file paths to their contents
        """
        files_content = {}
        total_size = 0
        
        for root, _, files in os.walk(workspace_dir):
            for file in files:
                # Skip hidden files, specified extensions, and binary files
                if (file.startswith('.') or 
                    file.endswith(tuple(self.SKIP_EXTENSIONS))):
                    continue
                    
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, workspace_dir)
                
                # Skip binary files
                if self.is_binary_file(file_path):
                    print(f"Skipping binary file: {rel_path}")
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Skip empty files
                        if not content.strip():
                            continue
                            
                        file_size = len(content.encode('utf-8'))
                        total_size += file_size
                        
                        files_content[rel_path] = content
                        print(f"Added file: {rel_path} ({file_size} bytes)")
                except Exception as e:
                    print(f"Error reading file {file_path}: {e}")
                    continue
        
        print(f"\nTotal files: {len(files_content)}")
        print(f"Total size: {total_size} bytes")
        
        return files_content
    
    def _analyze_dependencies(self, files_content: Dict[str, str]) -> Dict[str, Set[str]]:
        """Analyze file dependencies based on imports and references"""
        dependencies = {}
        import_patterns = {
            '.py': ['import ', 'from '],
            '.js': ['import ', 'require('],
            '.html': ['<script src=', '<link href='],
        }
        
        for file_path, content in files_content.items():
            ext = os.path.splitext(file_path)[1]
            deps = set()
            
            if ext in import_patterns:
                lines = content.split('\n')
                for line in lines:
                    for pattern in import_patterns[ext]:
                        if pattern in line:
                            # Extract dependency name (simplified)
                            dep = line.split(pattern)[-1].split()[0].strip('"\';')
                            deps.add(dep)
            
            dependencies[file_path] = deps
        
        return dependencies 
    
    def process_operations(self, operations: List[dict], workspace_dir: str) -> List[dict]:
        """Process and validate operations, adding diffs for changes
        
        Args:
            operations: List of operations to process
            workspace_dir: The workspace directory path
        """
        processed = []
        for operation in operations:
            try:
                # First validate the operation content before cleaning paths
                if operation['type'] == 'edit_file':
                    changes = operation.get('changes', [])
                    for change in changes:
                        if 'old' in change and 'new' in change:
                            # Validate that both old and new fields are complete
                            if not change['old'].strip() or not change['new'].strip():
                                raise ValueError(f"Incomplete change detected in {operation.get('path', 'unknown file')}")
                elif operation['type'] == 'create_file':
                    # Validate content field is complete
                    if not operation.get('content', '').strip():
                        raise ValueError(f"Empty or incomplete content for {operation.get('path', 'unknown file')}")

                # After validation, clean the paths for processing
                if 'path' in operation:
                    operation['path'] = operation['path'].split('?')[0].split('#')[0]
                if 'new_path' in operation:
                    operation['new_path'] = operation['new_path'].split('?')[0].split('#')[0]
                
                if operation['type'] == 'edit_file':
                    # Get current content if file exists
                    file_path = os.path.join(workspace_dir, operation['path'])
                    current_content = ''
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                current_content = f.read()
                        except UnicodeDecodeError:
                            try:
                                with open(file_path, 'r', encoding='latin-1') as f:
                                    current_content = f.read()
                            except Exception:
                                pass

                    # Generate unified diff
                    from difflib import unified_diff
                    changes = operation.get('changes', [])
                    new_content = current_content
                    for change in changes:
                        if 'old' in change and 'new' in change:
                            new_content = new_content.replace(change['old'], change['new'])
                    
                    diff = unified_diff(
                        current_content.splitlines(),
                        new_content.splitlines(),
                        fromfile=f'a/{operation["path"]}',
                        tofile=f'b/{operation["path"]}',
                        lineterm=''
                    )
                    operation['diff'] = '\n'.join(line for line in diff if line)
                    
                    # Run linter on Python files
                    if operation['path'].endswith('.py'):
                        import tempfile
                        import subprocess
                        
                        # Create temporary file with new content
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
                            tmp.write(new_content)
                            tmp_path = tmp.name
                        
                        try:
                            # Run pylama
                            result = subprocess.run(['pylama', tmp_path], capture_output=True, text=True)
                            operation['lint_output'] = result.stdout
                            operation['lint_passed'] = result.returncode == 0
                        except Exception as e:
                            print(f"Linting error: {str(e)}")
                            operation['lint_output'] = str(e)
                            operation['lint_passed'] = False
                        finally:
                            os.unlink(tmp_path)
                    else:
                        # Non-Python files don't need linting
                        operation['lint_passed'] = True
                        operation['lint_output'] = ''
                    
                elif operation['type'] == 'create_file':
                    # For new files, show the entire content as added
                    diff = [
                        f'--- /dev/null\n',
                        f'+++ b/{operation["path"]}\n',
                        '@@ -0,0 +1,{} @@\n'.format(operation['content'].count('\n') + 1)
                    ]
                    diff.extend(f'+{line}\n' for line in operation['content'].splitlines())
                    operation['diff'] = ''.join(diff)
                    
                    # Run linter on new Python files
                    if operation['path'].endswith('.py'):
                        import tempfile
                        import subprocess
                        
                        # Create temporary file with content
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
                            tmp.write(operation['content'])
                            tmp_path = tmp.name
                        
                        try:
                            # Run pylama
                            result = subprocess.run(['pylama', tmp_path], capture_output=True, text=True)
                            operation['lint_output'] = result.stdout
                            operation['lint_passed'] = result.returncode == 0
                        except Exception as e:
                            print(f"Linting error: {str(e)}")
                            operation['lint_output'] = str(e)
                            operation['lint_passed'] = False
                        finally:
                            os.unlink(tmp_path)
                    else:
                        # Non-Python files don't need linting
                        operation['lint_passed'] = True
                        operation['lint_output'] = ''
                    
                elif operation['type'] == 'remove_file':
                    # For file removal, show the entire content as removed
                    file_path = os.path.join(workspace_dir, operation['path'])
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except UnicodeDecodeError:
                            with open(file_path, 'r', encoding='latin-1') as f:
                                content = f.read()
                                
                        diff = [
                            f'--- a/{operation["path"]}\n',
                            f'+++ /dev/null\n',
                            '@@ -1,{} +0,0 @@\n'.format(content.count('\n') + 1)
                        ]
                        diff.extend(f'-{line}\n' for line in content.splitlines())
                        operation['diff'] = ''.join(diff)
                    else:
                        operation['diff'] = ''
                    
                    # No linting needed for file removal
                    operation['lint_passed'] = True
                    operation['lint_output'] = ''
                
                processed.append(operation)
                
            except Exception as e:
                print(f"Error processing operation: {str(e)}")
                operation['error'] = str(e)
                operation['lint_passed'] = False
                operation['lint_output'] = str(e)
                processed.append(operation)
                
        return processed 
    
    def is_binary_file(self, file_path: str) -> bool:
        """Check if a file is binary based on extension or content analysis."""
        # First check extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext in self.BINARY_EXTENSIONS:
            return True
            
        # If extension check fails, try to read the file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                chunk = f.read(1024)  # Read first 1KB
                return any(char not in string.printable for char in chunk)
        except (UnicodeDecodeError, IOError):
            return True  # If we can't read it as text, it's probably binary
        
        return False 
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate the number of tokens in a text string.
        
        This is a more accurate estimation than the simple char/4 method:
        - Each word is roughly 1.3 tokens
        - Each punctuation is a token
        - Each newline is a token
        - Each number is roughly 1 token per 2-3 digits
        """
        # Split into words
        words = text.split()
        # Count base tokens (words)
        token_count = len(words) * 1.3
        # Add tokens for punctuation and special characters
        token_count += text.count('.') + text.count(',') + text.count('!') + text.count('?')
        token_count += text.count('(') + text.count(')') + text.count('[') + text.count(']')
        token_count += text.count('{') + text.count('}') + text.count(':') + text.count(';')
        # Add tokens for newlines
        token_count += text.count('\n')
        # Add tokens for numbers (roughly 1 token per 2-3 digits)
        import re
        numbers = re.findall(r'\d+', text)
        for num in numbers:
            token_count += len(num) / 2.5
        return int(token_count)

    def chunk_workspace_files(self, files_content: Dict[str, str], max_tokens: int = None, system_prompt: str = "") -> List[Dict[str, Dict[str, str]]]:
        """Split workspace files into chunks that respect the token limit.
        
        Args:
            files_content: Dictionary mapping file paths to their contents
            max_tokens: Maximum tokens per chunk (defaults to MAX_TOKENS_PER_REQUEST - TOKEN_BUFFER)
            system_prompt: The system prompt to account for in token calculation
            
        Returns:
            List of dictionaries, each containing a subset of files that fits within token limit
        """
        if max_tokens is None:
            max_tokens = self.MAX_TOKENS_PER_REQUEST - self.TOKEN_BUFFER
            
        chunks = []
        current_chunk = {}
        current_tokens = 0
        
        # First, calculate tokens for system prompt and other fixed content
        system_tokens = self.estimate_tokens(system_prompt) if system_prompt else 0
        file_header_tokens = 10  # Tokens for "File: " and "Content:" headers
        
        # Adjust max_tokens to account for fixed content
        available_tokens = max_tokens - system_tokens - self.TOKEN_BUFFER
        
        print(f"\n=== Chunking {len(files_content)} files ===")
        print(f"System prompt tokens: {system_tokens}")
        print(f"Available tokens per chunk: {available_tokens}")
        
        # Sort files by size to try to balance chunks better
        sorted_files = sorted(files_content.items(), key=lambda x: len(x[1]))
        
        for path, content in sorted_files:
            # Calculate tokens for this file's content plus its path
            file_tokens = self.estimate_tokens(content) + self.estimate_tokens(path) + file_header_tokens
            
            print(f"\nProcessing: {path}")
            print(f"File tokens: {file_tokens}")
            print(f"Current chunk tokens: {current_tokens}")
            
            if current_tokens + file_tokens > available_tokens:
                if current_chunk:  # Save current chunk if not empty
                    print(f"Chunk full, saving {len(current_chunk)} files ({current_tokens} tokens)")
                    chunks.append(current_chunk)
                    current_chunk = {}
                    current_tokens = 0
                
                # If a single file is too large, split it
                if file_tokens > available_tokens:
                    print(f"File too large ({file_tokens} tokens), splitting: {path}")
                    # Split content into smaller chunks that fit
                    content_chunks = []
                    remaining_content = content
                    while remaining_content:
                        # Calculate max content length that would fit in a chunk
                        max_content_tokens = available_tokens - self.estimate_tokens(path) - file_header_tokens
                        max_chars = int(max_content_tokens * 4)  # Rough estimate of chars per token
                        
                        if len(remaining_content) <= max_chars:
                            content_chunks.append(remaining_content)
                            remaining_content = ""
                        else:
                            # Try to split at a newline near the max length
                            split_point = remaining_content.rfind('\n', 0, max_chars)
                            if split_point == -1:
                                split_point = max_chars
                            
                            content_chunks.append(remaining_content[:split_point])
                            remaining_content = remaining_content[split_point:].lstrip()
                    
                    # Create a chunk for each part
                    for i, chunk_content in enumerate(content_chunks):
                        chunk_tokens = self.estimate_tokens(chunk_content) + self.estimate_tokens(path) + file_header_tokens
                        print(f"Creating chunk for part {i+1}/{len(content_chunks)} ({chunk_tokens} tokens)")
                        chunks.append({f"{path} (part {i+1}/{len(content_chunks)})": chunk_content})
                else:
                    current_chunk = {path: content}
                    current_tokens = file_tokens
            else:
                current_chunk[path] = content
                current_tokens += file_tokens
        
        if current_chunk:  # Add the last chunk if not empty
            print(f"\nSaving final chunk with {len(current_chunk)} files ({current_tokens} tokens)")
            chunks.append(current_chunk)
            
        print(f"\n=== Chunking complete ===")
        print(f"Created {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            chunk_size = sum(len(content) for content in chunk.values())
            chunk_tokens = sum(self.estimate_tokens(content) + self.estimate_tokens(path) + file_header_tokens 
                             for path, content in chunk.items())
            print(f"Chunk {i+1}: {len(chunk)} files, ~{chunk_tokens} tokens, {chunk_size} bytes")
            
        return chunks

    def get_workspace_files_chunked(self, workspace_dir: str, query: str = None, max_tokens: int = None, system_prompt: str = "") -> List[Dict[str, Dict[str, str]]]:
        """Get workspace files split into chunks that respect the token limit.
        
        Args:
            workspace_dir: Path to the workspace directory
            query: Optional query to filter relevant files
            max_tokens: Maximum tokens per chunk
            system_prompt: The system prompt to account for in token calculation
            
        Returns:
            List of chunked file contents, each chunk respecting token limit
        """
        # Get all relevant files first
        files_content = self.get_workspace_files(workspace_dir, query)
        
        # Split into chunks
        return self.chunk_workspace_files(files_content, max_tokens, system_prompt)

    async def process_chunks_parallel(self, chunks: List[Dict[str, Dict[str, str]]], prompt: str, model_id: str) -> List[Dict]:
        """Process file chunks in parallel.
        
        Args:
            chunks: List of file content chunks
            prompt: The user's prompt
            model_id: The model to use for processing
            
        Returns:
            List of suggestions from processing each chunk
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        from app import model_clients, AVAILABLE_MODELS, system_prompt, socketio
        import json
        import time
        
        async def process_chunk(chunk, chunk_index):
            # Process each chunk in a separate thread
            with ThreadPoolExecutor() as executor:
                try:
                    client = model_clients[model_id]
                    model_config = AVAILABLE_MODELS[model_id]
                    
                    print(f"\n=== Step 1: Preparing Request for Chunk {chunk_index + 1}/{len(chunks)} ===")
                    print(f"Model: {model_id}")
                    print(f"Prompt length: {len(prompt)} characters")
                    
                    # Extract and log information about files in chunk
                    files_info = []
                    for file_path, content in chunk.items():
                        lines = content.count('\n') + 1
                        size = len(content.encode('utf-8'))
                        files_info.append({
                            'path': file_path,
                            'lines': lines,
                            'size': size
                        })
                    
                    # Log and emit detailed status about chunk files
                    file_details = '\n'.join(f"- {f['path']} ({f['lines']} lines, {f['size']} bytes)" for f in files_info)
                    print(f"\nFiles in chunk {chunk_index + 1}:\n{file_details}")
                    socketio.emit('status', {
                        'message': f'Processing chunk {chunk_index + 1}/{len(chunks)} ({len(files_info)} files)...',
                        'step': 1,
                        'details': {
                            'chunk': chunk_index + 1,
                            'total_chunks': len(chunks),
                            'files': files_info,
                            'total_files': len(files_info),
                            'total_lines': sum(f['lines'] for f in files_info),
                            'total_size': sum(f['size'] for f in files_info)
                        }
                    })
                    
                    # Build context from chunk files
                    context = "Here are the relevant files in the workspace:\n\n"
                    for file_path, content in chunk.items():
                        context += f"File: {file_path}\nContent:\n{content}\n\n"
                    
                    # Create messages array
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "system", "content": f"Workspace context:\n{context}"},
                        {"role": "user", "content": prompt}
                    ]
                    
                    print(f"\n=== Step 2: Sending Request for Chunk {chunk_index + 1} ===")
                    socketio.emit('status', {
                        'message': f'Sending request for chunk {chunk_index + 1}/{len(chunks)}...',
                        'step': 2
                    })
                    
                    # Use streaming for better progress tracking
                    start_time = time.time()
                    full_text = ""
                    chunk_count = 0
                    last_update = time.time()
                    update_interval = 0.5
                    
                    if model_id == 'claude':
                        print("Sending request to Claude model...")
                        # Claude uses a different message format
                        system_content = f"{system_prompt}\n\nWorkspace context:\n{context}"
                        try:
                            response = client.messages.create(
                                model=model_config['models']['code'],
                                system=system_content,
                                messages=[{
                                    "role": "user",
                                    "content": prompt
                                }],
                                temperature=0.1,  # Lower temperature for code suggestions
                                max_tokens=2048
                            )
                            # Claude's response format is different from OpenAI's
                            if hasattr(response, 'content') and len(response.content) > 0:
                                full_text = response.content[0].text
                            else:
                                print("Error: No content in Claude's response")
                                return None
                        except Exception as e:
                            print(f"Error with Claude API: {str(e)}")
                            return None
                        print(f"\nResponse received in {time.time() - start_time:.1f}s")
                        print(f"Response length: {len(full_text)} characters")
                        
                        # Emit progress for consistency with streaming
                        socketio.emit('status', {
                            'message': f'Received response for chunk {chunk_index + 1}/{len(chunks)}',
                            'step': 3,
                            'progress': {
                                'chunk': chunk_index + 1,
                                'total_chunks': len(chunks),
                                'chars': len(full_text),
                                'elapsed': time.time() - start_time
                            }
                        })
                    else:
                        print("Request sent, waiting for response...")
                        socketio.emit('status', {
                            'message': f'Receiving response for chunk {chunk_index + 1}/{len(chunks)}...',
                            'step': 3
                        })
                        
                        response = client.chat.completions.create(
                            model=model_config['models']['code'],
                            messages=messages,
                            temperature=0.1,
                            stream=True
                        )
                        
                        for chunk_response in response:
                            if (chunk_response and 
                                hasattr(chunk_response.choices[0], 'delta') and 
                                hasattr(chunk_response.choices[0].delta, 'content')):
                                content = chunk_response.choices[0].delta.content
                                if content is not None:
                                    full_text += content
                                    chunk_count += 1
                                
                                # Update status periodically
                                current_time = time.time()
                                if current_time - last_update >= update_interval:
                                    elapsed = current_time - start_time
                                    tokens_per_second = chunk_count / elapsed if elapsed > 0 else 0
                                    print(f"\rReceived {chunk_count} chunks ({len(full_text)} chars) in {elapsed:.1f}s ({tokens_per_second:.1f} chunks/s)", end="")
                                    socketio.emit('status', {
                                        'message': f'Processing chunk {chunk_index + 1}/{len(chunks)}... ({len(full_text)} characters)',
                                        'step': 3,
                                        'progress': {
                                            'chunk': chunk_index + 1,
                                            'total_chunks': len(chunks),
                                            'chars': len(full_text),
                                            'elapsed': elapsed,
                                            'rate': tokens_per_second
                                        }
                                    })
                                    last_update = current_time
                        
                        print(f"\nResponse complete in {time.time() - start_time:.1f}s")
                        print(f"Total response size: {len(full_text)} characters in {chunk_count} chunks")
                    
                    print(f"\n=== Step 3: Processing Response for Chunk {chunk_index + 1} ===")
                    socketio.emit('status', {
                        'message': f'Processing response for chunk {chunk_index + 1}/{len(chunks)}...',
                        'step': 4
                    })
                    
                    # Clean up the response text
                    cleaned_text = full_text.strip()
                    
                    # Remove markdown code block markers
                    if cleaned_text.startswith('```'):
                        first_newline = cleaned_text.find('\n')
                        if first_newline != -1:
                            cleaned_text = cleaned_text[first_newline:].strip()
                        if cleaned_text.endswith('```'):
                            cleaned_text = cleaned_text[:-3].strip()
                    
                    # Parse the response
                    try:
                        result = json.loads(cleaned_text)
                        if isinstance(result, dict) and 'operations' in result:
                            print(f"Successfully parsed response with {len(result['operations'])} operations")
                            return result
                    except json.JSONDecodeError:
                        # Try to extract just the JSON part
                        try:
                            start = cleaned_text.find('{')
                            end = cleaned_text.rfind('}')
                            if start != -1 and end != -1 and start < end:
                                json_text = cleaned_text[start:end+1]
                                result = json.loads(json_text)
                                if isinstance(result, dict) and 'operations' in result:
                                    print(f"Successfully extracted and parsed JSON with {len(result['operations'])} operations")
                                    return result
                        except:
                            pass
                    
                    print(f"Failed to parse valid response from chunk {chunk_index + 1}")
                    return None
                    
                except Exception as e:
                    print(f"Error processing chunk {chunk_index + 1}: {str(e)}")
                    socketio.emit('status', {
                        'message': f'Error processing chunk {chunk_index + 1}: {str(e)}',
                        'step': -1
                    })
                    return None
        
        print("\n=== Starting Parallel Processing ===")
        print(f"Total chunks: {len(chunks)}")
        socketio.emit('status', {
            'message': f'Starting parallel processing of {len(chunks)} chunks...',
            'step': 1
        })
        
        # Process all chunks in parallel
        tasks = [process_chunk(chunk, i) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks)
        
        # Filter out None results
        valid_results = [result for result in results if result is not None]
        print(f"\n=== Processing Complete ===")
        print(f"Successfully processed {len(valid_results)}/{len(chunks)} chunks")
        
        return valid_results

    def merge_suggestions(self, suggestions_list: List[Dict]) -> Dict:
        """Merge suggestions from multiple chunks into a single response.
        
        Args:
            suggestions_list: List of suggestions from different chunks
            
        Returns:
            Merged suggestions dictionary
        """
        merged = {
            'explanation': 'Combined suggestions from parallel processing',
            'operations': []
        }
        
        seen_paths = set()
        
        for suggestions in suggestions_list:
            if not suggestions or 'operations' not in suggestions:
                continue
                
            for operation in suggestions['operations']:
                # Skip duplicate operations on the same file
                if operation['path'] in seen_paths:
                    continue
                    
                merged['operations'].append(operation)
                seen_paths.add(operation['path'])
        
        return merged 