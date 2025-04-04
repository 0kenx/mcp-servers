# Changelog

All notable changes to the grammar parsers will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Advanced language-aware preprocessing**
  - New `LanguageAwarePreprocessor` for intelligent code fixing
  - Uses language-specific knowledge to make smart decisions
  - Structural analysis for detecting and fixing unlikely nesting patterns
  - Confidence scoring for applied fixes
  - Detailed diagnostics about preprocessing operations
  - Basic `IncompleteCodeHandler` as fallback for generic code fixing
  - Brace balancing to handle unmatched curly braces
  - Indentation fixing for languages with significant whitespace
  - Recovery of incomplete blocks at the end of files

- **Rich metadata extraction**
  - New `MetadataExtractor` classes for language-specific metadata extraction
  - Support for docstrings, decorators, type annotations, and other features
  - Language-specific extractors for Python, JavaScript/TypeScript, and C/C++
  - JSDoc parsing for JavaScript/TypeScript
  - Doxygen comment parsing for C/C++

- **Enhanced BaseParser functionality**
  - Option to enable/disable incomplete code handling
  - Tracking of code modifications during preprocessing
  - Integration of metadata extraction into the parsing process

### Changed

- Updated `CodeElement` class to better support metadata storage
- Modified Python parser to use the new metadata extraction system
- Refactored code to improve modularity and maintainability

### Fixed

- Improved handling of syntax errors in all parsers
- Better parsing of incomplete code fragments
- More robust docstring extraction

## [1.0.0] - Initial Release

- Basic parsing of complete, syntactically correct code
- Support for Python, JavaScript, TypeScript, Rust, and C/C++
- Identification of functions, classes, methods, variables, etc.
- Basic nested element support
