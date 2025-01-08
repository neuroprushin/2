# Changelog

All notable changes to this project will be documented in this file.

## [0.0.9] - 2024-01-10

### Added
- New AI models:
  - Llama 3.3 70B Instruct
  - Gemini 2.0 Flash Thinking Experimental
- Enhanced model handling:
  - Better context length management
  - Improved error handling for Gemini responses
  - Automatic context truncation for large inputs
  - Streaming support optimization

### Changed
- Improved code suggestion system:
  - More robust JSON response parsing
  - Better handling of markdown code blocks
  - Enhanced error recovery for model responses
- Optimized file handling:
  - Removed unused imports
  - Consolidated duplicate functions
  - Improved code organization

### Fixed
- Model response handling for Gemini
- Context length issues with large files
- JSON parsing for code suggestions
- Import statement cleanup

## [0.0.8] - 2024-01-09

### Added
- AI-Powered Analysis functionality:
  - Code pattern recognition and suggestions
  - Best practices recommendations
  - Dependency analysis and visualization
  - Performance optimization tips
  - Security vulnerability scanning
  - Code quality assessment

### Enhanced
- Large codebase support:
  - Efficient handling of large directories
  - Paginated directory browsing
  - Lazy loading of folder contents
  - Memory-optimized file tree
  - Progress indicators for large operations

### Fixed
- Directory path handling in workspace manager
- File tree expansion and navigation
- Error handling for invalid directories

## [0.0.7] - 2024-01-08

### Changed
- Updated model lineup:
  - Removed Codestral Mamba model
  - Optimized model configurations
  - Streamlined API integrations

### Fixed
- Model selection and configuration handling
- API key validation for remaining models
- Documentation consistency

## [0.0.6] - 2024-01-07

### Added
- Folder import functionality:
  - Import existing project folders as workspaces
  - Symlink support for efficient storage
  - Automatic workspace naming from folder
  - Import status tracking
- Enhanced file management:
  - File renaming within workspaces
  - Improved file path validation
  - Better directory structure handling

### Changed
- Improved workspace management:
  - Better handling of imported workspaces
  - Enhanced file system operations
  - More robust path validation
- Enhanced security measures:
  - Stricter file path validation
  - Improved symlink handling
  - Better error handling for file operations

## [0.0.5] - 2024-01-06

### Added
- New modern UI design inspired by Cursor IDE:
  - Bubble-style panels for workspace, chat, and main content
  - Centered logo and title placement
  - Improved spacing and layout consistency
  - Enhanced visual hierarchy
- Improved chat interface:
  - Fixed height chat input area
  - Better message spacing
  - Cleaner bubble design
- Enhanced workspace panel:
  - Centralized workspace controls
  - Better organized file tree
  - Improved model selection dropdown
- Updated copyright notice with special thanks

### Changed
- Adjusted panel widths for better usability
- Improved spacing between elements
- Enhanced button styles and hover effects
- Refined color scheme and borders
- Reorganized layout structure for better visual flow

## [0.0.4] - 2024-01-05

### Added
- New modern UI design inspired by Cursor IDE:
  - Bubble-style panels for workspace, chat, and main content
  - Centered logo and title placement
  - Improved spacing and layout consistency
  - Enhanced visual hierarchy
- Improved chat interface:
  - Fixed height chat input area
  - Better message spacing
  - Cleaner bubble design
- Enhanced workspace panel:
  - Centralized workspace controls
  - Better organized file tree
  - Improved model selection dropdown
- Updated copyright notice with special thanks

### Changed
- Adjusted panel widths for better usability
- Improved spacing between elements
- Enhanced button styles and hover effects
- Refined color scheme and borders
- Reorganized layout structure for better visual flow

## [0.0.3] - 2024-01-04

### Added
- Comprehensive file attachment support:
  - PDF files with text extraction
  - Microsoft Word documents (.docx)
  - Excel spreadsheets with sheet parsing
  - Images with OCR capabilities
  - Enhanced Markdown with GFM support
  - All major programming languages
  - Configuration files
  - Text and documentation files
- File preview functionality:
  - Syntax highlighting for code files
  - Formatted view for PDFs
  - Spreadsheet formatting
  - Image text extraction preview
- File handling features:
  - Multiple file upload support
  - Progress indicators
  - File size display
  - Type-specific icons
  - Remove attachments
  - Preview button for each file
- Error handling and validation:
  - File type detection
  - Size limits for unknown files
  - Proper error messages
  - Loading indicators

### Removed
- Archive file support (ZIP, RAR, 7z)

## [0.0.2] - 2024-01-03

### Added
- WebSocket support using Flask-SocketIO and Eventlet
- Real-time notifications for code changes
- Automatic server restart when static files or templates change
- Cache busting for static assets
- Socket.IO client integration for real-time updates

### Changed
- Updated model lineup:
  - Added Qwen 2.5 Coder (32B model)
  - Removed Groq integration
- Improved workspace change notifications
- Enhanced real-time feedback for file modifications

### Fixed
- Static file reloading issues
- Template caching problems
- WebSocket connection stability
- Environment variable configuration for OpenRouter API

## [0.0.1] - Initial Release

### Added
- Multi-model AI support (DeepSeek, Grok, Claude)
- Workspace management system
- Code generation and modification
- Interactive chat interface
- SQLite-based history tracking
- File diff previews
- Basic static file serving 