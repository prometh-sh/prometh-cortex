# Feature Specification: Qdrant Vector Store Integration

**Document**: `feature-qdrant-vector-store-integration-spec.md`  
**Version**: 1.0  
**Date**: 2025-01-24  
**Status**: Draft  
**Priority**: High  
**Estimated Effort**: 8-12 story points  

## Executive Summary

Integrate Qdrant vector database as an alternative to the current FAISS-based local indexing in Prometh-Cortex, providing users with a choice between local file-based indexing and cloud-native vector database storage. This enhancement will support both Docker-containerized and cloud-hosted Qdrant deployments through environment-based configuration.

## User Story

**As a** Prometh-Cortex user  
**I want** to choose between local FAISS indexing and Qdrant vector database storage  
**So that** I can scale my RAG system to handle larger document collections and benefit from distributed vector search capabilities  

## Business Context

### Problem Statement
- Current FAISS implementation is limited to local storage and single-machine scaling
- Users need cloud-native vector database options for production deployments
- Large document collections (1000+ files) require more scalable vector storage solutions
- Team collaboration requires shared vector indexes accessible across multiple environments

### Business Value
- **Scalability**: Support for larger document collections without local storage limitations
- **Collaboration**: Shared vector indexes accessible by multiple users/environments
- **Production Ready**: Cloud-native architecture suitable for enterprise deployments
- **Flexibility**: Choice between local development (FAISS) and production (Qdrant) storage

## Functional Requirements

### FR-1: Dual Vector Store Architecture
- **Description**: Implement abstracted vector store interface supporting both FAISS and Qdrant
- **Priority**: Must Have
- **Acceptance Criteria**:
  - [ ] Create `VectorStoreInterface` abstract base class
  - [ ] Implement `FAISSVectorStore` wrapper for existing functionality
  - [ ] Implement `QdrantVectorStore` for Qdrant integration
  - [ ] Vector store selection based on environment configuration
  - [ ] Seamless switching between stores without code changes

### FR-2: Environment-Based Configuration
- **Description**: Configure vector store type and connection through environment variables
- **Priority**: Must Have
- **Acceptance Criteria**:
  - [ ] `VECTOR_STORE_TYPE` environment variable (values: `faiss`, `qdrant`)
  - [ ] Qdrant-specific configuration variables:
    - [ ] `QDRANT_HOST` (default: localhost)
    - [ ] `QDRANT_PORT` (default: 6333)
    - [ ] `QDRANT_API_KEY` (optional for authentication)
    - [ ] `QDRANT_COLLECTION_NAME` (default: prometh-cortex)
    - [ ] `QDRANT_USE_HTTPS` (default: false)
  - [ ] Backward compatibility with existing `RAG_INDEX_DIR` for FAISS mode
  - [ ] Configuration validation with clear error messages

### FR-3: Qdrant Collection Management
- **Description**: Automatic collection creation and management in Qdrant
- **Priority**: Must Have
- **Acceptance Criteria**:
  - [ ] Auto-create collection if it doesn't exist
  - [ ] Configure collection with appropriate vector dimensions (384 for all-MiniLM-L6-v2)
  - [ ] Set up collection with metadata filtering capabilities
  - [ ] Collection health checks and connection validation
  - [ ] Collection reset/rebuild functionality

### FR-4: Document Indexing in Qdrant
- **Description**: Index documents with vectors and metadata in Qdrant
- **Priority**: Must Have
- **Acceptance Criteria**:
  - [ ] Store document vectors with unique IDs
  - [ ] Index document metadata (file_path, title, tags, created_date, etc.)
  - [ ] Support for batch indexing operations
  - [ ] Progress tracking for large document collections
  - [ ] Duplicate document handling and updates

### FR-5: Vector Search in Qdrant
- **Description**: Implement semantic search using Qdrant's vector similarity search
- **Priority**: Must Have
- **Acceptance Criteria**:
  - [ ] Vector similarity search with configurable top_k results
  - [ ] Metadata filtering capabilities (by tags, date ranges, file types)
  - [ ] Search result scoring and ranking
  - [ ] Search performance optimization
  - [ ] Error handling for connection failures

### FR-6: Docker Integration
- **Description**: Provide simple Docker setup for local Qdrant development
- **Priority**: Should Have
- **Acceptance Criteria**:
  - [ ] Simple `docker run` command for Qdrant service
  - [ ] Persistent volume configuration for daily use
  - [ ] Documentation for Docker setup and persistent storage
  - [ ] Connection validation and troubleshooting guide

### FR-7: MCP Server Integration
- **Description**: Ensure MCP server works with both vector store types
- **Priority**: Must Have
- **Acceptance Criteria**:
  - [ ] MCP tools work with Qdrant vector store
  - [ ] Health check reports vector store type and status
  - [ ] Query tool handles both storage backends transparently
  - [ ] Configuration passed through environment variables in MCP clients
  - [ ] Error handling for Qdrant connection issues

### FR-8: Incremental Indexing
- **Description**: Only index new and modified documents, avoiding full re-indexing for daily usage
- **Priority**: Must Have
- **Acceptance Criteria**:
  - [ ] Document change detection based on modification timestamps
  - [ ] File hash comparison to detect content changes
  - [ ] Maintain metadata index of processed documents
  - [ ] Add new documents without rebuilding entire index
  - [ ] Update modified documents (remove old + add new vector)
  - [ ] Remove deleted documents from vector store
  - [ ] `pcortex build` performs incremental updates by default
  - [ ] `pcortex rebuild` forces full re-indexing when needed
  - [ ] Progress reporting for incremental operations
  - [ ] Rollback capability if incremental update fails

### FR-9: Persistent Storage
- **Description**: Ensure vector indexes survive service restarts for daily usage workflows
- **Priority**: Must Have
- **Acceptance Criteria**:
  - [ ] Qdrant data persists across container restarts
  - [ ] FAISS index files preserved in configured directory
  - [ ] Index metadata and change tracking survives restarts
  - [ ] Data integrity validation on startup
  - [ ] Recovery procedures for corrupted indexes
  - [ ] Backup and restore documentation

## Technical Requirements

### TR-1: Dependencies
- **Description**: Add required Python packages for Qdrant integration
- **Priority**: Must Have
- **Dependencies**:
  ```python
  qdrant-client>=1.7.0
  ```

### TR-2: Architecture Pattern
- **Description**: Implement Strategy Pattern for vector store abstraction
- **Priority**: Must Have
- **Components**:
  - `VectorStoreInterface` (Abstract Base Class)
  - `FAISSVectorStore` (Current implementation wrapper)
  - `QdrantVectorStore` (New Qdrant implementation)
  - `VectorStoreFactory` (Factory for store selection)

### TR-3: Configuration Schema
- **Description**: Extended environment configuration schema
- **Priority**: Must Have
- **Configuration**:
  ```bash
  # Vector Store Configuration
  VECTOR_STORE_TYPE=qdrant  # or 'faiss'
  
  # Qdrant Configuration (when VECTOR_STORE_TYPE=qdrant)
  QDRANT_HOST=localhost
  QDRANT_PORT=6333
  QDRANT_API_KEY=optional-api-key
  QDRANT_COLLECTION_NAME=prometh-cortex
  QDRANT_USE_HTTPS=false
  
  # Backward compatibility (when VECTOR_STORE_TYPE=faiss)
  RAG_INDEX_DIR=/path/to/local/index
  ```

### TR-4: Data Migration
- **Description**: Support for migrating between vector store types
- **Priority**: Could Have
- **Requirements**:
  - Export from FAISS to Qdrant
  - Export from Qdrant to FAISS
  - Metadata preservation during migration
  - Validation of migrated data

## Implementation Plan

### Phase 1: Core Architecture (Week 1-2)
1. **Create vector store abstraction layer**
   - [ ] Define `VectorStoreInterface` with incremental operations
   - [ ] Implement `FAISSVectorStore` wrapper with change tracking
   - [ ] Create `VectorStoreFactory`
   - [ ] Update configuration system

2. **Basic Qdrant integration**
   - [ ] Add qdrant-client dependency
   - [ ] Implement basic `QdrantVectorStore`
   - [ ] Connection management and health checks
   - [ ] Collection creation and configuration

3. **Incremental indexing foundation**
   - [ ] Design document change detection system
   - [ ] Implement file modification tracking
   - [ ] Create index metadata persistence
   - [ ] File hash computation for content changes

### Phase 2: Indexing and Search (Week 3)
4. **Document indexing with incremental support**
   - [ ] Implement incremental batch operations
   - [ ] Document add/update/delete operations
   - [ ] Metadata extraction and storage
   - [ ] Progress tracking and error handling
   - [ ] Update CLI build commands for incremental mode

5. **Search functionality**
   - [ ] Vector similarity search implementation
   - [ ] Metadata filtering capabilities
   - [ ] Result formatting and scoring
   - [ ] Update CLI query commands

### Phase 3: Integration and Production Features (Week 4)
6. **MCP server integration**
   - [ ] Update MCP server to use new vector store interface
   - [ ] Environment configuration in MCP clients
   - [ ] Health check updates with incremental status
   - [ ] Error handling for both store types

7. **Persistent storage and Docker setup**
   - [ ] Simple Docker run commands with persistent volumes
   - [ ] Update README with Qdrant setup instructions
   - [ ] Migration documentation between FAISS and Qdrant
   - [ ] Performance comparison documentation
   - [ ] Backup and recovery procedures

## API Design

### Vector Store Interface
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

@dataclass
class DocumentChange:
    """Represents a document change for incremental indexing"""
    file_path: str
    change_type: str  # 'add', 'update', 'delete'
    file_hash: Optional[str] = None
    modified_time: Optional[float] = None

class VectorStoreInterface(ABC):
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the vector store connection and setup"""
        pass
    
    @abstractmethod
    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents with vectors and metadata"""
        pass
    
    @abstractmethod
    def update_document(self, document_id: str, document: Dict[str, Any]) -> None:
        """Update a single document by ID"""
        pass
    
    @abstractmethod
    def delete_document(self, document_id: str) -> None:
        """Delete a single document by ID"""
        pass
    
    @abstractmethod
    def document_exists(self, document_id: str) -> bool:
        """Check if a document exists in the index"""
        pass
    
    @abstractmethod
    def get_indexed_documents(self) -> Set[str]:
        """Get set of all indexed document IDs/paths"""
        pass
    
    @abstractmethod
    def get_document_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific document"""
        pass
    
    @abstractmethod
    def apply_incremental_changes(self, changes: List[DocumentChange]) -> Dict[str, int]:
        """Apply incremental changes and return stats"""
        pass
    
    @abstractmethod
    def query(self, 
             query_vector: List[float], 
             top_k: int = 10,
             filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for similar vectors with optional metadata filters"""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics and health info"""
        pass
    
    @abstractmethod
    def delete_collection(self) -> None:
        """Delete the entire collection/index"""
        pass
    
    @abstractmethod
    def backup_metadata(self, backup_path: str) -> None:
        """Backup index metadata for recovery"""
        pass
    
    @abstractmethod
    def restore_metadata(self, backup_path: str) -> None:
        """Restore index metadata from backup"""
        pass
```

### Incremental Indexing System
```python
from typing import Dict, List, Set
import hashlib
import os
from pathlib import Path

class DocumentChangeDetector:
    """Detects changes in document collection for incremental indexing"""
    
    def __init__(self, index_metadata_path: str):
        self.metadata_path = Path(index_metadata_path)
        self.indexed_docs: Dict[str, Dict] = self._load_metadata()
    
    def detect_changes(self, document_paths: List[str]) -> List[DocumentChange]:
        """Compare current documents with indexed metadata to detect changes"""
        changes = []
        current_docs = set(document_paths)
        indexed_docs = set(self.indexed_docs.keys())
        
        # New documents
        for doc_path in current_docs - indexed_docs:
            changes.append(DocumentChange(
                file_path=doc_path,
                change_type='add',
                file_hash=self._compute_file_hash(doc_path),
                modified_time=os.path.getmtime(doc_path)
            ))
        
        # Deleted documents
        for doc_path in indexed_docs - current_docs:
            changes.append(DocumentChange(
                file_path=doc_path,
                change_type='delete'
            ))
        
        # Modified documents
        for doc_path in current_docs & indexed_docs:
            current_hash = self._compute_file_hash(doc_path)
            indexed_hash = self.indexed_docs[doc_path].get('file_hash')
            current_mtime = os.path.getmtime(doc_path)
            indexed_mtime = self.indexed_docs[doc_path].get('modified_time', 0)
            
            if current_hash != indexed_hash or current_mtime > indexed_mtime:
                changes.append(DocumentChange(
                    file_path=doc_path,
                    change_type='update',
                    file_hash=current_hash,
                    modified_time=current_mtime
                ))
        
        return changes
    
    def update_metadata(self, changes: List[DocumentChange]) -> None:
        """Update metadata after successful indexing"""
        for change in changes:
            if change.change_type == 'delete':
                self.indexed_docs.pop(change.file_path, None)
            else:
                self.indexed_docs[change.file_path] = {
                    'file_hash': change.file_hash,
                    'modified_time': change.modified_time,
                    'indexed_at': time.time()
                }
        self._save_metadata()
    
    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file content"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _load_metadata(self) -> Dict[str, Dict]:
        """Load existing index metadata"""
        if self.metadata_path.exists():
            import json
            with open(self.metadata_path, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_metadata(self) -> None:
        """Save index metadata"""
        import json
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_path, 'w') as f:
            json.dump(self.indexed_docs, f, indent=2)
```

### Configuration Updates
```python
# config/settings.py additions
class Config(BaseModel):
    # Existing fields...
    
    # Vector Store Configuration
    vector_store_type: str = Field(default="faiss", description="Vector store type: 'faiss' or 'qdrant'")
    
    # Qdrant Configuration
    qdrant_host: str = Field(default="localhost", description="Qdrant server host")
    qdrant_port: int = Field(default=6333, description="Qdrant server port")
    qdrant_api_key: Optional[str] = Field(default=None, description="Qdrant API key")
    qdrant_collection_name: str = Field(default="prometh-cortex", description="Qdrant collection name")
    qdrant_use_https: bool = Field(default=False, description="Use HTTPS for Qdrant connection")
```

## Configuration Examples

### Local Development with Docker
```bash
# .env
VECTOR_STORE_TYPE=qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=prometh-cortex-dev
```

### Cloud Deployment
```bash
# .env
VECTOR_STORE_TYPE=qdrant
QDRANT_HOST=your-qdrant-cluster.com
QDRANT_PORT=443
QDRANT_API_KEY=your-api-key-here
QDRANT_COLLECTION_NAME=prometh-cortex-prod
QDRANT_USE_HTTPS=true
```

### Backward Compatibility (FAISS)
```bash
# .env
VECTOR_STORE_TYPE=faiss
RAG_INDEX_DIR=/path/to/index/storage
```

## Docker Setup for Qdrant

### Local Development with Docker

**Start Qdrant with persistent storage (recommended for daily use):**
```bash
docker run -d --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

**Alternative: Temporary Qdrant for testing:**
```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

**Manage the container:**
```bash
# Stop Qdrant
docker stop qdrant

# Start existing Qdrant container
docker start qdrant

# View logs
docker logs qdrant

# Remove container (data in named volume persists)
docker rm qdrant
```

## Testing Strategy

### Unit Tests
- [ ] Vector store interface implementations
- [ ] Configuration validation
- [ ] Connection management
- [ ] Document indexing and retrieval
- [ ] Error handling scenarios

### Integration Tests  
- [ ] End-to-end indexing with Qdrant
- [ ] Search functionality across store types
- [ ] MCP server with both vector stores
- [ ] Docker container integration
- [ ] Configuration switching

### Performance Tests
- [ ] Indexing performance comparison (FAISS vs Qdrant)
- [ ] Query latency benchmarks
- [ ] Memory usage analysis
- [ ] Scalability testing with large document sets

## Documentation Requirements

### User Documentation
- [ ] Update README with Qdrant setup instructions
- [ ] Docker Compose usage guide
- [ ] Configuration reference
- [ ] Migration guide between vector stores
- [ ] Troubleshooting guide

### Developer Documentation
- [ ] Architecture decision record (ADR) for vector store abstraction
- [ ] API documentation for new interfaces
- [ ] Performance benchmarking results
- [ ] Contribution guidelines for vector store implementations

## Expected User Workflow

### Daily Usage Pattern
```bash
# Initial setup (one time)
pcortex build  # Full indexing of all documents

# Daily workflow
# 1. Create new meeting notes, project docs, etc.
# 2. Quick incremental update
pcortex build  # Only processes new/changed documents (fast!)

# Weekly/monthly maintenance  
pcortex rebuild  # Full rebuild if needed (slower)
```

### Performance Expectations
- **Initial Build**: 345 documents ~2-3 minutes (full processing)
- **Daily Incremental**: 1-5 new documents ~5-15 seconds  
- **Weekly Incremental**: 10-20 changed documents ~30-60 seconds
- **Query Performance**: Maintained <300ms regardless of vector store type

## Success Criteria

### Primary Success Metrics
- [ ] Users can successfully switch between FAISS and Qdrant through configuration
- [ ] Qdrant integration maintains query performance within 10% of FAISS performance  
- [ ] MCP server works transparently with both vector store types
- [ ] Docker setup provides working Qdrant environment with single command
- [ ] Incremental indexing reduces daily build time by >90%
- [ ] Persistent storage maintains indexes across service restarts

### Secondary Success Metrics
- [ ] Documentation enables users to set up Qdrant in <15 minutes
- [ ] Zero breaking changes to existing FAISS users
- [ ] Configuration validation prevents common setup errors
- [ ] Migration tools enable seamless transitions between store types
- [ ] Change detection accuracy >99% (no missed updates or false positives)
- [ ] Rollback capability works within 30 seconds of failure

## Risks and Mitigations

### Technical Risks
1. **Performance Degradation**: Qdrant queries slower than FAISS
   - *Mitigation*: Benchmark and optimize query patterns, implement connection pooling

2. **Configuration Complexity**: Too many new environment variables
   - *Mitigation*: Provide sensible defaults, comprehensive documentation, validation

3. **Network Dependencies**: Qdrant connection failures
   - *Mitigation*: Robust error handling, connection retry logic, health checks

### Operational Risks
1. **Docker Setup Complexity**: Users struggle with containerized setup
   - *Mitigation*: Provide Docker Compose, clear documentation, troubleshooting guide

2. **Migration Data Loss**: Issues when switching between vector stores
   - *Mitigation*: Thorough testing, backup recommendations, rollback procedures

## Future Considerations

### Potential Enhancements
- Support for additional vector databases (Weaviate, Pinecone)
- Multi-tenant collection support
- Vector store clustering and replication
- Advanced filtering and search capabilities
- Real-time document updates and synchronization

### Scalability Considerations
- Connection pooling for high-throughput scenarios
- Distributed indexing for very large document collections
- Caching layers for frequently accessed vectors
- Monitoring and alerting for vector store health

---

**Stakeholders**: Product Owner, Development Team, DevOps Team  
**Next Review Date**: 2025-01-31  
**Approval Required**: Technical Lead, Product Owner