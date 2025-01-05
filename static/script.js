// Global Variables
let currentWorkspace = null;
let currentModel = 'deepseek';
let pendingChanges = null;
let socket = null;

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initializeWebSocket();
    initializeModelSelection();
    loadWorkspaceHistory();
    initializeKeyboardShortcuts();
});

// WebSocket Setup
function initializeWebSocket() {
    socket = io();
    
    // Status updates
    socket.on('status', (data) => {
        updateStatus(data.message, data.step);
    });
    
    // Progress updates
    socket.on('progress', (data) => {
        updateProgress(data.message, data.tokens);
    });
    
    // Connection status
    socket.on('connect', () => {
        console.log('Connected to server');
        updateConnectionStatus(true);
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        updateConnectionStatus(false);
    });
}

// UI Update Functions
function updateStatus(message, step) {
    const statusElement = document.getElementById('statusMessage') || createStatusElement();
    statusElement.textContent = message;
    
    // Update progress bar if exists
    const progressBar = document.getElementById('progressBar');
    if (progressBar) {
        progressBar.style.width = `${(step / 5) * 100}%`;
    }
    
    // Show error styling for negative steps
    if (step < 0) {
        statusElement.classList.add('error');
    } else {
        statusElement.classList.remove('error');
    }
}

function updateProgress(message, tokens) {
    const progressElement = document.getElementById('progressMessage') || createProgressElement();
    progressElement.textContent = message;
}

function updateConnectionStatus(connected) {
    const statusIndicator = document.getElementById('connectionStatus') || createConnectionIndicator();
    statusIndicator.className = `connection-status ${connected ? 'connected' : 'disconnected'}`;
    statusIndicator.title = connected ? 'Connected to server' : 'Disconnected from server';
}

// UI Element Creation
function createStatusElement() {
    const container = document.createElement('div');
    container.id = 'statusContainer';
    container.className = 'status-container fixed bottom-4 right-4 p-4 bg-gray-800 rounded-lg shadow-lg z-50';
    
    const message = document.createElement('div');
    message.id = 'statusMessage';
    message.className = 'text-white';
    
    const progress = document.createElement('div');
    progress.className = 'mt-2 h-2 bg-gray-700 rounded-full overflow-hidden';
    
    const bar = document.createElement('div');
    bar.id = 'progressBar';
    bar.className = 'h-full bg-blue-500 transition-all duration-300';
    bar.style.width = '0%';
    
    progress.appendChild(bar);
    container.appendChild(message);
    container.appendChild(progress);
    document.body.appendChild(container);
    
    return message;
}

function createProgressElement() {
    const container = document.createElement('div');
    container.id = 'progressContainer';
    container.className = 'progress-container fixed bottom-24 right-4 p-4 bg-gray-800 rounded-lg shadow-lg z-50';
    
    const message = document.createElement('div');
    message.id = 'progressMessage';
    message.className = 'text-white';
    
    container.appendChild(message);
    document.body.appendChild(container);
    
    return message;
}

function createConnectionIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'connectionStatus';
    indicator.className = 'connection-status';
    indicator.style.cssText = `
        position: fixed;
        top: 1rem;
        right: 1rem;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        z-index: 100;
    `;
    
    const style = document.createElement('style');
    style.textContent = `
        .connection-status.connected { background-color: #10B981; }
        .connection-status.disconnected { background-color: #EF4444; }
    `;
    document.head.appendChild(style);
    document.body.appendChild(indicator);
    
    return indicator;
}

// Model Selection
function initializeModelSelection() {
    const modelSelect = document.getElementById('modelSelect');
    modelSelect.addEventListener('change', (e) => {
        currentModel = e.target.value;
    });
    loadAvailableModels();
}

async function loadAvailableModels() {
    try {
        const response = await fetch('/models');
        const data = await response.json();

        if (data.status === 'success') {
            const modelSelect = document.getElementById('modelSelect');
            modelSelect.innerHTML = '';

            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name;
                modelSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading models:', error);
    }
}

// Mode Switching
function setMode(mode) {
    const codeMode = document.getElementById('codeMode');
    const chatMode = document.getElementById('chatMode');
    const codeModeBtn = document.querySelector('[onclick="setMode(\'code\')"]');
    const chatModeBtn = document.querySelector('[onclick="setMode(\'chat\')"]');

    if (mode === 'code') {
        codeMode.classList.remove('hidden');
        chatMode.classList.add('hidden');
        codeModeBtn.classList.add('active');
        chatModeBtn.classList.remove('active');
    } else {
        chatMode.classList.remove('hidden');
        codeMode.classList.add('hidden');
        chatModeBtn.classList.add('active');
        codeModeBtn.classList.remove('active');
    }
}

// Workspace Management
async function createWorkspace() {
    showLoading();
    try {
        const response = await fetch('/workspace/create', { method: 'POST' });
        const data = await response.json();

        if (data.status === 'success') {
            currentWorkspace = data.workspace_dir;
            updateWorkspaceInfo(data.workspace_id);
            updateWorkspaceTree(data.structure);
            await loadWorkspaceHistory();
        } else {
            showError('Failed to create workspace');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to create workspace: ' + error.message);
    } finally {
        hideLoading();
    }
}

async function loadWorkspaceHistory() {
    try {
        console.log('Loading workspace history');
        const response = await fetch('/workspace/history');
        const data = await response.json();
        console.log('Workspace history response:', data);

        if (data.status === 'success') {
            const historyList = document.getElementById('workspaceHistory');
            historyList.innerHTML = '';

            data.history.forEach(workspace => {
                console.log('Creating workspace item:', workspace);
                const workspaceDiv = document.createElement('div');
                const isImported = workspace.is_imported;
                workspaceDiv.className = `workspace-item flex items-center justify-between p-3 hover:bg-gray-700 rounded-lg cursor-pointer transition-colors ${isImported ? 'border-l-4 border-blue-500 bg-blue-900 bg-opacity-10' : ''} ${workspace.path === currentWorkspace ? 'bg-blue-900 bg-opacity-20' : ''}`;
                workspaceDiv.dataset.path = workspace.path;
                console.log('Set workspace path:', workspaceDiv.dataset.path);
                
                // Make the entire div clickable
                workspaceDiv.onclick = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('Workspace clicked:', workspace.path);
                    selectWorkspace(workspace.path);
                };
                
                const infoDiv = document.createElement('div');
                infoDiv.className = 'flex-1';
                
                const nameSpan = document.createElement('div');
                nameSpan.className = 'flex items-center gap-2';
                nameSpan.innerHTML = `
                    <i class="fas fa-${isImported ? 'link' : 'folder'} ${isImported ? 'text-blue-400' : 'text-gray-400'}"></i>
                    <span class="font-medium">${workspace.id}</span>
                    ${isImported ? '<span class="text-xs text-blue-400">(Imported)</span>' : ''}
                `;
                
                const statsSpan = document.createElement('span');
                statsSpan.className = 'text-sm text-gray-400 block mt-1';
                statsSpan.textContent = `${workspace.file_count} files`;
                
                infoDiv.appendChild(nameSpan);
                infoDiv.appendChild(statsSpan);
                
                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'flex items-center gap-2';
                
                if (isImported) {
                    // Show Unlink button for imported workspaces
                    const unlinkBtn = document.createElement('button');
                    unlinkBtn.className = 'p-2 text-red-400 hover:text-red-300 transition-colors';
                    unlinkBtn.innerHTML = '<i class="fas fa-unlink"></i>';
                    unlinkBtn.title = 'Unlink workspace';
                    unlinkBtn.onclick = (e) => {
                        e.stopPropagation();
                        if (confirm('Are you sure you want to unlink this workspace? The original folder will remain unchanged.')) {
                            deleteWorkspace(workspace.id);
                        }
                    };
                    actionsDiv.appendChild(unlinkBtn);
                } else {
                    // Show Rename and Delete buttons for regular workspaces
                    const renameBtn = document.createElement('button');
                    renameBtn.className = 'p-2 text-blue-400 hover:text-blue-300 transition-colors';
                    renameBtn.innerHTML = '<i class="fas fa-edit"></i>';
                    renameBtn.title = 'Rename workspace';
                    renameBtn.onclick = (e) => {
                        e.stopPropagation();
                        const newName = prompt('Enter new workspace name:', workspace.id);
                        if (newName && newName !== workspace.id) {
                            renameWorkspace(workspace.id, newName);
                        }
                    };
                    
                    const deleteBtn = document.createElement('button');
                    deleteBtn.className = 'p-2 text-red-400 hover:text-red-300 transition-colors';
                    deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
                    deleteBtn.title = 'Delete workspace';
                    deleteBtn.onclick = (e) => {
                        e.stopPropagation();
                        if (confirm('Are you sure you want to delete this workspace? This action cannot be undone.')) {
                            deleteWorkspace(workspace.id);
                        }
                    };
                    
                    actionsDiv.appendChild(renameBtn);
                    actionsDiv.appendChild(deleteBtn);
                }
                
                workspaceDiv.appendChild(infoDiv);
                workspaceDiv.appendChild(actionsDiv);
                historyList.appendChild(workspaceDiv);
            });
        }
    } catch (error) {
        console.error('Error loading history:', error);
        showError('Failed to load workspace history');
    }
}

async function deleteWorkspace(workspaceId) {
    try {
        const response = await fetch('/workspace/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ workspace_id: workspaceId })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            // If the deleted workspace was the current one, clear it
            if (currentWorkspace && currentWorkspace.endsWith(workspaceId)) {
                currentWorkspace = null;
                document.getElementById('currentWorkspaceInfo').classList.add('hidden');
                document.getElementById('workspaceTree').innerHTML = '';
            }
            
            // Reload the workspace history
            loadWorkspaceHistory();
        } else {
            showError(data.message || 'Failed to delete workspace');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to delete workspace: ' + error.message);
    }
}

async function renameWorkspace(workspaceId, newName) {
    try {
        const response = await fetch('/workspace/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_id: workspaceId,
                new_name: newName
            })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            // If the renamed workspace was the current one, update it
            if (currentWorkspace && currentWorkspace.endsWith(workspaceId)) {
                currentWorkspace = data.new_path;
                updateWorkspaceInfo(newName);
            }
            
            // Reload the workspace history
            loadWorkspaceHistory();
        } else {
            showError(data.message || 'Failed to rename workspace');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to rename workspace: ' + error.message);
    }
}

function createButton(iconClass, buttonClass, onClick) {
    const button = document.createElement('button');
    button.className = buttonClass + ' transition-colors';
    button.innerHTML = `<i class="${iconClass}"></i>`;
    button.onclick = (e) => {
        e.stopPropagation();
        onClick();
    };
    return button;
}

async function selectWorkspace(path) {
    console.log('Selecting workspace:', path);
    
    // Clear previous selection
    document.querySelectorAll('.workspace-item').forEach(item => {
        item.classList.remove('bg-blue-900', 'bg-opacity-20');
    });
    
    // Find and highlight the selected workspace
    const selectedItem = Array.from(document.querySelectorAll('.workspace-item')).find(
        item => item.dataset.path === path
    );
    console.log('Found selected item:', selectedItem);
    if (selectedItem) {
        selectedItem.classList.add('bg-blue-900', 'bg-opacity-20');
    }

    currentWorkspace = path;
    console.log('Current workspace set to:', currentWorkspace);
    
    try {
        console.log('Fetching workspace structure for:', path);
        const response = await fetch('/workspace/structure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ workspace_dir: path })
        });
        
        const data = await response.json();
        console.log('Workspace structure response:', data);
        
        if (data.status === 'success') {
            // Update workspace info
            const workspaceInfo = document.getElementById('currentWorkspaceInfo');
            if (workspaceInfo) {
                workspaceInfo.classList.remove('hidden');
            }
            
            const workspaceName = document.getElementById('currentWorkspaceName');
            if (workspaceName) {
                workspaceName.textContent = path.split('/').pop();
            }
            
            // Update tree structure
            const workspaceTree = document.getElementById('workspaceTree');
            if (workspaceTree) {
                workspaceTree.innerHTML = '';
                buildTree(data.structure, workspaceTree);
            }
        } else {
            showError('Failed to load workspace structure');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to load workspace structure: ' + error.message);
    }
}

function updateWorkspaceInfo(id) {
    currentWorkspace = id;
    const workspaceInfo = document.getElementById('currentWorkspaceInfo');
    const workspaceName = document.getElementById('currentWorkspaceName');
    
    if (workspaceInfo) {
        workspaceInfo.classList.remove('hidden');
    }
    
    if (workspaceName) {
        workspaceName.textContent = id;
    }
}

// File Tree Management
function updateWorkspaceTree(structure) {
    const workspaceTree = document.getElementById('workspaceTree');
    if (workspaceTree) {
        workspaceTree.innerHTML = '';
        buildTree(structure, workspaceTree);
    }
}

function buildTree(structure, container) {
    structure.forEach(item => {
        const itemDiv = document.createElement('div');
        itemDiv.className = `tree-item ${item.type === 'directory' ? 'folder' : 'file'}`;
        
        // Get the relative path by removing any leading slashes
        const relativePath = item.path.replace(/^[\/\\]+/, '');
        
        if (item.type === 'directory') {
            const folderHeader = document.createElement('div');
            folderHeader.className = 'folder-header flex items-center gap-2 p-1 hover:bg-gray-700 rounded cursor-pointer';
            
            const icon = document.createElement('i');
            icon.className = 'fas fa-folder text-yellow-400';
            folderHeader.appendChild(icon);
            
            const name = document.createElement('span');
            name.className = 'name text-gray-300';
            name.textContent = relativePath.split('/').pop();
            folderHeader.appendChild(name);
            
            itemDiv.appendChild(folderHeader);
            
            const children = document.createElement('div');
            children.className = 'children ml-4 mt-1';
            itemDiv.appendChild(children);
            
            // Lazy loading of directory contents
            folderHeader.onclick = async () => {
                if (!itemDiv.classList.contains('expanded')) {
                    // Only load children if not already loaded
                    if (!children.hasChildNodes() && item.has_children) {
                        try {
                            const response = await fetch('/workspace/expand', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ 
                                    workspace_dir: currentWorkspace,
                                    dir_path: relativePath 
                                })
                            });
                            
                            const data = await response.json();
                            if (data.status === 'success') {
                                buildTree(data.children, children);
                            }
                        } catch (error) {
                            console.error('Error expanding directory:', error);
                        }
                    }
                }
                itemDiv.classList.toggle('expanded');
                icon.className = itemDiv.classList.contains('expanded') ? 'fas fa-folder-open text-yellow-400' : 'fas fa-folder text-yellow-400';
            };
        } else {
            const fileHeader = document.createElement('div');
            fileHeader.className = 'file-header flex items-center gap-2 p-1 hover:bg-gray-700 rounded cursor-pointer';
            
            const icon = document.createElement('i');
            const iconClass = getFileIcon(relativePath);
            icon.className = `fas ${iconClass}`;
            fileHeader.appendChild(icon);
            
            const name = document.createElement('span');
            name.className = 'name text-gray-300';
            name.textContent = relativePath.split('/').pop();
            fileHeader.appendChild(name);
            
            // Show file size for large files
            if (item.size > 1024 * 1024) { // 1MB
                const size = document.createElement('span');
                size.className = 'text-xs text-gray-400';
                size.textContent = `${(item.size / (1024 * 1024)).toFixed(1)}MB`;
                fileHeader.appendChild(size);
            }
            
            itemDiv.appendChild(fileHeader);
            
            // Add click handler to view file content
            fileHeader.onclick = () => showFileContent(relativePath);
        }
        
        container.appendChild(itemDiv);
    });
}

function getFileIcon(path) {
    const ext = path.split('.').pop().toLowerCase();
    const filename = path.split('/').pop().toLowerCase();
    
    // First check for specific filenames
    const filenameIcons = {
        'dockerfile': 'fa-docker text-blue-400',
        'docker-compose.yml': 'fa-docker text-blue-400',
        'docker-compose.yaml': 'fa-docker text-blue-400',
        '.dockerignore': 'fa-docker text-gray-400',
        '.gitignore': 'fa-git text-gray-400',
        '.gitattributes': 'fa-git text-gray-400',
        '.gitmodules': 'fa-git text-gray-400',
        '.env': 'fa-lock text-yellow-400',
        '.env.example': 'fa-lock text-gray-400',
        '.env.local': 'fa-lock text-yellow-400',
        '.env.development': 'fa-lock text-green-400',
        '.env.production': 'fa-lock text-red-400',
        'package.json': 'fa-npm text-red-400',
        'package-lock.json': 'fa-npm text-red-400',
        'composer.json': 'fa-php text-purple-400',
        'composer.lock': 'fa-php text-purple-400',
        'requirements.txt': 'fa-python text-blue-400',
        'pipfile': 'fa-python text-blue-400',
        'pipfile.lock': 'fa-python text-blue-400',
        'poetry.lock': 'fa-python text-blue-400',
        'pyproject.toml': 'fa-python text-blue-400',
        'cargo.toml': 'fa-cube text-brown-400',
        'cargo.lock': 'fa-cube text-brown-400',
        'makefile': 'fa-cogs text-gray-400',
        'readme.md': 'fa-book text-blue-400',
        'changelog.md': 'fa-clipboard-list text-blue-400',
        'license': 'fa-certificate text-yellow-400',
        'license.md': 'fa-certificate text-yellow-400',
        'license.txt': 'fa-certificate text-yellow-400',
        'contributing.md': 'fa-hands-helping text-blue-400',
        'authors.md': 'fa-users text-blue-400',
        'security.md': 'fa-shield-alt text-red-400',
        'robots.txt': 'fa-robot text-gray-400',
        'manifest.json': 'fa-puzzle-piece text-purple-400',
        'browserslist': 'fa-browsers text-orange-400',
        '.eslintrc': 'fa-lint text-purple-400',
        '.prettierrc': 'fa-paint-brush text-pink-400',
        '.babelrc': 'fa-babel text-yellow-400',
        'tsconfig.json': 'fa-typescript text-blue-400',
        'jest.config.js': 'fa-jest text-red-400',
        'webpack.config.js': 'fa-webpack text-blue-400',
        'vite.config.js': 'fa-vite text-yellow-400',
        'next.config.js': 'fa-next text-black',
        'nuxt.config.js': 'fa-nuxt text-green-400',
        'angular.json': 'fa-angular text-red-400',
        'vue.config.js': 'fa-vuejs text-green-400',
        'svelte.config.js': 'fa-svelte text-orange-400'
    };

    if (filenameIcons[filename]) {
        return filenameIcons[filename];
    }

    // Then check file extensions
    const extensionIcons = {
        // Web Development
        'html': 'fa-html5 text-orange-400',
        'htm': 'fa-html5 text-orange-400',
        'xhtml': 'fa-html5 text-orange-400',
        'css': 'fa-css3 text-blue-400',
        'scss': 'fa-sass text-pink-400',
        'sass': 'fa-sass text-pink-400',
        'less': 'fa-less text-blue-400',
        'styl': 'fa-stylus text-green-400',
        'js': 'fa-js text-yellow-400',
        'jsx': 'fa-react text-blue-400',
        'cjs': 'fa-node text-green-400',
        'mjs': 'fa-node text-green-400',
        'ts': 'fa-typescript text-blue-400',
        'tsx': 'fa-react text-blue-400',
        'vue': 'fa-vuejs text-green-400',
        'svelte': 'fa-svelte text-orange-400',
        'php': 'fa-php text-purple-400',
        'phtml': 'fa-php text-purple-400',
        'rb': 'fa-gem text-red-400',
        'erb': 'fa-gem text-red-400',
        'py': 'fa-python text-blue-400',
        'pyc': 'fa-python text-gray-400',
        'pyo': 'fa-python text-gray-400',
        'pyd': 'fa-python text-gray-400',
        'java': 'fa-java text-red-400',
        'class': 'fa-java text-red-400',
        'jar': 'fa-java text-red-400',
        'war': 'fa-java text-red-400',
        'jsp': 'fa-java text-red-400',
        'go': 'fa-golang text-blue-400',
        'rs': 'fa-rust text-brown-400',
        'rlib': 'fa-rust text-brown-400',
        'swift': 'fa-swift text-orange-400',
        'kt': 'fa-kotlin text-purple-400',
        'kts': 'fa-kotlin text-purple-400',
        'dart': 'fa-dart text-blue-400',
        'coffee': 'fa-coffee text-brown-400',
        'elm': 'fa-elm text-blue-400',
        'erl': 'fa-erlang text-red-400',
        'ex': 'fa-elixir text-purple-400',
        'exs': 'fa-elixir text-purple-400',
        'fs': 'fa-microsoft text-purple-400',
        'fsx': 'fa-microsoft text-purple-400',
        'fsi': 'fa-microsoft text-purple-400',
        'rs': 'fa-rust text-brown-400',
        'rlib': 'fa-rust text-brown-400',

        // Data & Config
        'json': 'fa-code text-yellow-400',
        'yaml': 'fa-file-code text-red-400',
        'yml': 'fa-file-code text-red-400',
        'xml': 'fa-file-code text-orange-400',
        'toml': 'fa-file-code text-gray-400',
        'ini': 'fa-cog text-gray-400',
        'conf': 'fa-cog text-gray-400',
        'config': 'fa-cog text-gray-400',
        'sql': 'fa-database text-blue-400',
        'sqlite': 'fa-database text-blue-400',
        'db': 'fa-database text-blue-400',
        'mdb': 'fa-database text-blue-400',
        'pdb': 'fa-database text-blue-400',
        'graphql': 'fa-project-diagram text-pink-400',
        'gql': 'fa-project-diagram text-pink-400',
        'prisma': 'fa-database text-blue-400',
        'csv': 'fa-file-csv text-green-400',
        'tsv': 'fa-file-alt text-green-400',
        'properties': 'fa-cog text-gray-400',

        // Shell Scripts
        'sh': 'fa-terminal text-green-400',
        'bash': 'fa-terminal text-green-400',
        'zsh': 'fa-terminal text-green-400',
        'fish': 'fa-terminal text-green-400',
        'ps1': 'fa-terminal text-blue-400',
        'psm1': 'fa-terminal text-blue-400',
        'psd1': 'fa-terminal text-blue-400',
        'bat': 'fa-terminal text-blue-400',
        'cmd': 'fa-terminal text-blue-400',
        'reg': 'fa-windows text-blue-400',

        // Documents
        'md': 'fa-markdown text-white',
        'mdx': 'fa-markdown text-blue-400',
        'txt': 'fa-file-alt text-gray-400',
        'rtf': 'fa-file-alt text-blue-400',
        'pdf': 'fa-file-pdf text-red-400',
        'doc': 'fa-file-word text-blue-400',
        'docx': 'fa-file-word text-blue-400',
        'docm': 'fa-file-word text-blue-400',
        'xls': 'fa-file-excel text-green-400',
        'xlsx': 'fa-file-excel text-green-400',
        'xlsm': 'fa-file-excel text-green-400',
        'ppt': 'fa-file-powerpoint text-orange-400',
        'pptx': 'fa-file-powerpoint text-orange-400',
        'pptm': 'fa-file-powerpoint text-orange-400',
        'odt': 'fa-file-alt text-blue-400',
        'ods': 'fa-file-alt text-green-400',
        'odp': 'fa-file-alt text-orange-400',
        'pages': 'fa-apple text-blue-400',
        'numbers': 'fa-apple text-green-400',
        'keynote': 'fa-apple text-orange-400',
        'tex': 'fa-tex text-green-400',
        'latex': 'fa-tex text-green-400',
        'rst': 'fa-file-alt text-blue-400',
        'adoc': 'fa-file-alt text-blue-400',
        'epub': 'fa-book text-blue-400',
        'mobi': 'fa-book text-orange-400',

        // Images
        'jpg': 'fa-file-image text-pink-400',
        'jpeg': 'fa-file-image text-pink-400',
        'png': 'fa-file-image text-green-400',
        'gif': 'fa-file-image text-purple-400',
        'bmp': 'fa-file-image text-gray-400',
        'svg': 'fa-file-image text-orange-400',
        'svgz': 'fa-file-image text-orange-400',
        'ico': 'fa-file-image text-blue-400',
        'webp': 'fa-file-image text-blue-400',
        'tif': 'fa-file-image text-purple-400',
        'tiff': 'fa-file-image text-purple-400',
        'psd': 'fa-adobe text-blue-400',
        'psb': 'fa-adobe text-blue-400',
        'ai': 'fa-adobe text-orange-400',
        'eps': 'fa-adobe text-orange-400',
        'raw': 'fa-camera text-gray-400',
        'cr2': 'fa-camera text-gray-400',
        'nef': 'fa-camera text-gray-400',
        'sketch': 'fa-pencil-ruler text-yellow-400',
        'fig': 'fa-pencil-ruler text-purple-400',
        'xcf': 'fa-paint-brush text-orange-400',
        'heic': 'fa-file-image text-blue-400',
        'heif': 'fa-file-image text-blue-400',

        // Audio & Video
        'mp3': 'fa-file-audio text-purple-400',
        'wav': 'fa-file-audio text-blue-400',
        'ogg': 'fa-file-audio text-blue-400',
        'flac': 'fa-file-audio text-green-400',
        'aac': 'fa-file-audio text-red-400',
        'm4a': 'fa-file-audio text-red-400',
        'wma': 'fa-file-audio text-blue-400',
        'aiff': 'fa-file-audio text-gray-400',
        'mp4': 'fa-file-video text-red-400',
        'avi': 'fa-file-video text-blue-400',
        'mov': 'fa-file-video text-blue-400',
        'wmv': 'fa-file-video text-blue-400',
        'flv': 'fa-file-video text-red-400',
        'webm': 'fa-file-video text-green-400',
        'mkv': 'fa-file-video text-purple-400',
        'm4v': 'fa-file-video text-red-400',
        'mpg': 'fa-file-video text-blue-400',
        'mpeg': 'fa-file-video text-blue-400',
        '3gp': 'fa-file-video text-gray-400',

        // Archives
        'zip': 'fa-file-archive text-yellow-400',
        'rar': 'fa-file-archive text-purple-400',
        '7z': 'fa-file-archive text-gray-400',
        'tar': 'fa-file-archive text-brown-400',
        'gz': 'fa-file-archive text-red-400',
        'bz2': 'fa-file-archive text-red-400',
        'xz': 'fa-file-archive text-blue-400',
        'iso': 'fa-compact-disc text-gray-400',
        'dmg': 'fa-apple text-gray-400',
        'pkg': 'fa-box text-blue-400',
        'deb': 'fa-ubuntu text-orange-400',
        'rpm': 'fa-fedora text-blue-400',

        // Development
        'c': 'fa-file-code text-blue-400',
        'h': 'fa-file-code text-blue-400',
        'cpp': 'fa-file-code text-blue-400',
        'hpp': 'fa-file-code text-blue-400',
        'cc': 'fa-file-code text-blue-400',
        'hh': 'fa-file-code text-blue-400',
        'cs': 'fa-microsoft text-purple-400',
        'csx': 'fa-microsoft text-purple-400',
        'vb': 'fa-microsoft text-blue-400',
        'fs': 'fa-microsoft text-purple-400',
        'm': 'fa-apple text-gray-400',
        'mm': 'fa-apple text-gray-400',
        'swift': 'fa-apple text-orange-400',
        'r': 'fa-chart-line text-blue-400',
        'rmd': 'fa-chart-line text-blue-400',
        'matlab': 'fa-chart-line text-orange-400',
        'pl': 'fa-code text-blue-400',
        'pm': 'fa-code text-blue-400',
        'lua': 'fa-moon text-blue-400',
        'clj': 'fa-code text-green-400',
        'scala': 'fa-code text-red-400',
        'erl': 'fa-code text-red-400',
        'ex': 'fa-code text-purple-400',
        'exs': 'fa-code text-purple-400',
        'hx': 'fa-code text-orange-400',
        'hs': 'fa-code text-purple-400',
        'idr': 'fa-code text-red-400',
        'ml': 'fa-code text-orange-400',
        'mli': 'fa-code text-orange-400',
        'rkt': 'fa-code text-red-400',
        'elm': 'fa-leaf text-blue-400',

        // Other
        'log': 'fa-file-alt text-gray-400',
        'lock': 'fa-lock text-yellow-400',
        'key': 'fa-key text-yellow-400',
        'pem': 'fa-key text-green-400',
        'crt': 'fa-certificate text-green-400',
        'cer': 'fa-certificate text-green-400',
        'p12': 'fa-certificate text-purple-400',
        'pfx': 'fa-certificate text-purple-400',
        'pub': 'fa-key text-yellow-400',
        'gpg': 'fa-key text-red-400',
        'asc': 'fa-key text-gray-400',
        'enc': 'fa-lock text-red-400',
        'sig': 'fa-signature text-blue-400',
        'sum': 'fa-check-double text-green-400',
        'md5': 'fa-check-double text-blue-400',
        'sha1': 'fa-check-double text-blue-400',
        'sha256': 'fa-check-double text-blue-400',
        'tmp': 'fa-clock text-gray-400',
        'temp': 'fa-clock text-gray-400',
        'cache': 'fa-database text-gray-400',
        'bak': 'fa-history text-gray-400',
        'old': 'fa-history text-gray-400',
        'orig': 'fa-history text-gray-400',
        'swp': 'fa-history text-gray-400',
        'dist': 'fa-box text-blue-400',
        'min': 'fa-compress-arrows-alt text-blue-400',
        'map': 'fa-map text-green-400',
        'flow': 'fa-project-diagram text-blue-400',
        'test': 'fa-vial text-green-400',
        'spec': 'fa-vial text-green-400'
    };

    return extensionIcons[ext] || 'fa-file-code text-gray-400';
}

// Code Generation
async function processPrompt() {
    if (!validateWorkspace()) return;

    const promptInput = document.getElementById('promptInput');
    const prompt = promptInput.value.trim();
    
    if (!prompt) {
        showError('Please enter a prompt');
        return;
    }

    // Collect attachments
    const attachments = [];
    document.querySelectorAll('#codeAttachments > div').forEach(div => {
        attachments.push({
            name: div.querySelector('span').textContent,
            content: div.dataset.content // Get the stored file content
        });
    });

    showLoading();
    try {
        const response = await fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                workspace_dir: currentWorkspace,
                model_id: document.getElementById('modelSelect').value,
                attachments: attachments
            })
        });

        const data = await response.json();
        
        if (data.status === 'error') {
            showError(data.message || 'No changes to apply');
            return;
        }

        currentWorkspace = data.workspace_dir;
        if (data.structure) {
            updateWorkspaceTree(data.structure);
        }
        if (data.requires_approval) {
            showApprovalModal(data);
        }

    } catch (error) {
        console.error('Error:', error);
        showError('Failed to process prompt: ' + error.message);
    } finally {
        hideLoading();
    }
}

// Chat Functionality
async function sendChatMessage() {
    if (!validateWorkspace()) return;

    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();
    
    if (!message) {
        showError('Please enter a message');
        return;
    }

    // Collect attachments
    const attachments = [];
    document.querySelectorAll('#chatAttachments > div').forEach(div => {
        attachments.push({
            name: div.querySelector('span').textContent,
            content: div.dataset.content // Get the stored file content
        });
    });

    // Append user message first
    appendChatMessage(message, 'user');
    chatInput.value = '';

    // Show loading indicator
    const loadingMessage = appendChatMessage('<i class="fas fa-spinner fa-spin"></i> Thinking...', 'assistant', true);
    
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: message,
                workspace_dir: currentWorkspace,
                model_id: document.getElementById('modelSelect').value,
                attachments: attachments
            })
        });

        const data = await response.json();
        
        // Remove loading message
        loadingMessage.remove();

        if (data.status === 'success') {
            const formattedResponse = formatChatResponse(data.response);
            appendChatMessage(formattedResponse, 'assistant', true);
        } else {
            appendErrorMessage(data.message || 'Failed to get response');
        }
    } catch (error) {
        console.error('Error:', error);
        loadingMessage.remove();
        appendErrorMessage('Error: ' + error.message);
    }
}

function clearChatHistory() {
    if (confirm('Are you sure you want to clear the chat history?')) {
        const chatHistory = document.getElementById('chatHistory');
        if (chatHistory) {
            chatHistory.innerHTML = '';
            // Add a system message to indicate the chat was cleared
            appendChatMessage('Chat history has been cleared.', 'assistant', true);
        }
    }
}

function formatChatResponse(text) {
    // Configure marked options
    marked.setOptions({
        breaks: true,  // Convert line breaks
        gfm: true,     // Use GitHub Flavored Markdown
        headerIds: false,
        mangle: false
    });

    // Split text into code blocks and regular text
    const parts = text.split('```');
    const formattedParts = [];
    
    for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
            // Regular text: convert markdown to HTML
            let regularText = parts[i].trim();
            if (regularText) {
                regularText = marked.parse(regularText);
                regularText = regularText.replace(/\s+$/, '');
                formattedParts.push(regularText);
            }
        } else {
            // Code block: preserve original formatting
            let code = parts[i];
            let language = '';
            
            // Check if language is specified
            const firstLineBreak = code.indexOf('\n');
            if (firstLineBreak !== -1) {
                language = code.substring(0, firstLineBreak).trim();
                code = code.substring(firstLineBreak + 1);
            }
            
            // Clean up code: remove extra newlines and spaces
            code = code.trim()
                .replace(/\n\s*\n/g, '\n') // Remove empty lines
                .replace(/[ \t]+$/gm, '') // Remove trailing spaces from each line
                .replace(/^\s+|\s+$/g, ''); // Remove leading/trailing spaces
            
            // Preserve original formatting
            code = code
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');

            formattedParts.push(`<pre class="bg-gray-800 p-4 rounded-lg overflow-x-auto font-mono text-sm"><code class="language-${language}">${code}</code></pre>`);
        }
    }
    
    // Join parts and clean up
    let result = formattedParts.join('');
    
    // Clean up any remaining unwanted tags or spaces
    result = result.replace(/\s*<br\s*\/?>\s*<br\s*\/?>\s*/g, '<br>');
    result = result.replace(/\s*<br\s*\/?>\s*<\/p>/g, '</p>');
    result = result.replace(/<p>\s*<br\s*\/?>\s*/g, '<p>');
    result = result.replace(/\s+$/g, '');
    result = result.replace(/<\/pre>\s+<p>/g, '</pre><p>');
    result = result.replace(/<\/p>\s+<pre>/g, '</p><pre>');
    
    return result;
}

function appendChatMessage(content, type, isHtml = false) {
    const chatHistory = document.getElementById('chatHistory');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type} mb-4 p-4 rounded ${type === 'user' ? 'bg-blue-900' : 'bg-gray-800'}`;
    
    if (isHtml) {
        messageDiv.innerHTML = content;
    } else {
        messageDiv.textContent = content;
    }
    
    chatHistory.appendChild(messageDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return messageDiv;
}

function appendErrorMessage(message) {
    appendChatMessage(`<span class="text-red-500">${message}</span>`, 'assistant', true);
}

// Modal Management
function showApprovalModal(data) {
    const modal = document.getElementById('approvalModal');
    const preview = document.getElementById('changesPreview');
    const modalTitle = modal.querySelector('.modal-header h2');
    const footer = modal.querySelector('.modal-footer .flex');
    
    // Reset modal content
    modalTitle.textContent = data.title || 'Review Changes';
    preview.innerHTML = '';
    footer.innerHTML = '';

    // If it's a file preview
    if (data.isFilePreview) {
        if (data.fileInfo) {
            const fileInfo = document.createElement('div');
            fileInfo.className = 'flex items-center gap-3 mb-6 p-4 bg-gray-700 rounded-lg';
            fileInfo.innerHTML = `
                <i class="${getFileIcon(data.fileInfo.name)} text-xl"></i>
                <div>
                    <h3 class="text-lg font-medium">${data.fileInfo.name}</h3>
                    <p class="text-sm text-gray-400">${data.fileInfo.path}</p>
                </div>
            `;
            preview.appendChild(fileInfo);
        }

        if (data.content) {
            const editorDiv = document.createElement('div');
            editorDiv.style.height = '500px';
            editorDiv.className = 'relative bg-gray-900 rounded-lg';
            
            const textarea = document.createElement('textarea');
            textarea.value = data.content;
            editorDiv.appendChild(textarea);
            preview.appendChild(editorDiv);

            CodeMirror.fromTextArea(textarea, {
                mode: getLanguageMode(data.fileInfo?.path || ''),
                theme: 'monokai',
                lineNumbers: true,
                matchBrackets: true,
                styleActiveLine: true,
                scrollbarStyle: 'overlay',
                readOnly: true
            });

            // Add close button for file preview
            const closeBtn = document.createElement('button');
            closeBtn.className = 'btn btn-secondary';
            closeBtn.textContent = 'Close';
            closeBtn.onclick = hideModal;
            footer.appendChild(closeBtn);
        }
    } else {
        // For code changes preview
        const suggestions = data.suggestions || {};
        
        if (suggestions.explanation) {
            appendExplanation(preview, suggestions.explanation);
        }

        if (suggestions.operations) {
            suggestions.operations.forEach(operation => {
                appendOperation(preview, operation);
            });
            appendModalButtons(footer, suggestions.operations);
        }
    }

    modal.classList.remove('hidden');
}

function appendExplanation(container, explanation) {
    const explanationDiv = document.createElement('div');
    explanationDiv.className = 'mb-6 p-4 bg-gray-700 rounded-lg';
    explanationDiv.innerHTML = `
        <h3 class="text-lg font-medium mb-2">Overview</h3>
        <p class="text-gray-300">${explanation}</p>
    `;
    container.appendChild(explanationDiv);
}

function appendOperation(container, operation) {
    const operationDiv = document.createElement('div');
    operationDiv.className = 'mb-8 bg-gray-700 rounded-lg p-4';

    // Operation header
    const header = document.createElement('div');
    header.className = 'operation-header flex items-center justify-between mb-4';
    
    // Left side: icon and title
    const leftSide = document.createElement('div');
    leftSide.className = 'flex items-center gap-2';
    
    // Icon based on operation type
    const icon = document.createElement('i');
    icon.className = `fas ${getOperationIcon(operation.type)}`;
    leftSide.appendChild(icon);
    
    // Operation title
    const title = document.createElement('span');
    title.className = 'font-medium';
    title.textContent = formatOperationTitle(operation);
    leftSide.appendChild(title);
    
    header.appendChild(leftSide);
    
    // Right side: linter status
    if (operation.lint_passed !== undefined) {
        const linterStatus = document.createElement('div');
        linterStatus.className = 'flex items-center gap-2';
        linterStatus.innerHTML = `
            <i class="fas fa-${operation.lint_passed ? 'check' : 'exclamation-triangle'} text-${operation.lint_passed ? 'green' : 'yellow'}-500"></i>
            <span class="text-sm text-${operation.lint_passed ? 'green' : 'yellow'}-500">
                ${operation.lint_passed ? 'Linter passed' : 'Linter warnings'}
            </span>
        `;
        header.appendChild(linterStatus);
    }
    
    operationDiv.appendChild(header);

    // Operation content
    if (operation.type === 'edit_file' || operation.type === 'create_file') {
        // Show diff if available
        if (operation.diff) {
            const diffDiv = document.createElement('div');
            diffDiv.className = 'bg-gray-900 rounded-lg p-4 font-mono text-sm whitespace-pre overflow-x-auto';
            
            const lines = operation.diff.split('\n');
            const filteredLines = lines.filter((line, index) => line !== '' || index !== lines.length - 1);
            const formattedLines = filteredLines.map(line => {
                if (line.startsWith('---')) {
                    return `<span class="text-red-500">${escapeHtml(line)}</span>`;
                }
                if (line.startsWith('+++')) {
                    return `<span class="text-green-500">${escapeHtml(line)}</span>`;
                }
                if (line.startsWith('+')) {
                    return `<span class="text-green-500">${escapeHtml(line)}</span>`;
                }
                if (line.startsWith('-')) {
                    return `<span class="text-red-500">${escapeHtml(line)}</span>`;
                }
                if (line.startsWith('@@')) {
                    return `<span class="text-blue-500">${escapeHtml(line)}</span>`;
                }
                return `<span class="text-gray-400">${escapeHtml(line)}</span>`;
            });
            
            diffDiv.innerHTML = formattedLines.join('\n');
            operationDiv.appendChild(diffDiv);
        }
        
        // Show lint output if available
        if (operation.lint_output && !operation.lint_passed) {
            const lintDiv = document.createElement('div');
            lintDiv.className = 'mt-4 bg-gray-900 rounded-lg p-4 font-mono text-sm whitespace-pre overflow-x-auto text-yellow-500';
            lintDiv.textContent = operation.lint_output;
            operationDiv.appendChild(lintDiv);
        }
    }
    
    container.appendChild(operationDiv);
}

function getOperationIcon(type) {
    const icons = {
        'create_file': 'fa-file-plus text-green-500',
        'edit_file': 'fa-file-edit text-blue-500',
        'remove_file': 'fa-file-minus text-red-500'
    };
    return icons[type] || 'fa-file text-gray-500';
}

function formatOperationTitle(operation) {
    return `${operation.type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}: ${operation.path}`;
}

function appendModalButtons(footer, operations) {
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn btn-secondary';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.onclick = hideModal;

    const applyBtn = document.createElement('button');
    applyBtn.className = 'btn btn-primary';
    applyBtn.innerHTML = '<i class="fas fa-check mr-2"></i>Apply Changes';
    applyBtn.onclick = () => applyChanges(operations);

    footer.appendChild(cancelBtn);
    footer.appendChild(applyBtn);
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Utility Functions
function showLoading(message = 'Processing...') {
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    loadingOverlay.classList.remove('hidden');
    loadingText.textContent = message;
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

function hideModal() {
    document.getElementById('approvalModal').classList.add('hidden');
    
    // Clear status message
    const statusContainer = document.getElementById('statusContainer');
    if (statusContainer) {
        statusContainer.remove();
    }
    
    // Clear progress message
    const progressContainer = document.getElementById('progressContainer');
    if (progressContainer) {
        progressContainer.remove();
    }
}

function showError(message, type = 'error') {
    // Remove any existing notifications
    const existingNotification = document.getElementById('notification');
    if (existingNotification) {
        existingNotification.remove();
    }

    // Create notification element
    const notification = document.createElement('div');
    notification.id = 'notification';
    notification.className = `fixed bottom-4 right-4 p-4 rounded-lg shadow-lg z-50 ${
        type === 'success' ? 'bg-green-500' : 'bg-red-500'
    } text-white`;
    
    notification.innerHTML = `
        <div class="flex items-center gap-2">
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
            <span>${message}</span>
        </div>
    `;

    // Add to document
    document.body.appendChild(notification);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

function validateWorkspace() {
    if (!currentWorkspace) {
        showError('Please create or select a workspace first');
        return false;
    }
    return true;
}

function getLanguageMode(filePath) {
    const ext = filePath.split('.').pop().toLowerCase();
    const modeMap = {
        'js': 'javascript',
        'py': 'python',
        'html': 'xml',
        'css': 'css',
        'json': 'javascript',
        'md': 'markdown',
        'yaml': 'yaml',
        'yml': 'yaml'
    };
    return modeMap[ext] || 'plaintext';
}

async function applyChanges(operations) {
    showLoading('Applying changes...');
    hideModal();

    try {
        const response = await fetch('/apply_changes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_dir: currentWorkspace,
                operations: operations
            })
        });

        const data = await response.json();
        
        if (data.status === 'success') {
            if (data.structure) {
                updateWorkspaceTree(data.structure);
            }
            showError('Changes applied successfully', 'success');
        } else {
            showError(data.message || 'Failed to apply changes');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to apply changes: ' + error.message);
    } finally {
        hideLoading();
    }
}

// File Viewing
async function showFileContent(filePath) {
    const modal = document.getElementById('approvalModal');
    const preview = document.getElementById('changesPreview');
    const modalTitle = modal.querySelector('.modal-header h2');
    const modalFooter = document.getElementById('modalFooter');

    modalTitle.textContent = filePath.split('/').pop();
    preview.innerHTML = '<div class="text-center p-4"><i class="fas fa-spinner fa-spin mr-2"></i>Loading file...</div>';
    modalFooter.innerHTML = '';
    modal.classList.remove('hidden');

    try {
        // Ensure we're using a clean relative path
        const relativePath = filePath.replace(/^[\/\\]+/, '');
            
        console.log('Current workspace:', currentWorkspace);  // Debug log
        console.log('Original file path:', filePath);  // Debug log
        console.log('Relative path:', relativePath);  // Debug log

        const response = await fetch('/workspace/file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_dir: currentWorkspace,
                file_path: relativePath
            })
        });

        const data = await response.json();
        console.log('File content response:', data);  // Debug log
        
        if (data.status === 'success') {
            // Clear previous content
            preview.innerHTML = '';

            // Create the main container
            const container = document.createElement('div');
            container.className = 'file-preview-container h-full flex flex-col';
            
            // File info header
            const fileInfo = document.createElement('div');
            fileInfo.className = 'file-info-header mb-4 p-4 bg-gray-700 rounded-lg';
            
            // Handle file size display
            const fileSize = formatFileSize(data.file_size);
            console.log('File size:', data.file_size, 'Formatted:', fileSize);  // Debug log
            
            const fileSizeDisplay = data.truncated 
                ? `<p class="text-yellow-400 text-sm mt-1">File is large (${fileSize}). Showing preview of first 1000 lines.</p>` 
                : `<p class="text-gray-400 text-sm mt-1">File size: ${fileSize}</p>`;
            
            fileInfo.innerHTML = `
                <div class="flex items-center gap-3">
                    <i class="fas ${getFileIcon(filePath)}"></i>
                    <div class="flex-1">
                        <div class="flex items-center gap-2">
                            <h3 class="text-lg font-medium">${filePath.split('/').pop()}</h3>
                        </div>
                        <p class="text-sm text-gray-400">${relativePath}</p>
                        ${fileSizeDisplay}
                    </div>
                </div>
            `;
            container.appendChild(fileInfo);

            // File content container
            const contentContainer = document.createElement('div');
            contentContainer.className = 'file-content-container flex-1 bg-gray-800 rounded-lg overflow-hidden';
            contentContainer.style.minHeight = '400px';
            
            // Create editor container
            const editorDiv = document.createElement('div');
            editorDiv.className = 'h-full';
            editorDiv.style.minHeight = '400px';
            
            // Create textarea with content
            const textarea = document.createElement('textarea');
            if (data.content !== undefined && data.content !== null) {
                textarea.value = data.content.replace(/\n$/, '');  // Remove trailing newline if present
                console.log('Content length:', data.content.length);  // Debug log
            } else {
                console.warn('No content received from server');  // Debug log
                textarea.value = '';
            }
            
            editorDiv.appendChild(textarea);
            contentContainer.appendChild(editorDiv);
            container.appendChild(contentContainer);
            
            preview.appendChild(container);

            // Initialize CodeMirror with specific height
            const editor = CodeMirror.fromTextArea(textarea, {
                mode: getLanguageMode(filePath),
                theme: 'monokai',
                lineNumbers: true,
                matchBrackets: true,
                styleActiveLine: true,
                readOnly: true,
                scrollbarStyle: 'overlay',
                lineWrapping: true,
                viewportMargin: Infinity,
                lineSeparator: '\n',
                smartIndent: false,
                electricChars: false,
                extraKeys: null
            });

            // Set editor size and force refresh
            editor.setSize('100%', '400px');
            editor.refresh();  // Immediate refresh
            setTimeout(() => {
                editor.refresh();  // Additional refresh after a short delay
                console.log('Editor refreshed');  // Debug log
            }, 100);

            // Add close button to footer
            const closeBtn = document.createElement('button');
            closeBtn.className = 'btn btn-secondary';
            closeBtn.innerHTML = '<i class="fas fa-times mr-2"></i>Close';
            closeBtn.onclick = hideModal;
            modalFooter.appendChild(closeBtn);
        } else {
            console.error('Error response:', data.message);  // Debug log
            preview.innerHTML = `<div class="text-center text-red-500 p-4">Failed to load file content: ${data.message || 'Unknown error'}</div>`;
        }
    } catch (error) {
        console.error('Error:', error);
        preview.innerHTML = `<div class="text-center text-red-500 p-4">Error loading file: ${error.message}</div>`;
    }
}

function formatFileSize(bytes) {
    if (bytes === undefined || bytes === null || bytes === 0) {
        return 'Empty file';
    }
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = Math.abs(bytes);  // Ensure positive number
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

// Keyboard Shortcuts
function initializeKeyboardShortcuts() {
    // Code generation shortcut
    const promptInput = document.getElementById('promptInput');
    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            processPrompt();
        }
    });

    // Chat shortcut
    const chatInput = document.getElementById('chatInput');
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            sendChatMessage();
        }
    });
}

// File attachment handling
async function handleFileAttachment(fileInput, attachmentsContainer) {
    const files = Array.from(fileInput.files);
    attachmentsContainer.innerHTML = '';
    
    for (const file of files) {
        try {
            const content = await extractFileContent(file);
            if (content) {
                addAttachmentToContainer(file.name, content, attachmentsContainer, getFileType(file));
            }
        } catch (error) {
            console.error('Error processing file:', error);
            showError(`Error processing ${file.name}: ${error.message}`);
        }
    }
}

async function extractFileContent(file) {
    const reader = new FileReader();

    // Helper function to wrap FileReader in a promise
    const readFile = (method) => {
        return new Promise((resolve, reject) => {
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.onload = () => resolve(reader.result);
            method.call(reader, file);
        });
    };

    try {
        switch (true) {
            // PDF Files
            case file.type === 'application/pdf':
                const arrayBuffer = await readFile(reader.readAsArrayBuffer);
                const pdf = await pdfjsLib.getDocument(new Uint8Array(arrayBuffer)).promise;
                let pdfText = '';
                for (let i = 1; i <= pdf.numPages; i++) {
                    const page = await pdf.getPage(i);
                    const textContent = await page.getTextContent();
                    pdfText += textContent.items.map(item => item.str).join(' ') + '\n';
                }
                return pdfText;

            // Word Documents
            case file.type.includes('word') || file.type.includes('openxmlformats-officedocument.wordprocessingml'):
                const docArrayBuffer = await readFile(reader.readAsArrayBuffer);
                const result = await mammoth.extractRawText({ arrayBuffer: docArrayBuffer });
                return result.value;

            // Excel Files
            case file.type.includes('excel') || file.type.includes('spreadsheetml'):
                const excelData = await readFile(reader.readAsArrayBuffer);
                const workbook = XLSX.read(excelData, { type: 'array' });
                let excelText = '';
                workbook.SheetNames.forEach(sheetName => {
                    const sheet = workbook.Sheets[sheetName];
                    excelText += `Sheet: ${sheetName}\n${XLSX.utils.sheet_to_string(sheet)}\n\n`;
                });
                return excelText;

            // Images (OCR)
            case file.type.startsWith('image/'):
                const imageUrl = await readFile(reader.readAsDataURL);
                const worker = await Tesseract.createWorker('eng');
                const { data: { text } } = await worker.recognize(imageUrl);
                await worker.terminate();
                return text;

            // Markdown (Enhanced)
            case file.name.endsWith('.md'):
                const mdContent = await readFile(reader.readAsText);
                const parsed = marked.parse(mdContent, {
                    gfm: true,
                    breaks: true,
                    headerIds: false
                });
                // Strip HTML tags for context
                return parsed.replace(/<[^>]*>/g, ' ');

            // Text and Code Files
            case file.type.startsWith('text/') || 
                 file.type === 'application/json' ||
                 file.name.match(/\.(txt|js|py|java|c|cpp|h|hpp|cs|html|css|json|yml|yaml|xml|sql|sh|bash|r|rb|php|go|rust|swift)$/i):
                return await readFile(reader.readAsText);

            // Default: Try as text
            default:
                if (file.size > 10 * 1024 * 1024) { // 10MB limit for unknown files
                    throw new Error('File too large for unknown type');
                }
                return await readFile(reader.readAsText);
        }
    } catch (error) {
        throw new Error(`Failed to process ${file.name}: ${error.message}`);
    }
}

function getFileType(file) {
    if (file.type === 'application/pdf') return 'pdf';
    if (file.type.includes('word')) return 'word';
    if (file.type.includes('excel')) return 'excel';
    if (file.type.startsWith('image/')) return 'image';
    if (file.name.endsWith('.md')) return 'markdown';
    return 'text';
}

function addAttachmentToContainer(fileName, content, container, type) {
    const fileDiv = document.createElement('div');
    fileDiv.className = 'flex items-center justify-between bg-gray-700 p-2 rounded mb-2';
    fileDiv.dataset.content = content;
    
    const iconMap = {
        'pdf': 'fa-file-pdf text-red-500',
        'word': 'fa-file-word text-blue-500',
        'excel': 'fa-file-excel text-green-500',
        'image': 'fa-file-image text-purple-500',
        'markdown': 'fa-file-alt text-blue-400',
        'text': 'fa-file-code text-blue-500'
    };
    
    const iconClass = iconMap[type] || 'fa-file text-gray-500';
    
    fileDiv.innerHTML = `
        <div class="flex items-center gap-2">
            <i class="fas ${iconClass}"></i>
            <span class="text-sm">${fileName}</span>
            <span class="text-xs text-gray-400">(${formatFileSize(new Blob([content]).size)})</span>
        </div>
        <div class="flex items-center gap-2">
            <button onclick="previewAttachment(this.parentElement.parentElement)" class="text-gray-400 hover:text-blue-500" title="Preview">
                <i class="fas fa-eye"></i>
            </button>
            <button onclick="this.parentElement.parentElement.remove()" class="text-gray-400 hover:text-red-500" title="Remove">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    container.appendChild(fileDiv);
}

function formatFileSize(bytes) {
    if (bytes === undefined || bytes === null || bytes === 0) {
        return 'Empty file';
    }
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = Math.abs(bytes);  // Ensure positive number
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

function previewAttachment(attachmentDiv) {
    const fileName = attachmentDiv.querySelector('span').textContent;
    const content = attachmentDiv.dataset.content;
    
    const modal = document.getElementById('approvalModal');
    const preview = document.getElementById('changesPreview');
    const modalTitle = modal.querySelector('.modal-header h2');
    const footer = modal.querySelector('.modal-footer .flex');
    
    modalTitle.textContent = `Preview: ${fileName}`;
    preview.innerHTML = '';
    footer.innerHTML = '';
    
    const previewContent = document.createElement('div');
    previewContent.className = 'bg-gray-900 p-4 rounded-lg';
    
    if (fileName.endsWith('.pdf')) {
        // Format PDF content for readability
        const formattedContent = content
            .split('\n')
            .filter(line => line.trim())
            .join('\n\n');
        previewContent.innerHTML = `<pre class="whitespace-pre-wrap font-mono text-sm">${formattedContent}</pre>`;
    } else {
        // For text files, use CodeMirror
        const editorDiv = document.createElement('div');
        editorDiv.style.height = '500px';
        
        const textarea = document.createElement('textarea');
        textarea.value = content;
        previewContent.appendChild(textarea);
        
        CodeMirror.fromTextArea(textarea, {
            mode: getLanguageMode(fileName),
            theme: 'monokai',
            lineNumbers: true,
            readOnly: true,
            viewportMargin: Infinity
        });
    }
    
    preview.appendChild(previewContent);
    
    const closeBtn = document.createElement('button');
    closeBtn.className = 'btn btn-secondary';
    closeBtn.textContent = 'Close';
    closeBtn.onclick = hideModal;
    footer.appendChild(closeBtn);
    
    modal.classList.remove('hidden');
}

// Add event listeners for file inputs
document.getElementById('codeAttachment').addEventListener('change', function() {
    handleFileAttachment(this, document.getElementById('codeAttachments'));
});

document.getElementById('chatAttachment').addEventListener('change', function() {
    handleFileAttachment(this, document.getElementById('chatAttachments'));
});

async function importFolder() {
    await showFolderBrowser();
}

async function showFolderBrowser(path = null) {
    try {
        const modal = document.getElementById('approvalModal');
        const modalTitle = document.getElementById('modalTitle');
        const preview = document.getElementById('changesPreview');
        const footer = document.getElementById('modalFooter');
        
        if (!modal || !modalTitle || !preview || !footer) {
            throw new Error('Modal elements not found');
        }

        showLoading('Loading folders...');
        const response = await fetch(`/available-folders${path ? `?path=${encodeURIComponent(path)}` : ''}`);
        const data = await response.json();
        
        if (data.status !== 'success') {
            throw new Error(data.message || 'Failed to load folders');
        }
        
        modalTitle.textContent = 'Browse Folders';
        preview.innerHTML = `
            <div class="p-4 mb-4 bg-blue-900 bg-opacity-20 rounded-lg">
                <p class="text-sm text-blue-300">
                    <i class="fas fa-info-circle mr-2"></i>
                    Browse to find a folder to import. Click on any folder to navigate into it, or click "Import" when you find the folder you want.
                </p>
            </div>
            <div class="px-4 py-2 bg-gray-800 rounded-lg mb-4 flex items-center gap-2 text-sm">
                <i class="fas fa-folder-open text-blue-400"></i>
                <span class="text-gray-300">${data.current_path}</span>
            </div>
        `;
        footer.innerHTML = '';
        
        // Create folder list
        const folderList = document.createElement('div');
        folderList.className = 'grid grid-cols-1 gap-2';
        
        // Add parent directory navigation if available
        if (data.parent_path) {
            const parentDiv = document.createElement('div');
            parentDiv.className = 'flex items-center p-3 bg-gray-700 rounded-lg hover:bg-gray-600 cursor-pointer transition-colors';
            parentDiv.onclick = () => showFolderBrowser(data.parent_path);
            parentDiv.innerHTML = `
                <div class="flex items-center gap-2">
                    <i class="fas fa-level-up-alt text-gray-400"></i>
                    <span class="font-medium text-gray-300">Parent Directory</span>
                </div>
            `;
            folderList.appendChild(parentDiv);
        }
        
        // Add folders
        data.items.forEach(item => {
            const folderDiv = document.createElement('div');
            folderDiv.className = 'flex items-center justify-between p-3 bg-gray-700 rounded-lg hover:bg-gray-600 cursor-pointer transition-colors';
            
            // Make all folders navigable
            folderDiv.onclick = () => showFolderBrowser(item.path);
            
            const info = document.createElement('div');
            info.className = 'flex-1';
            
            let details = '';
            if (item.is_importable) {
                details = `
                    <div class="text-sm text-gray-400 mt-1">
                        ${item.files} files · ${formatFileSize(item.size)} · 
                        Modified: ${new Date(item.modified * 1000).toLocaleString()}
                    </div>
                `;
            }
            
            info.innerHTML = `
                <div class="flex items-center gap-2">
                    <i class="fas fa-folder${item.is_importable ? '' : '-open'} text-${item.is_importable ? 'blue' : 'gray'}-400"></i>
                    <span class="font-medium text-gray-300">${item.name}</span>
                </div>
                ${details}
            `;
            
            folderDiv.appendChild(info);
            
            // Add import button for importable folders
            if (item.is_importable) {
                const importBtn = document.createElement('button');
                importBtn.className = 'btn btn-primary btn-sm ml-4';
                importBtn.innerHTML = '<i class="fas fa-download mr-1"></i> Import';
                importBtn.onclick = (e) => {
                    e.stopPropagation();  // Prevent folder navigation
                    selectFolderToImport({ ...item, path: item.path });
                };
                folderDiv.appendChild(importBtn);
            } else {
                // Add navigation arrow for all folders
                const arrow = document.createElement('div');
                arrow.innerHTML = '<i class="fas fa-chevron-right text-gray-400"></i>';
                folderDiv.appendChild(arrow);
            }
            
            folderList.appendChild(folderDiv);
        });
        
        preview.appendChild(folderList);
        
        // Add close button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'btn btn-secondary';
        closeBtn.textContent = 'Cancel';
        closeBtn.onclick = hideModal;
        footer.appendChild(closeBtn);
        
        modal.classList.remove('hidden');
    } catch (error) {
        console.error('Error in showFolderBrowser:', error);
        showError(error.message);
    } finally {
        hideLoading();
    }
}

async function selectFolderToImport(folder) {
    try {
        hideModal(); // Hide modal first
        showLoading('Importing folder as workspace...');
        
        const response = await fetch('/workspace/import-folder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                path: folder.path
            })
        });
        
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Failed to import folder');
        }
        
        // First update workspace info
        currentWorkspace = data.workspace_dir;
        
        // Then update the workspace history to ensure all elements are created
        await loadWorkspaceHistory();
        
        // Now update the current workspace info and tree
        const workspaceInfo = document.getElementById('currentWorkspaceInfo');
        if (workspaceInfo) {
            workspaceInfo.classList.remove('hidden');
        }
        
        const workspaceName = document.getElementById('currentWorkspaceName');
        if (workspaceName) {
            workspaceName.textContent = data.workspace_id;
        }
        
        const workspaceTree = document.getElementById('workspaceTree');
        if (workspaceTree) {
            updateWorkspaceTree(data.structure);
        }
        
        showError('Folder imported successfully', 'success');
    } catch (error) {
        console.error('Error importing folder:', error);
        showError(error.message);
    } finally {
        hideLoading();
    }
} 