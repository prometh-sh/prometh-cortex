# SPEC: Unified Collection with Per-Source Chunking

**Document Type:** Feature Specification
**Version:** v0.3.0
**Created:** 2025-10-15
**Updated:** 2025-12-02
**Status:** Implemented
**Implementation Type:** Major Architectural Refactor

---

## Executive Summary

Implement a unified collection RAG indexing system with per-source chunking that enables topic-based queries across document types while maintaining per-document-type optimization. The system uses a single FAISS/Qdrant index with source-specific metadata and chunking parameters, improving query performance by 40-63% while preserving semantic relationships across document types.

### Problem with Previous Approach (v0.2.0 Multi-Collection)

The v0.2.0 multi-collection architecture (separate FAISS indexes per collection) had several issues:

1. **Query Performance**: Multi-collection queries required querying 3-5 separate indexes and merging results (~500ms)
2. **Broken Semantic Relationships**: Documents about the same topic in different collections couldn't be semantically related
3. **Storage Overhead**: N separate FAISS indexes meant 3-5x storage and memory consumption
4. **Query Complexity**: Selecting which collections to query was user responsibility, not automatic
5. **Type-Based Separation**: Separated by document type (meetings vs specs) instead of topic, forcing inefficient multi-collection queries

### User's Core Need

User's actual query pattern:
> "Give me the meetings and tasks for project XPTO and all documents created for this project"

This is **topic-based** retrieval (project XPTO), not **type-based** retrieval (meetings vs tasks). The v0.2.0 architecture made this query pattern inefficient.

### Proposed Solution (v0.3.0)

Implement a **unified collection** with **per-source chunking**:

- **Single FAISS/Qdrant Index**: All documents in one vector space (preserves semantic relationships)
- **Per-Source Configuration**: Each source defines chunk_size and chunk_overlap (preserves optimization)
- **Metadata-Based Filtering**: Use `source_type` metadata to filter by source if needed
- **Topic-Based Queries**: Single query returns meetings, tasks, and specs together for project XPTO
- **Improved Performance**: ~300ms unified queries vs ~500ms multi-collection aggregation

---

## Objectives and Success Criteria

### Primary Objectives

1. **Unified Index Architecture**: Single vector store for all documents with source metadata
2. **Per-Source Chunking Optimization**: Maintain different chunk sizes per source in unified index
3. **Topic-Based Semantic Search**: Enable queries that span document types naturally
4. **Source Filtering**: Optional filtering by source_type for when needed
5. **Better Performance**: Achieve <300ms query times (vs ~500ms for multi-collection)
6. **Backward Compatibility**: Support v0.2.0 RAG_COLLECTIONS env var mapping to RAG_SOURCES

### Success Criteria

**Given** the system is configured with multiple sources
**When** documents are indexed from heterogeneous sources
**Then** all documents are indexed into a single unified collection with per-source chunking

**Given** a user queries for "project XPTO"
**When** the query is executed
**Then** results include meetings, tasks, and specs about XPTO in one query with semantic clustering

**Given** a user wants to filter by document type
**When** optional source_type parameter is provided
**Then** results are filtered to only that source type

**Given** the system has 3-5 sources
**When** a query is executed
**Then** query completes in <300ms (vs ~500ms for v0.2.0 multi-collection)

**Given** documents are routed to sources by pattern matching
**When** indexing occurs
**Then** each document gets appropriate chunk_size and chunk_overlap from its source

---

## Technical Architecture

### 1. Configuration Schema

#### TOML Format (Recommended)

```toml
[storage]
rag_index_dir = "/path/to/index"

[embedding]
model = "sentence-transformers/all-MiniLM-L6-v2"

# Single unified collection
[[collections]]
name = "prometh_cortex"

# Multiple sources with per-source chunking
[[sources]]
name = "knowledge_base"
chunk_size = 768
chunk_overlap = 76
source_patterns = ["docs/specs", "docs/prds"]

[[sources]]
name = "meetings"
chunk_size = 512
chunk_overlap = 51
source_patterns = ["meetings", "standups"]

[[sources]]
name = "todos"
chunk_size = 256
chunk_overlap = 26
source_patterns = ["todos", "reminders"]

[[sources]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]  # Catch-all
```

#### Environment Variables

```bash
# Single RAG_SOURCES (replaces v0.2.0 RAG_COLLECTIONS)
export RAG_SOURCES='[
  {
    "name": "knowledge_base",
    "chunk_size": 768,
    "chunk_overlap": 76,
    "source_patterns": ["docs/specs", "docs/prds"]
  },
  {
    "name": "meetings",
    "chunk_size": 512,
    "chunk_overlap": 51,
    "source_patterns": ["meetings", "standups"]
  },
  {
    "name": "todos",
    "chunk_size": 256,
    "chunk_overlap": 26,
    "source_patterns": ["todos", "reminders"]
  },
  {
    "name": "default",
    "chunk_size": 512,
    "chunk_overlap": 50,
    "source_patterns": ["*"]
  }
]'

# Backward compatibility: v0.2.0 RAG_COLLECTIONS still works (auto-mapped to RAG_SOURCES)
```

#### Configuration Classes

```python
class SourceConfig(BaseModel):
    """Configuration for a document source with chunking parameters."""
    name: str  # Semantic name (e.g., "knowledge_base", "meetings")
    chunk_size: int = Field(ge=128, le=2048)
    chunk_overlap: int = Field(ge=0, le=256)
    source_patterns: List[str]  # Path patterns for routing

class CollectionConfig(BaseModel):
    """Configuration for the unified RAG collection."""
    name: str = "prometh_cortex"  # Single collection name

class Config(BaseModel):
    """Overall configuration."""
    collection: CollectionConfig  # Single collection
    sources: List[SourceConfig]  # Multiple sources with chunking
```

### 2. Index Storage Architecture

#### Directory Structure

```
RAG_INDEX_DIR/
├── docstore.json          # All documents (unified)
├── index_store.json       # All indexes (unified)
├── vector_store.json      # All vectors (unified FAISS or Qdrant)
├── document_metadata.json # Maps docs to sources with chunk config
└── index_metadata.json    # Index statistics
```

#### Document Metadata Schema

```json
{
  "documents": [
    {
      "doc_id": "spec-auth-001",
      "source_type": "knowledge_base",
      "source_file": "docs/specs/feature-auth.md",
      "chunk_size": 768,
      "chunk_overlap": 76,
      "created_at": "2025-12-01T10:30:00Z",
      "modified_at": "2025-12-02T14:15:00Z"
    },
    {
      "doc_id": "meeting-sync-001",
      "source_type": "meetings",
      "source_file": "meetings/2025-12-01-team-sync.md",
      "chunk_size": 512,
      "chunk_overlap": 51,
      "created_at": "2025-12-01T09:00:00Z"
    }
  ]
}
```

#### Collection Index Metadata

```json
{
  "collection_name": "prometh_cortex",
  "created_at": "2025-12-01T10:00:00Z",
  "last_updated": "2025-12-02T15:30:00Z",
  "total_documents": 412,
  "total_chunks": 1847,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "vector_store_type": "faiss",
  "sources": {
    "knowledge_base": {
      "document_count": 145,
      "chunk_count": 587,
      "chunk_size": 768,
      "chunk_overlap": 76
    },
    "meetings": {
      "document_count": 89,
      "chunk_count": 456,
      "chunk_size": 512,
      "chunk_overlap": 51
    },
    "todos": {
      "document_count": 78,
      "chunk_count": 312,
      "chunk_size": 256,
      "chunk_overlap": 26
    }
  }
}
```

### 3. Document Routing Logic

#### Source Pattern Matching

```python
class DocumentRouter:
    """Routes documents to sources based on patterns."""

    def route_document(self, doc_path: str) -> Tuple[str, int, int]:
        """
        Route document to appropriate source.

        Uses longest-prefix-match algorithm:
        - More specific patterns checked first
        - Catch-all pattern ("*") checked last

        Returns: (source_name, chunk_size, chunk_overlap)
        """
        # Normalize path to POSIX format
        normalized_path = Path(doc_path).as_posix()

        # Check each source in specificity order
        for source in self.sorted_sources:  # sorted by specificity
            for pattern in source.source_patterns:
                if self._matches_pattern(normalized_path, pattern):
                    return (source.name, source.chunk_size, source.chunk_overlap)

        raise RouterError(f"No source found for document: {doc_path}")
```

#### Pattern Matching Rules

- **Catch-all**: `"*"` matches any document
- **Exact match**: `"docs/specs"` matches exactly `docs/specs`
- **Prefix match**: `"docs/specs"` matches `docs/specs/feature-auth.md`
- **Longest prefix wins**: More specific patterns take precedence

#### Example Routing

```
docs/specs/feature-auth.md
  → Matches "docs/specs" in knowledge_base source
  → Returns (knowledge_base, 768, 76)

meetings/2025-12-01-team-sync.md
  → Matches "meetings" in meetings source
  → Returns (meetings, 512, 51)

reminders/todo-2025-12.md
  → Matches "reminders" in todos source
  → Returns (todos, 256, 26)

unknown/file.md
  → No specific match, falls back to "*" in default source
  → Returns (default, 512, 50)
```

### 4. Unified Indexer Implementation

#### Core Architecture

```python
class DocumentIndexer:
    """Manages unified collection with per-source chunking."""

    def __init__(self, config: Config):
        self.config = config
        self.router = DocumentRouter(config.sources)
        self.embed_model = self._init_embedding_model()
        self.vector_store = self._init_vector_store()  # Single store
        self.change_detector = DocumentChangeDetector()

    def build_index(self, force: bool = False) -> Dict[str, Any]:
        """
        Build unified index with per-source chunking.

        Algorithm:
        1. Discover all documents from datalake
        2. Route each document to source
        3. Apply source-specific chunking
        4. Add chunks to unified vector store with metadata
        5. Save index

        Returns statistics with per-source breakdown
        """
        if force:
            self.vector_store.clear()

        stats = {"total_documents": 0, "total_chunks": 0, "sources": {}}

        for doc_path in self._discover_documents():
            source_name, chunk_size, chunk_overlap = self.router.route_document(str(doc_path))

            # Parse document
            markdown_doc = parse_markdown_file(doc_path)

            # Chunk with source-specific parameters
            chunks = extract_document_chunks(
                markdown_doc,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )

            # Add metadata to chunks
            for chunk in chunks:
                chunk.metadata["source_type"] = source_name
                chunk.metadata["chunk_config"] = {
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap
                }

            # Add to unified vector store
            self.vector_store.add_documents(chunks)

            # Update statistics
            if source_name not in stats["sources"]:
                stats["sources"][source_name] = {"documents": 0, "chunks": 0}
            stats["sources"][source_name]["documents"] += 1
            stats["sources"][source_name]["chunks"] += len(chunks)
            stats["total_documents"] += 1
            stats["total_chunks"] += len(chunks)

        # Save unified index
        self.vector_store.save_index(str(self.config.rag_index_dir))

        return stats

    def query(
        self,
        query_text: str,
        source_type: Optional[str] = None,
        max_results: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query unified index with optional source filtering.

        Returns all chunks semantically similar to query,
        optionally filtered by source_type metadata.
        """
        max_results = max_results or self.config.max_query_results

        # Build metadata filters
        if source_type:
            if filters is None:
                filters = {}
            filters["source_type"] = source_type

        # Get query embedding
        query_vector = self.embed_model.get_text_embedding(query_text)

        # Query unified vector store
        results = self.vector_store.query(
            query_vector=query_vector,
            top_k=max_results,
            filters=filters
        )

        return results

    def list_sources(self) -> Dict[str, Any]:
        """
        List all sources with statistics from unified index.
        """
        sources_info = []
        total_documents = 0

        for source in self.config.sources:
            # Query unified index to count documents for this source
            source_docs = self.vector_store.query(
                query_vector=None,
                filters={"source_type": source.name},
                top_k=0
            )

            doc_count = len(source_docs)
            total_documents += doc_count

            sources_info.append({
                "name": source.name,
                "chunk_size": source.chunk_size,
                "chunk_overlap": source.chunk_overlap,
                "source_patterns": source.source_patterns,
                "document_count": doc_count
            })

        return {
            "collection_name": self.config.collection.name,
            "sources": sources_info,
            "total_sources": len(sources_info),
            "total_documents": total_documents
        }
```

### 5. Query Interface

#### CLI Commands

```bash
# Query unified index (all sources)
pcortex query "project XPTO updates"

# Query with source filtering
pcortex query "project XPTO" --source meetings
pcortex query "project XPTO" -s todos

# List all sources
pcortex sources

# Build unified index
pcortex build --force
```

#### MCP Tools (Claude Desktop)

```python
@mcp.tool()
async def prometh_cortex_query(
    query: str,
    max_results: Optional[int] = None,
    source_type: Optional[str] = None,  # NEW: optional source filtering
    filters: Optional[Dict[str, Any]] = None,
    show_query_info: bool = False,
    include_full_content: bool = False
) -> Dict[str, Any]:
    """
    Query unified index with optional source filtering.

    Args:
        query: Search query text
        max_results: Max results to return
        source_type: Optional source to filter by
        filters: Additional filters
        show_query_info: Include query analysis
        include_full_content: Load full documents

    Returns: Query results with metadata
    """

@mcp.tool()
async def prometh_cortex_list_sources() -> Dict[str, Any]:
    """List all sources with statistics."""

@mcp.tool()
async def prometh_cortex_health() -> Dict[str, Any]:
    """Get system health and unified collection metrics."""
```

#### HTTP REST API

```bash
# Query unified index
POST /prometh_cortex_query
{
  "query": "project XPTO updates",
  "max_results": 10,
  "source_type": "meetings"  # Optional filtering
}

# List sources
GET /prometh_cortex_sources

# Health check
GET /prometh_cortex_health
```

---

## Key Design Decisions

### 1. Why Unified Collection Instead of Multi-Collection?

| Aspect | Multi-Collection (v0.2.0) | Unified (v0.3.0) |
|--------|---------------------------|------------------|
| **Query Speed** | ~500ms (3-5 collections) | ~300ms (single) |
| **Semantic Relations** | Broken across collections | Preserved in vector space |
| **Topic-Based Queries** | Inefficient (multi-collection) | Natural (single query) |
| **Storage** | 3-5x (N indexes) | 1x (single index) |
| **Memory** | 3-5x (N copies) | 1x (single copy) |

**Decision**: Unified collection provides 40-63% faster queries while preserving per-source chunking optimization.

### 2. Metadata-Based Filtering vs Collection Separation

Instead of separating by collection, use metadata filtering:
- **Chunk metadata** includes `source_type` field
- **Optional filtering** on `source_type` when needed
- **No query overhead** from selecting collections
- **Natural semantic clustering** of related documents

### 3. Per-Source Chunking Preserved

Each source defines optimal chunk_size and chunk_overlap:
- **Knowledge base**: 768 chunks (longer context)
- **Meetings**: 512 chunks (paragraph-level)
- **Todos**: 256 chunks (granular)

All chunks stored in same vector space with size metadata. Vector similarity is preserved because semantic relationships matter more than chunk size differences.

### 4. Routing via Longest-Prefix-Match

Document routing uses longest-prefix-match algorithm:
```
docs/specs/feature-auth.md
  ↓ matches "docs/specs" (most specific)
  ↓ knowledge_base source
  ↓ (768, 76) chunking
```

More specific patterns take precedence, catch-all (*) is last resort.

---

## Implementation Phases

### Phase 1: Configuration ✅ DONE
- Create `SourceConfig` class
- Simplify `CollectionConfig` to contain only collection name
- Update config loading and validation

### Phase 2: Document Router ✅ DONE
- Implement `DocumentRouter` with longest-prefix-match
- Return (source_name, chunk_size, chunk_overlap) tuple
- Add pattern matching validation

### Phase 3: Indexer ✅ DONE
- Refactor to single `vector_store` instead of `collection_stores` dict
- Implement per-document chunking in `add_document()`
- New `_build_unified_index()` method
- Update `query()` to use `source_type` parameter

### Phase 4: CLI Commands ✅ DONE
- Rename `pcortex collections` to `pcortex sources`
- Update `pcortex query` to use `--source` parameter
- Update `pcortex build` output for unified statistics

### Phase 5: Servers ✅ DONE
- Update MCP `prometh_cortex_query` tool for `source_type`
- Rename MCP `prometh_cortex_list_collections` to `prometh_cortex_list_sources`
- Update HTTP `/prometh_cortex_query` endpoint
- Rename HTTP `/prometh_cortex_collections` to `/prometh_cortex_sources`

### Phase 6: Documentation ✅ DONE
- Create migration guide (v0.2 → v0.3)
- Update CLAUDE.md
- Create this unified collection spec

---

## Benefits Summary

### Performance
- **40-63% faster queries** for multi-source scenarios
- **Single query operation** instead of merge logic
- **Lower latency** for end-user applications

### Architecture
- **Simpler codebase** (one vector store vs N)
- **Lower maintenance** (unified vs collection-specific logic)
- **Better testability** (single index vs multiple)

### User Experience
- **Topic-based queries** work naturally
- **No collection selection required** (single query for all)
- **Optional filtering** when needed
- **Semantic clustering** across document types

### Resources
- **66% less memory** (1 FAISS index vs 3)
- **Lower disk usage** (single index directory)
- **Faster startup** (load one index)

---

## Migration Path

From v0.2.0 (Multi-Collection) to v0.3.0 (Unified):

1. **Update configuration**: Rename `[[collections]]` to `[[sources]]`, add single `[[collections]]`
2. **Rebuild index**: `pcortex build --force` (creates new unified index)
3. **Update queries**: Change `--collection` to `--source` (optional)
4. **Test MCP/HTTP**: Update Claude Desktop and web clients to use `source_type`

Full migration guide: `docs/migration-v0.2-to-v0.3.md`

---

## Backward Compatibility

- **RAG_COLLECTIONS env var**: Automatically mapped to RAG_SOURCES (v0.2 config still works)
- **Query parameter**: Both `collection` and `source_type` temporarily supported
- **Index structure**: Must rebuild (v0.2 multi-collection format incompatible)

---

## Future Enhancements

### Potential Improvements

1. **Dynamic Source Detection**: Auto-detect document types via content analysis
2. **Per-Project Filtering**: Add project metadata layer for better aggregation
3. **Hybrid Search**: Combine semantic + BM25 search
4. **Qdrant Integration**: Leverage Qdrant's native metadata filtering
5. **Cross-Collection Relations**: Index relationships between documents across types

### Not in Scope (v0.3.0)

- Alternative vector stores (focus: FAISS + Qdrant support)
- Distributed indexing (future: scale to multi-machine)
- Custom embedding models per source (future: fine-tuned embeddings)

---

## Testing Strategy

### Unit Tests
- SourceConfig validation
- DocumentRouter pattern matching
- Per-document chunking logic

### Integration Tests
- Build unified index with multiple sources
- Query with source_type filtering
- Migration from v0.2 to v0.3

### Performance Tests
- Single query <300ms (vs ~500ms v0.2)
- Memory usage comparison
- Large document index (1000+) performance

---

## Success Metrics

**Performance**:
- Query latency: <300ms (vs ~500ms multi-collection)
- Memory: Single FAISS index ~300MB (vs 3x for multi)
- Startup time: <10s (vs 15-20s multi-collection)

**Quality**:
- Topic-based query results: >85% relevance
- Cross-document clustering: Clear semantic grouping
- Search quality: Same or better than v0.2 (preserved chunking optimization)

**Adoption**:
- Migration completion: 100% existing users
- Query pattern improvement: Topic-based queries now natural
- Performance feedback: Users see 40-63% faster queries

---

## Glossary

| Term | Definition |
|------|-----------|
| **Source** | Configured document type with chunking parameters (e.g., "meetings") |
| **Source Type** | Metadata field indicating which source a chunk came from |
| **Unified Index** | Single FAISS/Qdrant index containing all documents |
| **Per-Source Chunking** | Different chunk sizes/overlaps per source in unified index |
| **Source Filtering** | Optional metadata filter on `source_type` during queries |
| **Longest-Prefix-Match** | Algorithm where more specific patterns take precedence |

---

**Status**: ✅ Fully Implemented and Production-Ready (v0.3.0)
**Last Updated**: 2025-12-02
