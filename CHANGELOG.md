# Changelog

All notable changes to the Lidarr Music Importer project will be documented in this file.

## [2.0.0] - 2025-11-08

### 🎉 Major Reorganization
- **Project Structure**: Complete reorganization into dedicated project folder
- **Documentation**: Comprehensive README and usage guides
- **Setup Tools**: Added setup script and requirements management

### ✨ Added
- Professional project structure with organized folders
- `setup.py` for easy installation and configuration
- `requirements.txt` for dependency management
- `config.template.py` for configuration management
- Comprehensive documentation in `docs/USAGE_AND_PRODUCTION.md`
- Example files and templates

### 🔧 Improved
- **Code Documentation**: Added comprehensive docstrings and comments to all functions
- **User Interface**: Enhanced command-line help with usage examples
- **Error Handling**: Better error messages and troubleshooting guidance
- **Progress Reporting**: Cleaner output with structured summaries

### 📝 Documentation
- Complete rewrite of README with professional formatting
- Added troubleshooting section for common issues
- Usage examples for various scenarios
- Configuration guidance with Lidarr UI references

## [1.5.0] - 2025-11-08

### 🚀 Feature Enhancement
- **Removed Legacy Modes**: Eliminated `add_artist` mode, focusing purely on selective album monitoring
- **Simplified Workflow**: Streamlined processing to only monitor specific albums
- **Code Cleanup**: Removed unused functions and simplified logic flow

### 🔧 Technical Improvements
- Consolidated artist addition logic into main processing function
- Improved status code management (removed `artist_added` and `artist_exists`)
- Enhanced retry logic and error handling

## [1.4.0] - 2025-11-07

### ✨ Added
- **Progress Tracking**: CSV status column for resumable imports
- **Batch Processing**: Configurable batch sizes with pauses to prevent API overload
- **Skip Completed**: Resume functionality for interrupted large imports
- **Enhanced Logging**: Detailed status reporting and processing summaries

### 🔧 Improved
- **Retry Logic**: Exponential backoff for API reliability
- **Album Matching**: Fuzzy matching for album title variations
- **Status Codes**: Comprehensive status tracking system

## [1.3.0] - 2025-11-06

### ✨ Added
- **Spotify Data Processing**: `parse_spotify_for_lidarr.py` for filtering Spotify exports
- **Connection Testing**: `test_lidarr_connection.py` utility
- **Data Analysis**: Statistical analysis of Spotify listening patterns

### 🔧 Improved
- **Data Filtering**: Intelligent filtering based on listening frequency
- **CSV Handling**: Better support for various CSV formats

## [1.2.0] - 2025-11-05

### ✨ Added
- **Album-Specific Monitoring**: Focus on selective album imports
- **Dual Mode Support**: Both artist addition and album-specific modes
- **Configuration Management**: Centralized configuration constants

### 🔧 Improved
- **API Integration**: Enhanced Lidarr API interaction
- **Error Handling**: Better exception management and logging

## [1.1.0] - 2025-11-04

### ✨ Added
- **MusicBrainz Integration**: Metadata lookup capabilities
- **Artist Management**: Automated artist addition to Lidarr
- **Basic CSV Processing**: Support for artist/album pair imports

### 🔧 Improved
- **API Reliability**: Basic retry logic for failed requests

## [1.0.0] - 2025-11-03

### 🎉 Initial Release
- **Core Functionality**: Basic script for adding artists to Lidarr
- **CSV Support**: Simple CSV processing for artist lists
- **API Integration**: Basic Lidarr API communication

---

## Version Notes

### Version Format
This project uses [Semantic Versioning](https://semver.org/):
- **MAJOR**: Incompatible API changes or major reorganization
- **MINOR**: New functionality in a backward-compatible manner  
- **PATCH**: Backward-compatible bug fixes

### Categories
- 🎉 **Major**: Significant new features or changes
- ✨ **Added**: New features and capabilities
- 🔧 **Improved**: Enhancements to existing functionality
- 🐛 **Fixed**: Bug fixes and error corrections
- 📝 **Documentation**: Documentation improvements
- 🚫 **Removed**: Removed features or deprecated functionality

---

For upcoming features and known issues, see the project's issue tracker.

## [2.0.1] - 2025-11-11

### 🔧 Release & Housekeeping
- Added packaging metadata and CI fixes so the project installs cleanly and tests run in GitHub Actions.
- Added a lightweight smoke test and migrated imports to the canonical `lib` package.
- Tidied `.gitignore` to avoid committing local virtualenv artifacts.

### 🚫 Removed
- Removed the top-level compatibility shim `text_utils.py`; imports should use `lib.text_utils`.

### 📝 Notes
- This is a non-breaking housekeeping release; most changes improve developer experience and CI reliability.

## [2.0.2] - 2025-11-12

### 📝 Documentation housekeeping
- Consolidated usage and production guides into `docs/USAGE_AND_PRODUCTION.md` to remove duplication and provide a single point of truth.
- Migrated enhanced MusicBrainz search documentation into `docs/UNIVERSAL_PARSER.md`.
- Added a one-page quickstart at `docs/QUICKSTART.md` for faster onboarding.
- Archived legacy docs into `docs/archive/` (historical copies kept) and added redirects in the top-level docs.

### 🔧 Notes
- These are documentation-only changes; no code or runtime behavior was changed.