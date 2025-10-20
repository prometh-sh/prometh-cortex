# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Prometh-Cortex is a **fully implemented** local-first Multi-Collection RAG (Retrieval-Augmented Generation) Indexer with intelligent document routing and dual MCP/HTTP server integration (v0.2.0+). The system:

- **Automatically routes documents** from multiple datalake repositories to dedicated collections
- **Applies collection-specific configurations**: Different chunk sizes, overlaps, and embeddings per collection
- **Provides dual access methods**: MCP protocol for Claude Desktop + HTTP REST API for Perplexity/VSCode/web
- **Supports sophisticated querying**: Search specific collections or aggregate across all collections

## Architecture (v0.2.0+)

The system implements a complete multi-collection pipeline:

1. **Configuration Layer**: TOML/environment-based with collection definitions
2. **Document Router**: Intelligent pattern-based routing to collections
3. **Per-Collection Indexing**: Independent LlamaIndex + FAISS instances per collection
4. **Datalake Ingest & Parser**: YAML frontmatter extraction with collection metadata
5. **Query Engine**: Single or multi-collection search with result merging
6. **Dual Server Architecture**:
   - **MCP Protocol** (`pcortex mcp`): stdio-based for Claude Desktop integration
   - **HTTP REST API** (`pcortex serve`): FastAPI server for web/API integrations

## Project Structure

```
src/prometh_cortex/
├── cli/                    # CLI commands and main entry point
│   ├── commands/
│   │   ├── build.py       # Multi-collection index building
│   │   ├── query.py       # Collection-aware querying
│   │   ├── collections.py # NEW: Collection listing and management
│   │   ├── mcp.py         # MCP server startup
│   │   ├── rebuild.py     # Index rebuilding
│   │   └── serve.py       # HTTP server startup
│   └── main.py            # Main CLI entry point
├── config/
│   └── settings.py        # Configuration with CollectionConfig (NEW)
├── router/                # NEW: Document routing module
│   └── __init__.py       # DocumentRouter implementation
├── indexer/
│   └── document_indexer.py # Rewritten for multi-collection (v0.2.0+)
├── parser/                # Markdown/YAML parsing
├── mcp/
│   └── server.py         # Enhanced with collection support
├── server/
│   └── app.py            # Enhanced HTTP API with collection endpoints
└── utils/                # Utility functions
```

## Current Implementation Status

**✅ v0.2.0 - FULLY IMPLEMENTED AND PRODUCTION-READY:**

### Core Features (Phase 1-3 Complete)
- ✅ **Multi-Collection Configuration**: CollectionConfig with validation
- ✅ **Document Router**: Pattern-based intelligent routing to collections
- ✅ **Multi-Collection Indexer**: Independent FAISS instances per collection
- ✅ **Collection-Specific Chunking**: Per-collection chunk size and overlap
- ✅ **Complete CLI Interface**: build, query, collections, rebuild commands
- ✅ **Advanced Configuration**: TOML/env-based with multi-collection support
- ✅ **YAML Frontmatter Parser**: Complex schemas with collection metadata
- ✅ **Dual Server Architecture**: MCP protocol + HTTP REST API
- ✅ **Collection Management**: List, query, and manage multiple collections

### Production Capabilities (v0.2.0+)
- ✅ **Multi-Collection Indexing**: Automatic routing and independent indexes
- ✅ **Collections Support**: Up to N configurable collections per deployment
- ✅ **Fast Query Performance**: <300ms for single collection, <500ms for 3-5 collections
- ✅ **Cross-Collection Search**: Intelligent result merging by similarity
- ✅ **Robust Error Handling**: Comprehensive validation and error messages
- ✅ **Authentication**: Bearer token auth on all HTTP and MCP tools
- ✅ **Tested**: Unit tests, integration tests, and performance tests included

## Configuration

The system uses TOML files or environment variables with multi-collection support:

### Multi-Collection Configuration (v0.2.0+)

**TOML Format** (Recommended):
```toml
[datalake]
repos = ["/path/to/your/documents"]

[storage]
rag_index_dir = "/path/to/index/storage"

# Define collections with different chunking parameters
[[collections]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]  # Catch-all

[[collections]]
name = "knowledge_base"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["docs/specs", "docs/prds"]

[[collections]]
name = "meetings"
chunk_size = 256
chunk_overlap = 25
source_patterns = ["meetings"]
```

**Environment Variables**:
```bash
# Datalake configuration
export DATALAKE_REPOS='/path/to/your/documents'
export RAG_INDEX_DIR='/path/to/index/storage'

# Multi-collection configuration (JSON)
export RAG_COLLECTIONS='[
  {"name":"default","chunk_size":512,"chunk_overlap":50,"source_patterns":["*"]},
  {"name":"knowledge_base","chunk_size":512,"chunk_overlap":50,"source_patterns":["docs/specs"]},
  {"name":"meetings","chunk_size":256,"chunk_overlap":25,"source_patterns":["meetings"]}
]'

# Server configuration
export MCP_PORT=8080
export MCP_HOST=localhost
export MCP_AUTH_TOKEN=test-token-123

# Embedding settings
export EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
export MAX_QUERY_RESULTS=10
```

## Available CLI Commands

### Index Management
- `pcortex build` - Build indexes for all collections from datalakes
- `pcortex build --force` - Force rebuild all collections from scratch
- `pcortex rebuild` - Alias for `build --force`

### Query Interface
- `pcortex query "search text"` - Query all collections (default behavior)
- `pcortex query "search text" --collection knowledge_base` - Query specific collection
- `pcortex query "search text" -c meetings` - Shorthand for collection option

### Collection Management
- `pcortex collections` - List all available collections and statistics
- `pcortex collections -v` - Detailed collection information (verbose)

### Server Operations
- `pcortex mcp` - Start MCP protocol server (for Claude Desktop)
- `pcortex serve` - Start HTTP REST server (for Perplexity/VSCode/web)

### Configuration
- `pcortex config --sample` - Generate sample configuration
- `pcortex config --init` - Initialize user config directory
- `pcortex config --show-paths` - Show config file search paths

## Integration Status

### MCP Integration (Claude Desktop)
**Status: ✅ v0.2.0 - FULLY IMPLEMENTED WITH COLLECTION SUPPORT**
- **MCP Protocol Server**: Complete stdio-based implementation using FastMCP
- **MCP Tools Available**:
  - `prometh_cortex_query`: Search with optional collection parameter
  - `prometh_cortex_list_collections`: NEW - List all collections
  - `prometh_cortex_health`: System health with collection metrics
- **Multi-Collection Support**: Query single collection or aggregate across all
- **Configuration**: Ready for Claude Desktop integration

### HTTP REST API Integration
**Status: ✅ v0.2.0 - FULLY IMPLEMENTED WITH COLLECTION SUPPORT**
- **FastAPI Server**: Complete REST API with multi-collection support
- **Endpoints Available**:
  - `POST /prometh_cortex_query`: Search with optional collection parameter
  - `GET /prometh_cortex_collections`: NEW - List collections and statistics
  - `GET /prometh_cortex_health`: Health check with collection metrics
  - `GET /`: API info with features and version
- **Multi-Collection Support**: Filter by collection or search all
- **Authentication**: Bearer token protected on all endpoints
- **CORS**: Configured for web/VSCode integration

## Technical Implementation Details

### Dependencies
- **Core**: Click, Pydantic, python-dotenv, PyYAML
- **RAG Stack**: llama-index, faiss-cpu, sentence-transformers
- **MCP**: fastmcp (stdio protocol)
- **HTTP**: fastapi, uvicorn (REST API)
- **Parsing**: python-frontmatter, markdown

### Error Handling
- **Datetime Serialization**: Fixed JSON serialization issues
- **Pydantic V2 Compatibility**: Updated to modern Pydantic patterns
- **LlamaIndex Integration**: Resolved import and compatibility issues
- **Index Loading**: Robust index detection and loading

### Performance
- **Query Speed**: Achieving <300ms query times on 345 documents
- **Memory Efficient**: Optimized chunking and streaming
- **Scalable**: FAISS vector storage handles thousands of documents

## Known Issues & Solutions

### Claude Desktop MCP Integration
**Issue**: `spawn pcortex ENOENT 2` - Claude Desktop can't find pcortex command
**Solution**: Use full path in claude_desktop_config.json:
```json
{
  "mcpServers": {
    "prometh-cortex": {
      "command": "/full/path/to/pcortex",
      "args": ["mcp"],
      "env": {}
    }
  }
}
```

### Health Check Discrepancy
**Issue**: HTTP server health check shows incorrect vector store status
**Note**: This is a display bug only - query functionality works perfectly

## Development Guidelines

### Testing Commands
```bash
# Test index building
pcortex build --force

# Test querying
pcortex query "meeting" --max-results 5

# Test MCP server
pcortex mcp  # Run in separate terminal

# Test HTTP server
pcortex serve  # Run in separate terminal
curl -H "Authorization: Bearer test-token-123" \
     -H "Content-Type: application/json" \
     -d '{"query": "meetings", "max_results": 3}' \
     http://localhost:8080/prometh_cortex_query
```

### Code Quality
- **Error Handling**: Always wrap operations in try-catch blocks
- **Logging**: Use structured logging to stderr for MCP, rich console for CLI
- **Configuration**: All settings should be environment-configurable
- **Documentation**: Maintain comprehensive docstrings

## License

Apache 2.0 License
- Always don't use personal or private information in documents or sample configs, because my repos maybe will be public.