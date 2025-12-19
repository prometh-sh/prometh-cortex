# SPEC: RAG Multi-Collection Indexing System (v0.2.0 - DEPRECATED)

> ⚠️ **DEPRECATED**: This specification documents v0.2.0 architecture, which has been superseded by v0.3.0.
>
> **Current Version**: See [feature-unified-collection-per-source-chunking-spec.md](feature-unified-collection-per-source-chunking-spec.md) for v0.3.0+ implementation.
>
> **Migration Guide**: See [docs/migration-v0.2-to-v0.3.md](../migration-v0.2-to-v0.3.md) for upgrade instructions.

**Document Type:** Feature Specification (Archived)
**Created:** 2025-10-15
**Status:** Deprecated - Superseded by v0.3.0
**Implementation Type:** Feature Development (Historical Reference)

---

## Executive Summary

Implement a configurable multi-collection RAG indexing system that enables source-to-collection routing for heterogeneous document types. The system will support independent collections with type-specific chunking strategies, optimized embeddings, and metadata-based filtering to dramatically improve retrieval precision for diverse content types.

### Current Problem

The existing implementation indexes all heterogeneous documents (technical specs, git logs, meeting notes, todos) into a single RAG collection using uniform chunking and embedding parameters. This creates several critical issues:

1. **Poor Retrieval Precision**: Different document types have vastly different semantic density and query patterns
2. **Lost Metadata Context**: Rich metadata (tags, dates, status, document type) isn't leveraged for filtering
3. **Temporal Context Loss**: Time-series data (git commits, task updates) loses chronological relevance
4. **Query Result Mixing**: Low-precision results mix task statuses with architecture documentation
5. **Suboptimal Chunking**: One-size-fits-all chunk size doesn't accommodate varying semantic structures

### Proposed Solution

Implement a configurable routing system where:
- Each document source maps to a dedicated collection (e.g., `knowledge_base`, `meetings`, `activity_logs`, `asset_logs`)
- Each collection has optimized chunking parameters (`chunk_size`, `chunk_overlap`)
- Type-specific metadata enrichment and indexing strategies
- Collection-aware querying with optional cross-collection search

---

## Objectives and Success Criteria

### Primary Objectives

1. **Configurable Source-to-Collection Routing**: Enable administrators to map document sources to named collections via configuration
2. **Collection-Specific Optimization**: Support per-collection chunking and embedding parameters
3. **Metadata-Enhanced Retrieval**: Leverage document metadata for filtering and relevance scoring
4. **Backward Compatibility**: Maintain existing single-collection functionality as default behavior
5. **Query Flexibility**: Support both single-collection and cross-collection queries

### Success Criteria

**Given** the system is configured with multiple collections
**When** documents are indexed from heterogeneous sources
**Then** each document is routed to its appropriate collection with optimized parameters

**Given** a user queries a specific collection (e.g., "meetings")
**When** the query is executed
**Then** results are returned only from that collection with >85% relevance precision

**Given** a user performs a cross-collection search
**When** the query spans multiple collections
**Then** results are returned with collection metadata and merged relevance scoring

**Given** git logs are indexed into the `asset_logs` collection
**When** querying for temporal commit history
**Then** results maintain chronological context and code change relevance

**Given** the system is configured without collection routing
**When** documents are indexed
**Then** the system defaults to single-collection behavior (backward compatible)

---

## Technical Requirements

### 1. Configuration Schema

#### Environment Variables
```bash
# Collection routing configuration
RAG_COLLECTIONS='knowledge_base,meetings,activity_logs,asset_logs'

# Source-to-collection mapping (JSON format)
RAG_SOURCE_COLLECTION_MAP='{"docs/specs": "knowledge_base", "docs/prds": "knowledge_base", "meetings": "meetings", "todos": "activity_logs", ".git": "asset_logs"}'

# Per-collection chunking configuration (JSON format)
RAG_COLLECTION_PARAMS='{
  "knowledge_base": {"chunk_size": 512, "chunk_overlap": 50},
  "meetings": {"chunk_size": 256, "chunk_overlap": 25},
  "activity_logs": {"chunk_size": 128, "chunk_overlap": 10},
  "asset_logs": {"chunk_size": 384, "chunk_overlap": 30}
}'

# Default chunking for unmatched sources (backward compatibility)
CHUNK_SIZE=512
CHUNK_OVERLAP=50
```

#### Configuration Validation
- Validate JSON format for `RAG_SOURCE_COLLECTION_MAP` and `RAG_COLLECTION_PARAMS`
- Ensure all collections in mapping exist in `RAG_COLLECTIONS`
- Validate chunk_size and chunk_overlap are positive integers
- Provide clear error messages for misconfiguration

### 2. Index Storage Architecture

#### Directory Structure
```
RAG_INDEX_DIR/
├── collections/
│   ├── knowledge_base/
│   │   ├── docstore.json
│   │   ├── index_store.json
│   │   ├── vector_store.json
│   │   └── metadata.json
│   ├── meetings/
│   │   └── [same structure]
│   ├── activity_logs/
│   │   └── [same structure]
│   └── asset_logs/
│       └── [same structure]
└── default/  # Backward compatibility
    └── [existing single-collection structure]
```

#### Metadata Schema
Each collection's `metadata.json` contains:
```json
{
  "collection_name": "knowledge_base",
  "created_at": "2025-10-15T10:30:00Z",
  "last_updated": "2025-10-15T11:45:00Z",
  "document_count": 145,
  "chunk_size": 512,
  "chunk_overlap": 50,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "source_paths": [
    "docs/specs",
    "docs/prds"
  ]
}
```

### 3. Document Routing Logic

#### Source Path Matching
```python
def determine_collection(document_path: str) -> str:
    """Route document to appropriate collection based on path matching."""
    # Load source-to-collection mapping
    # Match longest prefix (most specific match)
    # Return collection name or "default" if no match
```

#### Example Routing Rules
- `docs/specs/feature-auth.md` → `knowledge_base` (matches `docs/specs`)
- `meetings/2025-10-team-sync.md` → `meetings` (matches `meetings`)
- `todos/sprint-tasks.md` → `activity_logs` (matches `todos`)
- `.git/logs/refs/heads/main` → `asset_logs` (matches `.git`)

### 4. Indexer Modifications

#### Multi-Collection Indexer
```python
class MultiCollectionIndexer:
    """Manages multiple RAG collections with independent configurations."""

    def __init__(self, config: Config):
        self.collections = {}  # collection_name -> LlamaIndex instance
        self.routing_map = self._load_routing_map()
        self.collection_params = self._load_collection_params()

    def build_indexes(self, force: bool = False):
        """Build or update all configured collections."""
        # For each datalake source:
        #   1. Determine target collection via routing
        #   2. Load/create collection index with appropriate params
        #   3. Process documents with collection-specific chunking
        #   4. Update collection metadata

    def get_collection(self, name: str) -> LlamaIndex:
        """Get specific collection instance."""

    def query_collection(self, collection: str, query: str, max_results: int):
        """Query a single collection."""

    def query_all(self, query: str, max_results: int):
        """Query across all collections with merged results."""
```

#### Backward Compatibility Layer
```python
class IndexerFactory:
    """Factory to create appropriate indexer based on configuration."""

    @staticmethod
    def create_indexer(config: Config):
        if config.rag_collections:
            return MultiCollectionIndexer(config)
        else:
            return LegacyIndexer(config)  # Existing single-collection
```

### 5. Query Interface Extensions

#### CLI Query Command
```bash
# Query specific collection
pcortex query "authentication flow" --collection knowledge_base --max-results 5

# Query all collections
pcortex query "team decisions" --all-collections --max-results 10

# Query multiple specific collections
pcortex query "recent updates" --collections meetings,activity_logs --max-results 7
```

#### MCP Tool Extension
```python
@mcp.tool()
def prometh_cortex_query(
    query: str,
    collection: str = None,  # New parameter
    all_collections: bool = False,  # New parameter
    max_results: int = 10
) -> dict:
    """Query RAG index with optional collection filtering."""
```

#### HTTP API Extension
```json
POST /prometh_cortex_query
{
    "query": "authentication implementation",
    "collection": "knowledge_base",  // Optional
    "all_collections": false,  // Optional
    "max_results": 5
}

Response:
{
    "results": [
        {
            "text": "...",
            "score": 0.89,
            "metadata": {
                "source": "docs/specs/feature-auth.md",
                "collection": "knowledge_base",
                "chunk_size": 512
            }
        }
    ],
    "collection_counts": {
        "knowledge_base": 3,
        "meetings": 0
    }
}
```

### 6. Metadata Enrichment

#### Document Metadata Fields
Each indexed chunk includes:
```python
{
    "source_path": str,          # Original document path
    "collection": str,           # Collection name
    "document_type": str,        # Inferred type (spec, meeting, log, etc.)
    "chunk_size": int,           # Chunking parameter used
    "indexed_at": datetime,      # Index timestamp
    "yaml_frontmatter": dict,    # Existing frontmatter parsing
    "temporal_context": dict     # For time-series data (git logs, tasks)
}
```

#### Type-Specific Enrichment
- **Git Logs**: Extract commit hash, author, date, changed files
- **Meeting Notes**: Extract date, attendees, action items
- **Task/Todos**: Extract status, priority, due date, assignee
- **Technical Specs**: Extract document type, created date, status

---

## Architecture and Design

### Component Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                    Configuration Layer                       │
│  (RAG_COLLECTIONS, RAG_SOURCE_COLLECTION_MAP, etc.)         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Document Router                             │
│  • Source Path Matching                                      │
│  • Collection Determination                                  │
│  • Parameter Lookup                                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Multi-Collection Indexer                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ knowledge_   │ │   meetings   │ │ activity_    │        │
│  │    base      │ │              │ │    logs      │  ...   │
│  │ (512/50)     │ │  (256/25)    │ │  (128/10)    │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Query Interface                             │
│  • Single Collection Query                                   │
│  • Cross-Collection Search                                   │
│  • Result Merging & Ranking                                  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

#### Indexing Flow
1. **Configuration Loading**: Parse collection definitions and routing rules
2. **Source Scanning**: Iterate through datalake repositories
3. **Document Routing**: Match source paths to collections
4. **Parameter Application**: Apply collection-specific chunk_size/overlap
5. **Metadata Enrichment**: Add type-specific metadata fields
6. **Index Persistence**: Store in collection-specific directory

#### Query Flow
1. **Query Parsing**: Extract query text and collection filters
2. **Collection Selection**: Determine target collection(s)
3. **Parallel Execution**: Query selected collections concurrently
4. **Result Merging**: Combine and rank results if multi-collection
5. **Response Formatting**: Include collection metadata in results

### Design Patterns

- **Factory Pattern**: `IndexerFactory` creates appropriate indexer based on config
- **Strategy Pattern**: Collection-specific chunking and enrichment strategies
- **Repository Pattern**: Abstract index storage and retrieval operations
- **Facade Pattern**: Unified query interface across multiple collections

---

## Implementation Plan

### Phase 1: Planning (Estimated: 2-3 days)

#### Requirements Analysis
- Review existing indexer architecture and identify extension points
- Analyze configuration schema requirements and validation logic
- Define metadata enrichment strategies for each document type
- Design backward compatibility approach for existing installations

#### Technical Design
- Create detailed component diagrams for multi-collection architecture
- Design index storage directory structure and metadata schemas
- Define source routing algorithm with prefix matching logic
- Specify query result merging and ranking strategy

#### Resource Allocation
- **Primary Developer**: Core indexing and routing logic
- **Configuration Specialist**: Config schema and validation
- **Testing Engineer**: Test strategy and fixture creation
- **Documentation Writer**: API documentation and migration guide

#### Risk Assessment
- **Risk**: Breaking changes to existing single-collection users
  - **Mitigation**: Maintain backward compatibility with factory pattern
- **Risk**: Performance degradation with multiple collections
  - **Mitigation**: Implement lazy loading and concurrent querying
- **Risk**: Complex configuration errors
  - **Mitigation**: Comprehensive validation with clear error messages

### Phase 2: Task Breakdown (Estimated: 1 day)

#### Task List

**2.1 Configuration Management**
- [ ] Define Pydantic models for collection configuration
- [ ] Implement JSON validation for `RAG_SOURCE_COLLECTION_MAP`
- [ ] Implement JSON validation for `RAG_COLLECTION_PARAMS`
- [ ] Add configuration loading and validation in `config/settings.py`
- [ ] Write unit tests for configuration validation
- [ ] **Acceptance**: All configuration edge cases validated with clear errors

**2.2 Document Routing System**
- [ ] Implement `DocumentRouter` class with prefix matching
- [ ] Add longest-prefix-match algorithm for source paths
- [ ] Implement fallback to "default" collection for unmatched sources
- [ ] Write unit tests for routing logic
- [ ] **Acceptance**: 100% accurate routing based on configuration

**2.3 Multi-Collection Index Storage**
- [ ] Create directory structure management for collections
- [ ] Implement collection metadata schema and persistence
- [ ] Add collection-specific index loading and saving
- [ ] Implement lazy loading for collection instances
- [ ] Write integration tests for storage operations
- [ ] **Acceptance**: Independent collection storage with metadata tracking

**2.4 Indexer Refactoring**
- [ ] Create `MultiCollectionIndexer` class
- [ ] Implement `IndexerFactory` for backward compatibility
- [ ] Refactor `build` command to use factory pattern
- [ ] Add collection-specific chunking parameter application
- [ ] Implement parallel collection building
- [ ] Write unit tests for indexer factory
- [ ] **Acceptance**: Both single and multi-collection modes work seamlessly

**2.5 Metadata Enrichment**
- [ ] Define metadata schema with collection and temporal fields
- [ ] Implement type-specific enrichment for git logs
- [ ] Implement type-specific enrichment for meeting notes
- [ ] Implement type-specific enrichment for task/todos
- [ ] Add metadata to indexed chunks
- [ ] Write unit tests for enrichment logic
- [ ] **Acceptance**: All document types have appropriate metadata

**2.6 Query Interface Extensions**
- [ ] Add `--collection` flag to CLI query command
- [ ] Add `--all-collections` flag for cross-collection search
- [ ] Implement single-collection query logic
- [ ] Implement cross-collection query with result merging
- [ ] Add collection metadata to query responses
- [ ] Update MCP tool signature with collection parameters
- [ ] Update HTTP API endpoint with collection parameters
- [ ] Write integration tests for query variations
- [ ] **Acceptance**: All query modes return correct, collection-aware results

**2.7 Documentation and Migration**
- [ ] Update README.md with multi-collection configuration examples
- [ ] Create migration guide for existing users
- [ ] Document collection configuration best practices
- [ ] Add API documentation for new query parameters
- [ ] Create example configurations for common use cases
- [ ] **Acceptance**: Clear documentation for setup and migration

**2.8 Testing and Quality Assurance**
- [ ] Create test fixtures for multiple collections
- [ ] Write end-to-end tests for full indexing workflow
- [ ] Write end-to-end tests for query workflows
- [ ] Perform load testing with 1000+ documents
- [ ] Test backward compatibility with existing configs
- [ ] Validate query performance meets <300ms target
- [ ] **Acceptance**: >95% test coverage, all performance targets met

### Phase 3: Implementation (Estimated: 5-7 days)

#### Week 1: Core Infrastructure (Days 1-3)

**Day 1: Configuration and Routing**
- Implement configuration models and validation
- Build document routing system with tests
- Establish collection directory structure
- **Deliverable**: Working configuration system with validated routing

**Day 2: Multi-Collection Indexer**
- Create `MultiCollectionIndexer` class
- Implement collection-specific parameter application
- Add lazy loading and index persistence
- **Deliverable**: Functional multi-collection indexing

**Day 3: Metadata Enrichment**
- Implement type-specific metadata enrichment
- Add temporal context for time-series documents
- Integrate enrichment into indexing pipeline
- **Deliverable**: Enhanced metadata in all indexed chunks

#### Week 2: Query Interface and Testing (Days 4-7)

**Day 4: CLI and Query Logic**
- Extend CLI with collection parameters
- Implement single and cross-collection query logic
- Add result merging and ranking
- **Deliverable**: Working CLI with collection-aware queries

**Day 5: MCP and HTTP Extensions**
- Update MCP tool with collection parameters
- Extend HTTP API endpoint
- Add collection metadata to responses
- **Deliverable**: All interfaces support multi-collection queries

**Day 6: Testing and Validation**
- Execute comprehensive test suite
- Perform load testing with realistic data
- Validate backward compatibility
- Test query performance benchmarks
- **Deliverable**: Fully tested, production-ready implementation

**Day 7: Documentation and Deployment**
- Complete documentation updates
- Create migration guide
- Prepare deployment procedures
- **Deliverable**: Release-ready feature with complete documentation

---

## Testing Strategy

### Unit Tests

**Configuration Validation**
```python
def test_valid_collection_config():
    """Test valid collection configuration parsing."""

def test_invalid_json_source_map():
    """Test error handling for malformed JSON."""

def test_missing_collection_in_params():
    """Test validation error for unmapped collections."""
```

**Document Routing**
```python
def test_exact_path_match():
    """Test routing for exact source path matches."""

def test_longest_prefix_match():
    """Test routing uses longest prefix for specificity."""

def test_fallback_to_default():
    """Test unmatched sources route to default collection."""
```

**Metadata Enrichment**
```python
def test_git_log_enrichment():
    """Test git log metadata extraction."""

def test_meeting_note_enrichment():
    """Test meeting note metadata extraction."""

def test_temporal_context_addition():
    """Test temporal metadata for time-series documents."""
```

### Integration Tests

**End-to-End Indexing**
```python
def test_multi_collection_build():
    """Test full indexing workflow with multiple collections."""
    # Setup: Configure 3 collections with different sources
    # Execute: Run pcortex build
    # Assert: Each collection has correct document count and metadata

def test_backward_compatibility():
    """Test single-collection mode still works."""
    # Setup: Config without RAG_COLLECTIONS
    # Execute: Run pcortex build
    # Assert: Creates default collection index
```

**Query Workflows**
```python
def test_single_collection_query():
    """Test querying specific collection."""
    # Setup: Index docs into knowledge_base
    # Execute: Query with --collection knowledge_base
    # Assert: Results only from that collection

def test_cross_collection_query():
    """Test querying all collections."""
    # Setup: Index docs into multiple collections
    # Execute: Query with --all-collections
    # Assert: Results merged from all collections with metadata

def test_query_performance():
    """Test query speed meets <300ms target."""
    # Setup: Index 1000+ documents across collections
    # Execute: 10 queries to different collections
    # Assert: Average response time <300ms
```

### Performance Tests

**Load Testing**
- Index 1000+ documents across 4 collections
- Measure indexing throughput (documents/second)
- Validate memory usage remains reasonable
- Test concurrent query handling

**Regression Testing**
- Compare single-collection performance before/after changes
- Ensure no degradation in existing functionality
- Validate backward compatibility with existing configs

### User Acceptance Testing

**Scenario 1: Technical Documentation Search**
- **Given**: 200 technical specs indexed in `knowledge_base`
- **When**: User queries "authentication implementation"
- **Then**: Returns only relevant architecture docs, no meeting notes

**Scenario 2: Meeting Context Retrieval**
- **Given**: 50 meeting notes indexed in `meetings`
- **When**: User queries "team decision on API design"
- **Then**: Returns meeting notes with temporal context, no code specs

**Scenario 3: Cross-Collection Discovery**
- **Given**: Content in multiple collections
- **When**: User queries with `--all-collections`
- **Then**: Returns relevant results from all collections with metadata

---

## Deployment and Rollout

### Deployment Steps

1. **Pre-Deployment Validation**
   - Verify all tests pass (unit, integration, performance)
   - Review code changes and documentation
   - Confirm backward compatibility testing complete

2. **Version Bump**
   - Update version in `pyproject.toml` (e.g., 0.2.0 for feature release)
   - Update CHANGELOG.md with new features and breaking changes (if any)

3. **Package Build and Distribution**
   ```bash
   # Build package
   python -m build

   # Test installation in clean environment
   pip install dist/prometh_cortex-0.2.0-py3-none-any.whl

   # Verify CLI commands work
   pcortex --version
   pcortex config --sample
   ```

4. **Documentation Updates**
   - Update README.md with multi-collection examples
   - Publish migration guide for existing users
   - Update MCP integration docs with new parameters
   - Add API documentation for HTTP endpoint extensions

5. **Deployment Procedure**
   ```bash
   # Stop existing servers (if running)
   # MCP and HTTP servers

   # Backup existing indexes
   cp -r $RAG_INDEX_DIR $RAG_INDEX_DIR.backup

   # Install new version
   pip install --upgrade prometh-cortex

   # Update configuration (if migrating to multi-collection)
   # Add RAG_COLLECTIONS, RAG_SOURCE_COLLECTION_MAP, etc. to .env

   # Rebuild indexes with new structure
   pcortex rebuild --force

   # Restart servers
   pcortex mcp  # or pcortex serve
   ```

### Rollback Plan

If issues are discovered post-deployment:

1. **Stop Services**
   ```bash
   # Kill running MCP or HTTP servers
   pkill -f "pcortex mcp"
   pkill -f "pcortex serve"
   ```

2. **Restore Previous Version**
   ```bash
   # Reinstall previous version
   pip install prometh-cortex==0.1.3

   # Restore backed-up indexes
   rm -rf $RAG_INDEX_DIR
   mv $RAG_INDEX_DIR.backup $RAG_INDEX_DIR
   ```

3. **Restart Services**
   ```bash
   # Start with previous configuration
   pcortex mcp  # or pcortex serve
   ```

4. **Verify Functionality**
   - Test basic query operations
   - Verify index loads correctly
   - Check MCP/HTTP endpoints respond

### Monitoring and Validation

Post-deployment monitoring:

- **Health Checks**: Monitor `/prometh_cortex_health` endpoint
- **Query Performance**: Track query response times (target <300ms)
- **Error Rates**: Monitor logs for indexing or query errors
- **Resource Usage**: Track memory and CPU utilization
- **Collection Metrics**: Monitor document counts per collection

### Migration Guide for Existing Users

**For users with existing single-collection indexes:**

Option 1: Continue with single-collection mode (no changes required)
- Existing configuration works as-is (backward compatible)
- No migration needed

Option 2: Migrate to multi-collection mode
1. Backup existing index
2. Add multi-collection configuration to `.env`
3. Run `pcortex rebuild --force` to reindex with new structure
4. Update query commands to use collection parameters (optional)

---

## Risk Assessment and Mitigation

### Technical Risks

**Risk 1: Breaking Changes for Existing Users**
- **Probability**: Medium
- **Impact**: High
- **Mitigation**:
  - Implement factory pattern for backward compatibility
  - Default to single-collection mode when `RAG_COLLECTIONS` not configured
  - Extensive regression testing
  - Clear migration documentation
- **Contingency**: Rollback plan with version downgrade instructions

**Risk 2: Performance Degradation with Multiple Collections**
- **Probability**: Medium
- **Impact**: Medium
- **Mitigation**:
  - Implement lazy loading for collection instances
  - Use concurrent querying for cross-collection searches
  - Optimize index loading with caching
  - Load testing with realistic data volumes
- **Contingency**: Add configuration option to disable lazy loading if issues arise

**Risk 3: Configuration Complexity**
- **Probability**: High
- **Impact**: Medium
- **Mitigation**:
  - Comprehensive validation with clear error messages
  - Provide example configurations for common scenarios
  - Add `pcortex config --sample-collections` command
  - Detailed documentation with troubleshooting guide
- **Contingency**: Support single-collection mode as simpler alternative

**Risk 4: Index Storage Size Increase**
- **Probability**: Low
- **Impact**: Low
- **Mitigation**:
  - Monitor storage usage during testing
  - Document expected storage requirements
  - Implement index cleanup utilities if needed
- **Contingency**: Add compression options for index storage

### Operational Risks

**Risk 5: Migration Errors During Deployment**
- **Probability**: Medium
- **Impact**: High
- **Mitigation**:
  - Require explicit backup before rebuilding
  - Provide automated backup script
  - Test migration process in staging environment
  - Clear rollback instructions
- **Contingency**: Restore from backup and downgrade version

**Risk 6: Documentation Gaps**
- **Probability**: Low
- **Impact**: Medium
- **Mitigation**:
  - Comprehensive documentation review
  - Example configurations for all use cases
  - FAQ section for common issues
  - Video tutorial for complex configurations
- **Contingency**: Rapid documentation updates based on user feedback

---

## Appendix

### Example Configurations

#### Basic Multi-Collection Setup
```bash
# .env configuration for 3 collections
RAG_COLLECTIONS='docs,meetings,tasks'

RAG_SOURCE_COLLECTION_MAP='{
  "docs": "docs",
  "meetings": "meetings",
  "todos": "tasks"
}'

RAG_COLLECTION_PARAMS='{
  "docs": {"chunk_size": 512, "chunk_overlap": 50},
  "meetings": {"chunk_size": 256, "chunk_overlap": 25},
  "tasks": {"chunk_size": 128, "chunk_overlap": 10}
}'
```

#### Advanced Multi-Collection with Git Logs
```bash
# .env configuration for 4 collections including git logs
RAG_COLLECTIONS='knowledge_base,meetings,activity_logs,asset_logs'

RAG_SOURCE_COLLECTION_MAP='{
  "docs/specs": "knowledge_base",
  "docs/prds": "knowledge_base",
  "meetings": "meetings",
  "todos": "activity_logs",
  "reminders": "activity_logs",
  ".git/logs": "asset_logs"
}'

RAG_COLLECTION_PARAMS='{
  "knowledge_base": {"chunk_size": 512, "chunk_overlap": 50},
  "meetings": {"chunk_size": 256, "chunk_overlap": 25},
  "activity_logs": {"chunk_size": 128, "chunk_overlap": 10},
  "asset_logs": {"chunk_size": 384, "chunk_overlap": 30}
}'
```

### CLI Usage Examples

```bash
# Build indexes with multi-collection configuration
pcortex build --force

# Query specific collection
pcortex query "authentication flow" --collection knowledge_base

# Query all collections
pcortex query "team decisions" --all-collections

# Query multiple specific collections
pcortex query "recent tasks" --collections activity_logs,meetings --max-results 10

# Start MCP server with multi-collection support
pcortex mcp

# Start HTTP server with multi-collection support
pcortex serve
```

### API Examples

#### HTTP API Request
```bash
curl -X POST http://localhost:8080/prometh_cortex_query \
  -H "Authorization: Bearer test-token-123" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication implementation",
    "collection": "knowledge_base",
    "max_results": 5
  }'
```

#### MCP Tool Usage (in Claude Desktop)
```
Use the prometh_cortex_query tool to search for "authentication" in the knowledge_base collection.
```

### Performance Benchmarks

Expected performance targets:
- **Indexing**: 50-100 documents/second per collection
- **Query Response**: <300ms for single-collection queries
- **Cross-Collection Query**: <500ms for 4 collections
- **Memory Usage**: ~200MB per collection with 500 documents
- **Index Size**: ~5MB per 100 documents

### References

- **LlamaIndex Documentation**: https://docs.llamaindex.ai/
- **FAISS Documentation**: https://github.com/facebookresearch/faiss
- **FastMCP Documentation**: https://github.com/jlowin/fastmcp
- **Sentence Transformers**: https://www.sbert.net/

---

**Document End**
