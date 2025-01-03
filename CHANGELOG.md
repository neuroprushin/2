# Changelog

All notable changes to this project will be documented in this file.

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