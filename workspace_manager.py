import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Union
import json
import mmap

class WorkspaceManager:
    # File size thresholds and constants
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    PREVIEW_SIZE = 10 * 1024  # 10KB for previews
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks for large file reading
    
    # File type configurations
    BINARY_EXTENSIONS = {'.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe', '.bin'}
    SKIP_EXTENSIONS = {'.db'} | BINARY_EXTENSIONS
    LARGE_FILE_THRESHOLD = 1 * 1024 * 1024  # 1MB
    
    def __init__(self, workspace_root: str):
        """Initialize workspace manager with root directory"""
        self.workspace_root = workspace_root
        os.makedirs(workspace_root, exist_ok=True)
        
        # Cache for file contents and metadata
        self._content_cache: Dict[str, Tuple[str, float]] = {}  # path -> (content, mtime)
        self._structure_cache: Dict[str, Tuple[List[dict], float]] = {}  # workspace -> (structure, mtime)
    
    def _is_cache_valid(self, path: str, cache_entry: Tuple[Union[str, List[dict]], float]) -> bool:
        """Check if cached content is still valid"""
        try:
            return os.path.getmtime(path) == cache_entry[1]
        except OSError:
            return False
    
    def _is_binary_file(self, file_path: str, check_content: bool = True) -> bool:
        """Efficiently check if a file is binary"""
        # First check extension
        if any(file_path.endswith(ext) for ext in self.BINARY_EXTENSIONS):
            return True
            
        # Then check content if requested
        if check_content:
            try:
                with open(file_path, 'rb') as f:
                    chunk = f.read(1024)
                    return b'\x00' in chunk
            except:
                return True
        return False
    
    def _get_file_content(self, file_path: str, use_cache: bool = True) -> Optional[str]:
        """Get content of a single file with caching"""
        try:
            abs_path = os.path.abspath(file_path)
            
            # Check cache first
            if use_cache and abs_path in self._content_cache:
                cached_content, cached_mtime = self._content_cache[abs_path]
                if self._is_cache_valid(abs_path, (cached_content, cached_mtime)):
                    return cached_content
            
            # Skip if file is too large or binary
            if os.path.getsize(abs_path) > self.MAX_FILE_SIZE:
                return None
            if self._is_binary_file(abs_path):
                return None
            
            # Read file content
            content = None
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Try latin-1 as fallback
                try:
                    with open(abs_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                except:
                    return None
            
            # Cache the content
            if content and use_cache:
                self._content_cache[abs_path] = (content, os.path.getmtime(abs_path))
            
            return content
            
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None
    
    def get_workspace_files(self, workspace_dir: str, use_cache: bool = True) -> Dict[str, str]:
        """Get all readable files in workspace with efficient caching"""
        if not os.path.exists(workspace_dir) or not os.path.isdir(workspace_dir):
            raise ValueError('Invalid workspace directory')
        
        files_content = {}
        for root, _, files in os.walk(workspace_dir):
            for file in files:
                # Skip hidden and binary files
                if file.startswith('.') or any(file.endswith(ext) for ext in self.SKIP_EXTENSIONS):
                    continue
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, workspace_dir)
                
                content = self._get_file_content(file_path, use_cache)
                if content is not None:
                    files_content[rel_path] = content
        
        return files_content
    
    def get_workspace_structure(self, workspace_dir: str) -> List[dict]:
        """Get workspace file structure with caching"""
        try:
            # Check cache first
            if workspace_dir in self._structure_cache:
                cached_structure, cached_mtime = self._structure_cache[workspace_dir]
                if self._is_cache_valid(workspace_dir, (cached_structure, cached_mtime)):
                    return cached_structure
            
            structure = []
            is_imported = os.path.exists(os.path.join(workspace_dir, '.imported'))
            
            for root, dirs, files in os.walk(workspace_dir):
                rel_path = os.path.relpath(root, workspace_dir)
                if rel_path == '.':
                    rel_path = ''
                
                # Skip hidden directories and files
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                files = [f for f in files if not f.startswith('.')]
                
                # Add directories
                for name in dirs:
                    full_path = os.path.join(root, name)
                    rel_full_path = os.path.relpath(full_path, workspace_dir)
                    structure.append({
                        'name': name,
                        'type': 'directory',
                        'path': rel_full_path.replace('\\', '/'),
                        'imported': is_imported
                    })
                
                # Add files
                for name in files:
                    full_path = os.path.join(root, name)
                    rel_full_path = os.path.relpath(full_path, workspace_dir)
                    structure.append({
                        'name': name,
                        'type': 'file',
                        'path': rel_full_path.replace('\\', '/'),
                        'size': os.path.getsize(full_path)
                    })
            
            # Cache the structure
            self._structure_cache[workspace_dir] = (structure, os.path.getmtime(workspace_dir))
            return structure
            
        except Exception as e:
            print(f"Error getting workspace structure: {e}")
            return []
    
    def get_workspace_context(self, workspace_dir: str, include_content: bool = True) -> str:
        """Get unified workspace context for both chat and code generation"""
        try:
            # Get structure first (cached)
            structure = self.get_workspace_structure(workspace_dir)
            
            # Build context string
            context = ["Workspace Structure:"]
            for item in structure:
                prefix = "📁 " if item['type'] == 'directory' else "📄 "
                context.append(f"{prefix}{item['path']}")
            
            if include_content:
                # Get file contents (cached)
                files_content = self.get_workspace_files(workspace_dir)
                
                # Add file contents
                if files_content:
                    context.append("\nFile Contents:")
                    for file_path, content in files_content.items():
                        context.append(f"\nFile: {file_path}\nContent:\n{content}")
                
                # Analyze and add dependencies
                deps = self._analyze_dependencies(files_content)
                if deps:
                    context.append("\nFile Dependencies:")
                    for file, file_deps in deps.items():
                        if file_deps:
                            context.append(f"{file} depends on: {', '.join(file_deps)}")
            
            return "\n".join(context)
            
        except Exception as e:
            print(f"Error getting workspace context: {e}")
            return ""
    
    def _analyze_dependencies(self, files_content: Dict[str, str]) -> Dict[str, Set[str]]:
        """Analyze file dependencies based on imports and references"""
        dependencies = {}
        import_patterns = {
            '.py': ['import ', 'from '],
            '.js': ['import ', 'require('],
            '.html': ['<script src=', '<link href='],
            '.jsx': ['import ', 'require('],
            '.ts': ['import ', 'require('],
            '.tsx': ['import ', 'require('],
        }
        
        for file_path, content in files_content.items():
            ext = os.path.splitext(file_path)[1]
            deps = set()
            
            if ext in import_patterns:
                for line in content.split('\n'):
                    for pattern in import_patterns[ext]:
                        if pattern in line:
                            # Extract dependency name (simplified)
                            dep = line.split(pattern)[-1].split()[0].strip('"\';')
                            deps.add(dep)
            
            dependencies[file_path] = deps
        
        return dependencies
    
    def clear_cache(self):
        """Clear all caches"""
        self._content_cache.clear()
        self._structure_cache.clear()

    def generate_diff(self, file_path: str, changes: List[dict]) -> str:
        """Generate a unified diff for file changes"""
        try:
            # Get the original content
            original_content = self._get_file_content(file_path) or ""
            
            # Apply changes to get the new content
            new_content = original_content
            
            # Handle global replacements
            for change in changes:
                old_text = change['old']
                new_text = change['new']
                # If this is a simple text replacement (not a complex code change)
                # and it's a single word or phrase, do a global replace
                if (len(old_text.splitlines()) == 1 and 
                    not any(c in old_text for c in '{}()[]') and
                    not old_text.strip().startswith(('def ', 'class ', 'import ', 'from '))):
                    new_content = new_content.replace(old_text, new_text)
                else:
                    # For complex changes, do a single replacement
                    pos = new_content.find(old_text)
                    if pos != -1:
                        new_content = new_content[:pos] + new_text + new_content[pos + len(old_text):]
            
            # Ensure both contents end with a newline if either one does
            if original_content.endswith('\n') or new_content.endswith('\n'):
                original_content = original_content.rstrip('\n') + '\n'
                new_content = new_content.rstrip('\n') + '\n'
            
            # Generate unified diff
            return self._generate_unified_diff(
                original_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                os.path.basename(file_path)  # Only show filename in diff
            )
        except Exception as e:
            print(f"Error generating diff for {file_path}: {e}")
            return ""

    def _generate_unified_diff(self, a: List[str], b: List[str], filename: str) -> str:
        """Generate a unified diff between two lists of lines"""
        import difflib
        
        # Generate unified diff with 3 lines of context
        diff = list(difflib.unified_diff(
            a, b,
            fromfile=filename,
            tofile=filename,
            lineterm='',  # Don't add line terminators
            n=3
        ))
        
        # Clean up the diff output
        if diff:
            # Remove the first two lines (--- and +++) as they're redundant
            diff = diff[2:]
            # Join with newlines and ensure proper line endings
            return '\n'.join(line.rstrip('\n') for line in diff)
        return ''

    def run_linter(self, file_path: str) -> bool:
        """Run pylama for multi-language linting support"""
        try:
            import subprocess
            from pathlib import Path
            
            # Get file extension
            file_ext = Path(file_path).suffix.lower()
            
            # Skip binary or non-code files
            binary_extensions = {'.pyc', '.pyo', '.so', '.dll', '.exe', '.bin', '.jpg', '.png', '.gif'}
            if file_ext in binary_extensions:
                return True
            
            # Run pylama directly as a subprocess
            result = subprocess.run(['pylama', file_path], capture_output=True, text=True)
            
            # Return True if no issues found (exit code 0)
            return result.returncode == 0
            
        except Exception as e:
            print(f"Linting error for {file_path}: {str(e)}")
            return False

    def process_operations(self, operations: List[dict], workspace_dir: str) -> List[dict]:
        """Process operations and add diffs for edit operations"""
        processed = []
        for op in operations:
            try:
                if op['type'] == 'edit_file':
                    # Generate diff for edit operations
                    file_path = os.path.join(workspace_dir, op['path'])
                    if not os.path.exists(file_path):
                        # For new files that don't exist yet, show the entire content as added
                        op['diff'] = '\n'.join([
                            '@@ -0,0 +1,{} @@'.format(len(op.get('content', '').splitlines())),
                            *['+' + line for line in op.get('content', '').splitlines()]
                        ])
                    else:
                        # For existing files, generate proper diff
                        op['diff'] = self.generate_diff(file_path, op['changes'])
                    
                    # Create a temporary file with the new content for linting
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix=os.path.splitext(file_path)[1], delete=False) as tmp:
                        # Get original content and apply changes
                        content = self._get_file_content(file_path) if os.path.exists(file_path) else ""
                        new_content = content
                        for change in op['changes']:
                            if (len(change['old'].splitlines()) == 1 and 
                                not any(c in change['old'] for c in '{}()[]') and
                                not change['old'].strip().startswith(('def ', 'class ', 'import ', 'from '))):
                                new_content = new_content.replace(change['old'], change['new'])
                            else:
                                pos = new_content.find(change['old'])
                                if pos != -1:
                                    new_content = new_content[:pos] + change['new'] + new_content[pos + len(change['old']):]
                        
                        # Write to temp file
                        tmp.write(new_content)
                        tmp.flush()
                        
                        # Run linter on temp file
                        op['linter_status'] = self.run_linter(tmp.name)
                        
                        # Clean up
                        os.unlink(tmp.name)
                
                elif op['type'] == 'create_file':
                    # For new files, show the entire content as added
                    op['diff'] = '\n'.join([
                        '@@ -0,0 +1,{} @@'.format(len(op['content'].splitlines())),
                        *['+' + line for line in op['content'].splitlines()]
                    ])
                    
                    # Run linter on the new file content
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix=os.path.splitext(op['path'])[1], delete=False) as tmp:
                        tmp.write(op['content'])
                        tmp.flush()
                        op['linter_status'] = self.run_linter(tmp.name)
                        os.unlink(tmp.name)
                
                elif op['type'] == 'rename_file':
                    # For rename operations, show the file move
                    old_path = os.path.join(workspace_dir, op['path'])
                    new_path = os.path.join(workspace_dir, op['new_path'])
                    if os.path.exists(old_path):
                        content = self._get_file_content(old_path) or ""
                        op['diff'] = f"Rename {op['path']} → {op['new_path']}\n"
                        # Show file content in diff for context
                        op['diff'] += '\n'.join([
                            '@@ -1,{0} +1,{0} @@'.format(len(content.splitlines())),
                            *[' ' + line for line in content.splitlines()]
                        ])
                    op['linter_status'] = True  # No need to lint renamed files
                
                elif op['type'] == 'remove_file':
                    # For file removal, show the entire content as removed
                    file_path = os.path.join(workspace_dir, op['path'])
                    if os.path.exists(file_path):
                        content = self._get_file_content(file_path) or ""
                        op['diff'] = '\n'.join([
                            '@@ -1,{} +0,0 @@'.format(len(content.splitlines())),
                            *['-' + line for line in content.splitlines()]
                        ])
                    op['linter_status'] = True  # No need to lint removed files
                
                processed.append(op)
            except Exception as e:
                print(f"Error processing operation: {e}")
                op['error'] = str(e)
                processed.append(op)
        
        return processed 