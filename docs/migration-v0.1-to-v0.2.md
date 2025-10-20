# Migration Guide: v0.1.x to v0.2.0 - Multi-Collection RAG Indexing

## Overview

Prometh-Cortex v0.2.0 introduces a major architectural change: **Multi-Collection RAG Indexing**. This guide will help you migrate from v0.1.x (single-collection) to v0.2.0 (multi-collection).

## What's New in v0.2.0

### ✨ Key Features

1. **Multi-Collection Indexing**: Index documents from multiple sources with independent configurations
2. **Smart Document Routing**: Automatically route documents to appropriate collections based on source patterns
3. **Collection-Specific Chunking**: Different collections can use different chunking parameters
4. **CLI Collections Command**: New `pcortex collections` command to list and manage collections
5. **Enhanced Query Interface**: Query specific collections or search all collections simultaneously
6. **API Endpoints**: New `/prometh_cortex_collections` endpoint for collection management

### 🔄 Breaking Changes

- **Index Storage Structure**: Changed from flat structure to `collections/` subdirectories
- **Configuration Format**: `CHUNK_SIZE` and `CHUNK_OVERLAP` replaced with `collections` array
- **Query Responses**: Results now include `collection` metadata
- **CLI Commands**: `build` and `query` commands have new options

## Migration Steps

### Step 1: Backup Your Current Index

```bash
# Backup existing v0.1.x index
cp -r $RAG_INDEX_DIR $RAG_INDEX_DIR.v0.1.backup

echo "✓ Backup created at: $RAG_INDEX_DIR.v0.1.backup"
```

### Step 2: Update Configuration

#### Option A: Simple Migration (Single Default Collection)

If you only need one collection, minimal changes are required:

**Before (v0.1.x)**:
```bash
# .env file
DATALAKE_REPOS='/path/to/docs'
RAG_INDEX_DIR='/path/to/index'
CHUNK_SIZE=512
CHUNK_OVERLAP=50
```

**After (v0.2.0)**:
```bash
# .env file - remove CHUNK_SIZE and CHUNK_OVERLAP
DATALAKE_REPOS='/path/to/docs'
RAG_INDEX_DIR='/path/to/index'
# Collections default to single 'default' collection with chunk_size=512, chunk_overlap=50
```

#### Option B: Advanced Migration (Multiple Collections)

For multiple collections, define them explicitly:

**TOML Configuration**:
```toml
[datalake]
repos = ["/path/to/docs"]

[storage]
rag_index_dir = "/path/to/index"

# NEW: Collections configuration (v0.2.0+)
[[collections]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]  # Catch-all pattern

[[collections]]
name = "knowledge_base"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["docs/specs", "docs/prds", "docs/guides"]

[[collections]]
name = "meetings"
chunk_size = 256         # Smaller chunks for meeting notes
chunk_overlap = 25
source_patterns = ["meetings", "standup"]

[[collections]]
name = "tasks"
chunk_size = 128         # Minimal chunks for tasks
chunk_overlap = 10
source_patterns = ["todos", "tasks", "reminders"]
```

**Environment Variables**:
```bash
# Using JSON format
export RAG_COLLECTIONS='[
  {"name":"default","chunk_size":512,"chunk_overlap":50,"source_patterns":["*"]},
  {"name":"knowledge_base","chunk_size":512,"chunk_overlap":50,"source_patterns":["docs/specs","docs/prds"]},
  {"name":"meetings","chunk_size":256,"chunk_overlap":25,"source_patterns":["meetings"]}
]'
```

### Step 3: Rebuild Indexes

```bash
# Remove old index structure (v0.1.x format incompatible with v0.2.0)
rm -rf $RAG_INDEX_DIR

# Create fresh indexes with new multi-collection structure
pcortex build --force

# Verify build completed
echo "✓ Index built for $(pcortex collections | grep -c Collection) collections"
```

### Step 4: Verify Migration

```bash
# List all collections
pcortex collections

# Expected output:
# 📚 RAG Collections (3)
# ┌─────────────────┬───────────┬────────────┬──────────────────────┐
# │ Collection      │ Documents │ Chunk Size │ Source Patterns      │
# ├─────────────────┼───────────┼────────────┼──────────────────────┤
# │ default         │ 50        │ 512        │ *                    │
# │ knowledge_base  │ 100       │ 512        │ docs/specs, docs/... │
# │ meetings        │ 25        │ 256        │ meetings             │
# └─────────────────┴───────────┴────────────┴──────────────────────┘
```

### Step 5: Update Your Queries

#### CLI Queries

**Before (v0.1.x)**:
```bash
pcortex query "search term"
```

**After (v0.2.0)**:
```bash
# Query all collections (default behavior)
pcortex query "search term"

# Query specific collection
pcortex query "search term" --collection knowledge_base

# Shorthand
pcortex query "search term" -c meetings
```

#### MCP Queries (Claude Desktop)

**Before (v0.1.x)**:
```
prometh_cortex_query(query: "search term")
```

**After (v0.2.0)**:
```
# Query all collections
prometh_cortex_query(query: "search term")

# Query specific collection
prometh_cortex_query(query: "search term", collection: "knowledge_base")

# List collections
prometh_cortex_list_collections()
```

#### HTTP REST API Queries

**Before (v0.1.x)**:
```bash
curl -X POST http://localhost:8080/prometh_cortex_query \
  -H "Authorization: Bearer test-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "search term",
    "max_results": 10
  }'
```

**After (v0.2.0)**:
```bash
# Query all collections (same format)
curl -X POST http://localhost:8080/prometh_cortex_query \
  -H "Authorization: Bearer test-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "search term",
    "max_results": 10
  }'

# Query specific collection (NEW)
curl -X POST http://localhost:8080/prometh_cortex_query \
  -H "Authorization: Bearer test-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "search term",
    "collection": "knowledge_base",
    "max_results": 10
  }'

# List collections (NEW endpoint)
curl http://localhost:8080/prometh_cortex_collections \
  -H "Authorization: Bearer test-token-123"
```

## Configuration Examples

### Example 1: Simple Single Collection

Minimal configuration for single collection (backward compatible):

```toml
[datalake]
repos = ["/path/to/docs"]

[storage]
rag_index_dir = "/path/to/index"

# Collections default to single "default" collection
```

### Example 2: Two Collections by Type

Split documents by type:

```toml
[[collections]]
name = "technical"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["docs/api", "docs/specs", "code"]

[[collections]]
name = "general"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["docs/guides", "README"]

[[collections]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]
```

### Example 3: Three Collections by Purpose

Collections for different use cases:

```toml
[[collections]]
name = "knowledge"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["docs", "guides", "tutorials"]

[[collections]]
name = "events"
chunk_size = 256
chunk_overlap = 25
source_patterns = ["meetings", "standups", "planning"]

[[collections]]
name = "tasks"
chunk_size = 128
chunk_overlap = 10
source_patterns = ["todos", "backlog", "tasks"]

[[collections]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]
```

## Index Storage Structure

### v0.1.x Structure
```
RAG_INDEX_DIR/
├── docstore.json
├── index_store.json
└── vector_store.json
```

### v0.2.0 Structure
```
RAG_INDEX_DIR/
└── collections/
    ├── default/
    │   ├── docstore.json
    │   ├── index_store.json
    │   ├── vector_store.json
    │   └── metadata.json
    ├── knowledge_base/
    │   ├── docstore.json
    │   ├── index_store.json
    │   ├── vector_store.json
    │   └── metadata.json
    ├── meetings/
    │   └── ...
    └── tasks/
        └── ...
```

## Troubleshooting

### Q: My queries are returning no results after migration

**A**: This is likely because:
1. New index hasn't been built yet: Run `pcortex build --force`
2. Documents are being routed to wrong collection: Run `pcortex collections` to verify routing
3. Check source patterns match your document structure

### Q: Error "Collection 'X' not found" when querying

**A**: The collection name doesn't exist or is misspelled.
```bash
# See available collections
pcortex collections

# Use correct collection name
pcortex query "term" --collection knowledge_base
```

### Q: How do I query all collections?

**A**: Omit the `--collection` parameter:
```bash
# Queries all collections
pcortex query "search term"

# Same as explicitly specifying all
pcortex query "search term" --collection knowledge_base --collection meetings
```

### Q: Can I still use my old v0.1.x configuration?

**A**: Not directly. You must:
1. Remove `CHUNK_SIZE` and `CHUNK_OVERLAP` environment variables
2. Either use defaults (single collection) or define collections explicitly
3. Rebuild indexes with `pcortex build --force`

### Q: How do I revert to v0.1.x?

**A**: If you need to revert:
```bash
# Restore v0.1.x index
rm -rf $RAG_INDEX_DIR
cp -r $RAG_INDEX_DIR.v0.1.backup $RAG_INDEX_DIR

# Downgrade package
pip install prometh-cortex==0.1.3

# Verify
pcortex --version
```

## Performance Considerations

### Building Multiple Collections

Building indexes for multiple collections will take longer than v0.1.x:
- v0.1.x: Single index build for all documents
- v0.2.0: Independent index builds for each collection

**Optimization tips**:
1. Use `pcortex build --incremental` after initial build
2. Collections with fewer documents build faster
3. Smaller `chunk_size` = faster indexing

### Querying Multiple Collections

Cross-collection queries are slightly slower than v0.1.x single-collection queries:
- v0.1.x: ~50ms for single index
- v0.2.0: ~100-150ms for 3-5 collections combined
- Still well within <300ms acceptable range

**Optimization tips**:
1. Use collection-specific queries when possible
2. Larger `max_results` from each collection = slower queries
3. FAISS is faster than Qdrant for multi-collection queries

## Rollout Strategy

### For New Installations

Start directly with v0.2.0:
```bash
pip install prometh-cortex>=0.2.0
```

### For Existing Installations

**Stage 1: Testing (Non-Production)**
```bash
# 1. Backup index
# 2. Update to v0.2.0
# 3. Test with sample documents
# 4. Verify performance
```

**Stage 2: Staging (Production-Like)**
```bash
# 1. Run parallel v0.1.x and v0.2.0 systems
# 2. Migrate configuration
# 3. Rebuild indexes
# 4. Monitor performance
```

**Stage 3: Production**
```bash
# 1. Final backup
# 2. Rebuild production indexes
# 3. Monitor queries
# 4. Confirm search quality
```

## Getting Help

### Commands

```bash
# See all available commands
pcortex --help

# Get help for specific command
pcortex build --help
pcortex query --help
pcortex collections --help

# Verbose output for debugging
pcortex -v build
pcortex -v query
```

### Common Issues

- **Empty collections after build**: Verify source patterns match document paths
- **Collection not found errors**: Use `pcortex collections` to see available collections
- **Slow queries**: Check if documents are properly distributed across collections

### Documentation

- **README**: [../../README.md](../../README.md)
- **Configuration**: [../configuration.md](../configuration.md)
- **API Reference**: [../api-reference.md](../api-reference.md)

## Summary of Changes

| Feature | v0.1.x | v0.2.0 |
|---------|--------|--------|
| Collections | Single (fixed) | Multiple (configurable) |
| Chunking | Global config | Per-collection config |
| Document Routing | N/A | Pattern-based automatic |
| Storage Structure | Flat | Hierarchical (collections/) |
| Query Interface | Single target | Single or multiple collections |
| CLI Commands | build, query | build, query, collections (NEW) |
| MCP Tools | prometh_cortex_query, health | + prometh_cortex_list_collections (NEW) |
| HTTP Endpoints | /prometh_cortex_query, /health | + /prometh_cortex_collections (NEW) |

## Version Support

- **v0.1.x**: Deprecated (no longer maintained)
- **v0.2.0+**: Current (actively maintained)

We recommend upgrading to v0.2.0 to enjoy the benefits of multi-collection RAG indexing!

---

**Last Updated**: 2025-10-20
**Version**: 0.2.0
