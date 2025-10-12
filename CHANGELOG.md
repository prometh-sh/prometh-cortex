# Changelog

All notable changes to Prometh Cortex will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2025-10-12

### Added
- Comprehensive CI/CD workflows with multi-OS testing (Ubuntu, macOS, Windows)
- GitHub Actions workflows for automated testing and PyPI publishing
- Coverage reporting with Codecov integration
- Build validation in CI pipeline

### Changed
- Updated README with PyPI installation badges and status indicators
- Improved README with table of contents and enhanced documentation
- Updated author email to prometh-cortex@prometh.sh
- Enhanced security by adding .pypirc to .gitignore

### Fixed
- Security: Prevented PyPI credentials from being committed to repository

## [0.1.0] - 2025-01-15

### Added
- Multi-datalake RAG indexer with YAML frontmatter parsing
- Dual vector store support (FAISS local and Qdrant cloud)
- MCP protocol server (`pcortex mcp`) for Claude Desktop integration
- HTTP REST server (`pcortex serve`) for web integrations (Perplexity, VSCode)
- CLI interface with commands: build, rebuild, query, mcp, serve, config
- Incremental indexing with smart change detection
- TOML-based configuration system
- Performance optimized for <100ms query times on M1/M2 Mac
- Comprehensive documentation with integration guides
- Support for complex YAML frontmatter schemas
- Authentication with bearer token for HTTP endpoints
- Health check endpoints for monitoring
- Rich console output for CLI operations
- Apache License 2.0

### Technical Implementation
- LlamaIndex integration for RAG workflows
- HuggingFace sentence-transformers for embeddings
- FastAPI HTTP server with CORS support
- FastMCP stdio protocol server
- Pydantic V2 models for configuration and data validation
- Click-based CLI with subcommands
- Python-frontmatter for Markdown parsing
