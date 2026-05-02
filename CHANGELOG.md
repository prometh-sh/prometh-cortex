# Changelog

All notable changes to Prometh Cortex will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.3] - 2026-05-02

### Added
- **Memory Forget Command (v0.5.3)**: New `pcortex memory forget` CLI for selective deletion of memory documents with safety-first design
- **Memory List Command**: `pcortex memory list` CLI with filtering by creation date, project, and tags
- **Time Parser Utilities**: Support for relative (7d, 2w, 24h) and absolute (2026-03-01) time formats
- **Dry-Run Safety Feature**: `--dry-run` flag on all memory delete operations to preview before deletion
- **Project Payload Index**: Fixed Qdrant 400 Bad Request error by adding `project` keyword payload index

### Changed
- **Memory Operations CLI**: Refactored memory management into dedicated `memory` command group with `list` and `forget` subcommands
- **Test Safety**: All memory deletion tests refactored to use `--dry-run` for preview-only operations (no accidental deletions)
- **Version Bump**: Updated to v0.5.3 in pyproject.toml

### Fixed
- **Qdrant Project Filter**: Added missing `"project": PayloadSchemaType.KEYWORD` payload index, resolving 400 Bad Request errors when filtering memories by project
- **Expiry Filter Logic**: Corrected inverted expiry date filter to delete documents OLDER than specified date (not newer)
- **Memory List Display**: Fixed title column truncation by adding `min_width=50` to allow text wrapping

### Documentation
- Added comprehensive `pcortex memory list` and `pcortex memory forget` command examples to README.md
- Documented safety workflow: preview with `--dry-run`, review, then delete with `--confirm`
- Added filter options documentation: `--since`, `--expiry`, `--project`, `--tag`, `--id`, `--all`

### Safety & Protection
- ✅ Memory documents cannot be accidentally deleted without explicit `--dry-run` preview
- ✅ Confirmation prompt required by default (disable with `--confirm` for automation)
- ✅ Full ID display in memory list (no truncation) for accurate reference
- ✅ Dry-run mode enforced in all unit tests to prevent data loss

## [0.5.0] - 2026-04-20

### Added
- **Memory Tool (MCP)**: New `prometh_cortex_memory()` tool for capturing and storing session summaries, decisions, and patterns directly to the index without rebuilding
- **Memory Preservation on Force Rebuild**: Memories automatically survive `pcortex build --force` and `pcortex rebuild --confirm` via backend-specific strategies (FAISS sidecar JSON, Qdrant filter-based deletion)
- **Virtual Memory Source**: Auto-injected `prmth_memory` source for in-memory document storage with per-source chunk configuration
- **Automatic Deduplication**: Memory documents deduplicated by content hash (title + content = same document ID, idempotent)
- **Metadata-Rich Storage**: Support for tags, session IDs, project references, and custom metadata in memory documents
- **Immediate Queryability**: Memories available for search immediately after creation (no rebuild needed)
- **Dual Vector Store Support**: Memory preservation works seamlessly with both FAISS (local) and Qdrant (cloud) backends
- **Smart Metadata Retrieval**: Automatic handling of both parent document IDs and chunk IDs in memory documents

### Changed
- **Configuration Schema**: Added virtual `prmth_memory` source to default configuration (auto-injected)
- **Vector Store Interface**: Enhanced with `delete_documents_except_source()` for selective metadata clearing
- **Indexer API**: `add_memory_document()` method for direct memory storage with chunking and deduplication
- **MCP Tools**: Added `prometh_cortex_memory()` to available tools alongside query and health checks
- **pyproject.toml**: Updated version to 0.5.0 and GitHub URLs to prometh-sh organization

### Improved
- **Memory Workflow**: Session → Capture → Query → Force Rebuild → Preserved → Export workflow documented
- **Transport Selection**: Added comprehensive decision table and decision tree for choosing between stdio/sse/streamable-http
- **Documentation**: Complete v0.5.0 memory preservation specification and v0.4.0 → v0.5.0 migration guide

### Fixed
- Metadata persistence across index clear operations (both FAISS and Qdrant)
- Chunk ID tracking for accurate metadata retrieval in memory documents
- Virtual source pattern matching (`.prmth_memory` won't match real files)

### Migration
- See `docs/migration-v0.4-to-v0.5.md` for detailed upgrade instructions
- Backward compatible: existing v0.4.0 configs auto-inject `prmth_memory` source
- Memory tool optional: use only when needed for session capture workflows

## [0.4.0] - 2026-04-16

### Added
- **SSE Transport**: MCP server now supports Server-Sent Events transport via `pcortex mcp start --transport sse`, enabling persistent daemon mode with shared Qdrant connections across multiple clients
- **Streamable HTTP Transport**: Alternative HTTP-based MCP transport via `--transport streamable-http` for clients that support the newer MCP spec
- **OpenCode Config Generator**: New `pcortex mcp init opencode` target generates MCP configuration for OpenCode with correct JSON structure (`"mcp"` wrapper, array command, `"environment"` key)
- **SSE Client Config Generation**: All `pcortex mcp init` targets now accept `--transport sse` to generate lightweight SSE client configs (no executable path or env vars needed)
- **Custom SSE URL**: `pcortex mcp init <target> --transport sse --url http://host:port` for remote/Tailscale access
- **Transport CLI Options**: `pcortex mcp start` now accepts `--transport/-t`, `--host`, and `--port/-p` flags
- **MCP_TRANSPORT Config**: New `MCP_TRANSPORT` environment variable and TOML `[server] transport` setting

### Changed
- **`run_mcp_server()` Signature**: Now accepts `transport`, `host`, and `port` parameters (backward compatible, defaults to stdio)
- **Config Generator API**: All `generate_*_config()` functions accept `transport` and `url` keyword arguments

### Security
- **SSE/HTTP Auth Enforcement**: Bearer token authentication required on all non-stdio transports via `StaticBearerTokenVerifier`; server refuses to start without `MCP_AUTH_TOKEN` when using SSE or streamable-http
- **0.0.0.0 Binding Warning**: Runtime warning when binding to all interfaces on network transports
- **TOML Transport Validation**: `[server] transport` value now validated against allowlist (consistent with `MCP_TRANSPORT` env var)

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
