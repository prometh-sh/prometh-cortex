# Changelog

All notable changes to Prometh Cortex will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2025-12-19

### Added
- **Unified Collection Architecture**: Single FAISS/Qdrant index replacing multi-collection model for better semantic search
- **Per-Source Chunking**: Different chunk sizes and overlaps per source while maintaining unified index
- **Source-Based Routing**: Intelligent document routing with longest-prefix-match algorithm
- **Source Type Filtering**: Optional `source_type` parameter for filtering results by document source
- **Document Metadata**: Enhanced metadata tracking with source type information
- **CLI Source Management**: New `pcortex sources` command replacing `pcortex collections`
- **MCP Tool Updates**: Renamed `prometh_cortex_list_collections` to `prometh_cortex_list_sources`
- **HTTP API Updates**: Renamed `/prometh_cortex_collections` to `/prometh_cortex_sources`
- **Comprehensive Documentation**: v0.3.0 architecture spec and v0.2→v0.3 migration guide

### Changed
- **Architecture**: Refactored from multi-collection to unified collection with per-source chunking
- **Configuration Format**: Changed from `[[collections]]` with chunk params to `[[collections]]` + `[[sources]]`
- **Query Performance**: Improved from ~500ms (3-collection queries) to ~300ms (unified index)
- **Memory Usage**: Reduced by ~66% with single index instead of multiple collection indexes
- **Router Return Type**: DocumentRouter now returns `(source_name, chunk_size, chunk_overlap)` tuple
- **MCP API**: Query parameter `collection` → `source_type`
- **HTTP API**: Query parameter `collection` → `source_type`
- **PROMETH.md**: Updated with v0.3.0 status, implementation phases, and architecture evolution

### Deprecated
- v0.2.0 Multi-Collection architecture (superseded by v0.3.0)
- `pcortex collections` command (replaced by `pcortex sources`)
- `prometh_cortex_list_collections` MCP tool (replaced by `prometh_cortex_list_sources`)
- `/prometh_cortex_collections` HTTP endpoint (replaced by `/prometh_cortex_sources`)

### Fixed
- DocumentChangeDetector metadata updates for incremental indexing
- QdrantVectorStore interface compliance with save_index method

### Migration
- See `docs/migration-v0.2-to-v0.3.md` for detailed upgrade instructions
- Backward compatibility: RAG_COLLECTIONS env var automatically mapped to RAG_SOURCES

## [0.1.3] - 2025-10-13

### Added
- `pcortex --version` flag to display package version

### Fixed
- Config commands (`--init`, `--show-paths`) now work without existing config file
- Improved first-time user experience after `pip install prometh-cortex`
- Better error messages suggesting `pcortex config --init` for setup

### Changed
- Simplified release workflow (removed test requirements for faster releases)

## [0.1.2] - 2025-11-05

### Added
- XDG Base Directory Specification support for config file locations
- `pcortex config --init` command to initialize user config directory
- `pcortex config --show-paths` command to display config search paths
- Config file search now includes `~/.config/prometh-cortex/config.toml` (XDG standard)

### Changed
- Improved config file discovery with XDG-compliant paths
- Enhanced `pcortex config` command with multiple options
- Updated Quick Start guide in README with better installation instructions

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
- **BREAKING**: Minimum Python version updated from 3.9 to 3.10 (required by fastmcp dependency)

### Fixed
- Security: Prevented PyPI credentials from being committed to repository
- CI/CD: Fixed Python version compatibility for fastmcp dependency

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
