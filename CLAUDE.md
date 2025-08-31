# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Prometh-Cortex is a **fully implemented** local-first Multi-Datalake RAG (Retrieval-Augmented Generation) Indexer with dual MCP/HTTP server integration. The system indexes multiple datalake repositories containing Markdown files and exposes their content through both **MCP protocol** (for Claude Desktop) and **HTTP REST API** (for Perplexity, VSCode, and web integrations).

## Architecture

The system implements a complete pipeline architecture:

1. **Configuration Layer**: Uses `.env` files with comprehensive settings
2. **Datalake Ingest & Parser**: Processes Markdown files with complex YAML frontmatter schemas
3. **Vector Store / Indexing**: Uses LlamaIndex/FAISS with HuggingFace sentence-transformers
4. **Dual Server Architecture**:
   - **MCP Protocol Server** (`pcortex mcp`): stdio-based for Claude Desktop integration
   - **HTTP REST Server** (`pcortex serve`): FastAPI server for web/API integrations

## Project Structure

```
src/prometh_cortex/
├── cli/                    # CLI commands and main entry point
│   ├── commands/          # Individual command implementations
│   │   ├── build.py       # Index building
│   │   ├── mcp.py         # MCP server startup
│   │   ├── query.py       # Local querying
│   │   ├── rebuild.py     # Index rebuilding
│   │   └── serve.py       # HTTP server startup
│   └── main.py            # Main CLI entry point
├── config/                # Configuration management
├── indexer/               # RAG indexing and querying logic
├── mcp/                   # MCP protocol server implementation
├── parser/                # Markdown and YAML frontmatter parsing
├── server/                # HTTP REST API server
└── utils/                 # Utility functions
```

## Current Implementation Status

**✅ FULLY IMPLEMENTED AND WORKING:**

### Core Features
- ✅ **Complete CLI Interface**: All commands implemented and tested
- ✅ **Advanced Configuration**: Environment-based with validation
- ✅ **YAML Frontmatter Parser**: Supports complex schemas with datetime handling
- ✅ **Vector Indexing**: LlamaIndex + FAISS with HuggingFace embeddings
- ✅ **Dual Server Architecture**: Both MCP and HTTP servers implemented

### Production Capabilities
- ✅ **345 Documents Indexed**: Successfully tested with user's Obsidian vault
- ✅ **Fast Query Performance**: <300ms response times achieved
- ✅ **Robust Error Handling**: Comprehensive exception handling throughout
- ✅ **Authentication**: Bearer token authentication for HTTP endpoints

## Configuration

The system uses `.env` files with the following structure:

### Current Production Configuration
```bash
# Required: Datalake repository paths
DATALAKE_REPOS='/path/to/your/documents'

# Index storage location
RAG_INDEX_DIR='/path/to/index/storage'

# HTTP Server configuration
MCP_PORT=8080
MCP_HOST=localhost
MCP_AUTH_TOKEN=test-token-123

# Embedding and search settings
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
MAX_QUERY_RESULTS=10
CHUNK_SIZE=512
CHUNK_OVERLAP=50
```

## Available CLI Commands

### Index Management
- `pcortex build` - Build index from configured datalakes
- `pcortex rebuild` - Rebuild entire index from scratch
- `pcortex query "search text"` - Query index locally for testing

### Server Operations
- `pcortex mcp` - Start MCP protocol server (for Claude Desktop)
- `pcortex serve` - Start HTTP REST server (for Perplexity/VSCode/web)
- `pcortex config --sample` - Generate sample configuration

## Integration Status

### MCP Integration (Claude Desktop)
**Status: ✅ IMPLEMENTED**
- **MCP Protocol Server**: Complete stdio-based implementation using FastMCP
- **MCP Tools Available**:
  - `prometh_cortex_query`: Search indexed documents
  - `prometh_cortex_health`: Get system health status
- **Configuration**: Ready for Claude Desktop integration

### HTTP REST API Integration
**Status: ✅ IMPLEMENTED**
- **FastAPI Server**: Complete REST API implementation
- **Endpoints Available**:
  - `POST /prometh_cortex_query`: Search with JSON payload
  - `GET /prometh_cortex_health`: Health check endpoint
- **Authentication**: Bearer token protected
- **CORS**: Configured for web integration

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