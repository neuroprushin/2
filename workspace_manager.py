import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Union
import json
import mmap
from pathlib import Path

class WorkspaceManager:
    # File size thresholds and constants
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    PREVIEW_SIZE = 10 * 1024  # 10KB for previews
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks for large file reading
    LAZY_LOAD_THRESHOLD = 1000  # Number of files before switching to lazy loading
    
    # File type configurations
    BINARY_EXTENSIONS = {'.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe', '.bin'}
    SKIP_EXTENSIONS = {'.db'} | BINARY_EXTENSIONS
    LARGE_FILE_THRESHOLD = 1 * 1024 * 1024  # 1MB
    
    def __init__(self, workspace_root: str):
        """Initialize workspace manager with root directory"""
        self.workspace_root = workspace_root
        os.makedirs(workspace_root, exist_ok=True)
        
        # Enhanced caching system
        self._content_cache: Dict[str, Tuple[str, float, int]] = {}  # path -> (content, mtime, size)
        self._structure_cache: Dict[str, Tuple[List[dict], float]] = {}  # workspace -> (structure, mtime)
        self._chunk_cache: Dict[str, Dict[int, str]] = {}  # path -> {chunk_index: content}
        
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
                # Skip hidden files and directories
                if entry.name.startswith('.'):
                    continue
                    
                # Get path relative to current directory instead of workspace root
                rel_path = os.path.relpath(entry.path, abs_path)
                
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
            total_files = sum(len(files) for _, _, files in os.walk(workspace_dir))
            
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
    
    def expand_directory(self, dir_path: str) -> List[dict]:
        """Expand a directory node for lazy loading"""
        return self.get_directory_structure(dir_path, depth=1)
    
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
    
    def get_workspace_files(self, workspace_dir: str) -> Dict[str, str]:
        """Get content of existing files in workspace"""
        # Validate workspace directory
        if not os.path.exists(workspace_dir) or not os.path.isdir(workspace_dir):
            raise ValueError('Invalid workspace directory')
            
        files_content = {}
        for root, _, files in os.walk(workspace_dir):
            for file in files:
                # Skip database, hidden files, and common binary formats
                if (not file.endswith('.db') and 
                    not file.startswith('.') and 
                    not file.endswith(tuple(self.SKIP_EXTENSIONS))):
                    
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, workspace_dir)
                    try:
                        # Get file size
                        file_size = os.path.getsize(file_path)
                        if file_size > self.MAX_FILE_SIZE:
                            print(f"Warning: Skipping large file {rel_path} ({file_size} bytes)")
                            continue
                            
                        content = self._get_file_content(file_path)
                        if content:
                            files_content[rel_path] = content
                            
                    except Exception as e:
                        print(f"Warning: Could not read file {file_path}: {e}")
                        continue
                        
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