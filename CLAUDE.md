# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Prometh-Cortex is a **fully implemented** local-first Unified Collection RAG (Retrieval-Augmented Generation) Indexer with per-source chunking, intelligent document routing, and dual MCP/HTTP server integration (v0.3.0+). The system:

- **Automatically routes documents** from multiple datalake repositories to configured sources
- **Applies per-source chunking**: Different chunk sizes and overlaps per source in a unified index
- **Enables unified semantic search**: Single query across all document types with optimal performance
- **Provides dual access methods**: MCP protocol for Claude Desktop + HTTP REST API for Perplexity/VSCode/web
- **Preserves topic-based querying**: Find meetings, tasks, and specs together by topic in a single query

## Architecture (v0.3.0+)

The system implements a unified collection with per-source chunking pipeline:

1. **Configuration Layer**: TOML/environment-based with single collection + multiple sources
2. **Document Router**: Intelligent pattern-based routing to sources for chunking parameters
3. **Unified Indexing**: Single LlamaIndex + FAISS instance with per-document metadata
4. **Datalake Ingest & Parser**: YAML frontmatter extraction with source type metadata
5. **Query Engine**: Single unified semantic search with optional source filtering
6. **Dual Server Architecture**:
   - **MCP Protocol** (`pcortex mcp`): stdio-based for Claude Desktop integration
   - **HTTP REST API** (`pcortex serve`): FastAPI server for web/API integrations

## Project Structure

```
src/prometh_cortex/
├── cli/                    # CLI commands and main entry point
│   ├── commands/
│   │   ├── build.py       # Unified index building with per-source chunking
│   │   ├── query.py       # Unified query with optional source filtering
│   │   ├── sources.py     # Source listing and management (renamed from collections.py)
│   │   ├── mcp.py         # MCP server startup
│   │   ├── rebuild.py     # Index rebuilding
│   │   └── serve.py       # HTTP server startup
│   └── main.py            # Main CLI entry point
├── config/
│   └── settings.py        # SourceConfig + CollectionConfig (unified architecture)
├── router/                # Document routing for per-source chunking
│   └── __init__.py       # DocumentRouter returns (source_name, chunk_size, chunk_overlap)
├── indexer/
│   └── document_indexer.py # Refactored for unified collection (v0.3.0+)
├── parser/                # Markdown/YAML parsing
├── mcp/
│   └── server.py         # MCP tools with source_type parameter
├── server/
│   └── app.py            # HTTP API with source_type parameter
└── utils/                # Utility functions
```

## Current Implementation Status

**✅ v0.3.0 - FULLY IMPLEMENTED AND PRODUCTION-READY:**

### Core Features (All 7 Phases Complete)
- ✅ **Unified Collection Architecture**: Single FAISS index for all documents
- ✅ **Per-Source Chunking**: Different chunk sizes per source in unified index
- ✅ **Document Router**: Pattern-based routing that returns chunking parameters
- ✅ **Single Vector Store**: Unified LlamaIndex + FAISS instance with metadata filtering
- ✅ **Source-Specific Configuration**: SourceConfig with validation for per-source chunking
- ✅ **Complete CLI Interface**: build, query, sources (renamed from collections), rebuild commands
- ✅ **Advanced Configuration**: TOML/env-based with unified collection + sources support
- ✅ **YAML Frontmatter Parser**: Complex schemas with source type metadata
- ✅ **Dual Server Architecture**: MCP protocol + HTTP REST API (both updated for v0.3.0)
- ✅ **Source Management**: List, query, and manage document sources

### Production Capabilities (v0.3.0+)
- ✅ **Unified Indexing**: Single index with per-source chunking metadata
- ✅ **Sources Support**: Multiple configurable sources per collection
- ✅ **Fast Query Performance**: <300ms for unified queries (vs ~500ms for v0.2 multi-collection)
- ✅ **Semantic Cross-Type Search**: Topic-based queries work across document types
- ✅ **Source Filtering**: Optional `source_type` parameter for filtering results
- ✅ **Robust Error Handling**: Comprehensive validation and error messages
- ✅ **Authentication**: Bearer token auth on all HTTP and MCP tools
- ✅ **Backward Compatible**: v0.2 RAG_COLLECTIONS env var automatically mapped to RAG_SOURCES

## Configuration

The system uses TOML files or environment variables with unified collection + sources support:

### Unified Collection Configuration (v0.3.0+)

**TOML Format** (Recommended):
```toml
[datalake]
repos = ["/path/to/your/documents"]

[storage]
rag_index_dir = "/path/to/index/storage"

# Single unified collection
[[collections]]
name = "prometh_cortex"

# Document sources with per-source chunking
[[sources]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]  # Catch-all

[[sources]]
name = "knowledge_base"
chunk_size = 768
chunk_overlap = 76
source_patterns = ["docs/specs", "docs/prds"]

[[sources]]
name = "meetings"
chunk_size = 512
chunk_overlap = 51
source_patterns = ["meetings"]

[[sources]]
name = "todos"
chunk_size = 256
chunk_overlap = 26
source_patterns = ["todos", "reminders"]
```

**Environment Variables**:
```bash
# Datalake configuration
export DATALAKE_REPOS='/path/to/your/documents'
export RAG_INDEX_DIR='/path/to/index/storage'

# Document sources configuration (JSON)
export RAG_SOURCES='[
  {"name":"default","chunk_size":512,"chunk_overlap":50,"source_patterns":["*"]},
  {"name":"knowledge_base","chunk_size":768,"chunk_overlap":76,"source_patterns":["docs/specs","docs/prds"]},
  {"name":"meetings","chunk_size":512,"chunk_overlap":51,"source_patterns":["meetings"]},
  {"name":"todos","chunk_size":256,"chunk_overlap":26,"source_patterns":["todos","reminders"]}
]'

# Server configuration
export MCP_PORT=8080
export MCP_HOST=localhost
export MCP_AUTH_TOKEN=test-token-123

# Embedding settings
export EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
export MAX_QUERY_RESULTS=10
```

**Backward Compatibility**:
- v0.3.0 still supports the old `RAG_COLLECTIONS` env var (automatically mapped to `RAG_SOURCES`)
- TOML files using `[[collections]]` must be updated to `[[sources]]` (see migration guide)

## Available CLI Commands

### Index Management
- `pcortex build` - Build unified index with per-source chunking from datalakes
- `pcortex build --force` - Force rebuild unified index from scratch
- `pcortex rebuild` - Alias for `build --force`

### Query Interface
- `pcortex query "search text"` - Query unified index (default behavior, all sources)
- `pcortex query "search text" --source knowledge_base` - Filter results to specific source
- `pcortex query "search text" -s meetings` - Shorthand for source option
- `pcortex query "search text" --max-results 10` - Limit number of results

### Source Management
- `pcortex sources` - List all available sources and their statistics (v0.3.0+, renamed from collections)
- `pcortex sources -v` - Detailed source information including patterns and chunk sizes (verbose)

### Server Operations
- `pcortex mcp` - Start MCP protocol server (for Claude Desktop)
- `pcortex serve` - Start HTTP REST server (for Perplexity/VSCode/web)

### Configuration
- `pcortex config --sample` - Generate sample configuration
- `pcortex config --init` - Initialize user config directory
- `pcortex config --show-paths` - Show config file search paths

## Integration Status

### MCP Integration (Claude Desktop)
**Status: ✅ v0.3.0 - FULLY IMPLEMENTED WITH PER-SOURCE CHUNKING SUPPORT**
- **MCP Protocol Server**: Complete stdio-based implementation using FastMCP
- **MCP Tools Available**:
  - `prometh_cortex_query`: Search unified index with optional `source_type` filter (v0.3.0+)
  - `prometh_cortex_list_sources`: List all sources (v0.3.0+, renamed from list_collections)
  - `prometh_cortex_health`: System health with unified collection + source metrics
- **Unified Index Support**: Query all sources or filter by specific source
- **Configuration**: Ready for Claude Desktop integration with v0.3.0

### HTTP REST API Integration
**Status: ✅ v0.3.0 - FULLY IMPLEMENTED WITH PER-SOURCE CHUNKING SUPPORT**
- **FastAPI Server**: Complete REST API with unified collection support
- **Endpoints Available**:
  - `POST /prometh_cortex_query`: Search with optional `source_type` filter (v0.3.0+)
  - `GET /prometh_cortex_sources`: List sources and statistics (v0.3.0+, renamed from collections)
  - `GET /prometh_cortex_health`: Health check with unified collection metrics
  - `GET /`: API info with features and version
- **Unified Index Support**: Query all sources or filter by source_type
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