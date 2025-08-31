# Feature Specification: Multi-Datalake RAG Indexer with Local MCP Integration

**Document Date:** 2025-08-23  
**Specification Type:** New Feature Implementation  
**Output Style:** prometh-spec-feature  
**Source:** docs/prds/prd-multi-datalake-rag-mcp.md

---

## 1. Feature Summary

**Business Value:** Enable developers to efficiently index and query multiple datalake repositories of Markdown content through a local RAG system with MCP server integration for Claude, VSCode, and other chat tools.

**Problem Statement:** Current solutions lack support for multiple datalake sources with portable configuration and local RAG consumption flexibility for different chat agents while maintaining open-source readiness.

**Success Metrics:**
- Index multiple datalake repos via `.env` config: ✅ Target
- RAG query speed: <100ms on M1/M2 Mac
- Claude/VSCode integration: ✅ MCP compatibility 
- OSS readiness: Linted, structured, tested codebase

## 2. User Stories

### Primary Persona: Developer (Ivan Nagy)
**Context:** Manages structured Markdown notes from Apple Notes, Obsidian, and other sources

#### Epic 1: Multi-Datalake Configuration
**Priority:** Must-have

- **US-001:** As a developer, I want to configure multiple datalake paths via `.env` file so that I can index different content repositories (notes, documents, todos)
  - **AC:** Support comma-separated paths in `DATALAKE_REPOS=./data/notes,./data/documents`
  - **AC:** Validate paths exist and are readable
  - **AC:** Support both absolute and relative paths

- **US-002:** As a developer, I want to use `.envrc` with direnv so that my environment is automatically configured per project
  - **AC:** Support `use dotenv` and `layout python` in .envrc
  - **AC:** Environment variables loaded automatically when entering directory

#### Epic 2: Content Indexing
**Priority:** Must-have

- **US-003:** As a developer, I want to index Markdown files with YAML frontmatter so that metadata and content are both searchable
  - **AC:** Parse YAML frontmatter correctly
  - **AC:** Extract and index both metadata and body content
  - **AC:** Handle malformed frontmatter gracefully

- **US-004:** As a developer, I want CLI commands to manage indexing so that I can build, rebuild, and maintain my RAG index
  - **AC:** `pcortex build` creates initial index
  - **AC:** `pcortex rebuild` recreates entire index
  - **AC:** Clear error messages for failures
  - **AC:** Progress indicators for long operations

#### Epic 3: RAG Query Interface
**Priority:** Must-have

- **US-005:** As a developer, I want a local MCP server so that I can integrate with Claude, VSCode, and other tools
  - **AC:** MCP server runs on configurable port (default 8080)
  - **AC:** `/prometh_cortex_query` endpoint accepts queries
  - **AC:** `/prometh_cortex_health` endpoint returns status
  - **AC:** Authentication via configurable token

- **US-006:** As a developer, I want to test queries locally so that I can validate my index before using with external tools
  - **AC:** `pcortex query "search term"` returns relevant results
  - **AC:** Results include source file references
  - **AC:** Query response time <100ms on M1/M2 Mac

#### Epic 4: Integration & Compatibility  
**Priority:** Should-have

- **US-007:** As a developer, I want Claude integration so that I can query my datalake through Claude chat
  - **AC:** Claude accepts MCP server connection
  - **AC:** Queries return contextually relevant results
  - **AC:** Source attribution included in responses

- **US-008:** As a developer, I want VSCode integration so that I can query my notes from my editor
  - **AC:** VSCode chat extension connects to MCP server
  - **AC:** Search results accessible within editor context

## 3. Technical Requirements

### Architecture Components

```ascii
+---------------------+
|  .env/.envrc config |
+---------------------+
           |
+---------------------------+
| Datalake Ingest & Parser |
| - Markdown files         |
| - YAML frontmatter       |
+---------------------------+
           |
+---------------------------+
| Vector Store / Indexing  |
| - LlamaIndex / FAISS     |
| - Local embedding model  |
+---------------------------+
           |
+---------------------------+
|     MCP Local Server     |
| - /prometh_cortex_query  |
| - /prometh_cortex_health |
+---------------------------+
```

### YAML RAG Formatting Sample

```yaml
---
title: Title of Document
created: YYYY-MM-DDTHH:MM:SS
author: Ivan Nagy
category: #Meetings
tags:
  - #RAG
focus: Work
uuid: 544725C9-45B2-4BDC-8BFD-D0BF485FEA65
project:
  - name: Project Name
    uuid: D86F080E-D47E-42C0-949A-737E85485FF2
reminder:
  - subject: Todo Item
    uuid: 741C071F-EC6A-4036-9A8C-23F80705A1D9
    list: Work
event:
  subject: Event Subject
  uuid: B897515C-1BE9-41B6-8423-3988BE0C9E3E:F042576B-4006-4EAF-975D-A4C0274FC8BA
  shortUUID: MF042576B
  created: YYYY-MM-DDTHH:MM:SS
  start: YYYY-MM-DDTHH:MM:SS
  end: YYYY-MM-DDTHH:MM:SS
  duration: HH:MM:SS
  organizer: Organizer Name
  attendees:
    - Attendee Name
  location: Location Name or Teams
related:
  - Related Item Name
---
```

### API Specifications

#### MCP Server Endpoints

**POST /prometh_corex_query**
```json
{
  "query": "search term or question",
  "max_results": 10,
  "filters": {
    "datalake": "notes",
    "tags": ["work", "project"]
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "content": "matching content snippet",
      "source_file": "path/to/source.md",
      "metadata": {"title": "Note Title", "tags": ["work"]},
      "similarity_score": 0.92
    }
  ],
  "query_time_ms": 45
}
```

**GET /prometh_cortex_health**
```json
{
  "status": "healthy",
  "indexed_files": 1250,
  "last_index_update": "2025-08-23T10:30:00Z",
  "uptime_seconds": 3600
}
```

### Configuration Requirements

**Environment Variables:**
```bash
# Required
DATALAKE_REPOS=./data/notes,./data/documents,./data/todos

# Optional with defaults
RAG_INDEX_DIR=.rag_index
MCP_PORT=8080
MCP_HOST=localhost
MCP_AUTH_TOKEN=auto_generated_if_empty
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
MAX_QUERY_RESULTS=10
```

### Integration Points

- **Claude:** MCP protocol compliance for chat integration
- **VSCode:** Extension compatibility via MCP server
- **Perplexity:** API compatibility (future enhancement)
- **LlamaIndex:** Vector store and embedding management  
- **FAISS:** Efficient similarity search backend

## 4. Implementation Plan

### Phase 1: Core Infrastructure (4-6 weeks)
**Dependencies:** Python 3.9+, Virtual environment setup

1. **Week 1-2: Configuration & Parsing**
   - Environment variable handling with validation
   - Markdown file discovery and parsing
   - YAML frontmatter extraction
   - Basic CLI structure (`pcortex --help`)

2. **Week 3-4: Vector Store Setup**
   - LlamaIndex integration  
   - FAISS backend configuration
   - Local embedding model setup
   - Basic indexing workflow (`pcortex build`)

### Phase 2: MCP Server (3-4 weeks)
**Dependencies:** Phase 1 completion, MCP protocol specs

1. **Week 5-6: Server Implementation**
   - HTTP server with FastAPI/Flask
   - `/prometh_cortex_query` endpoint
   - `/prometh_cortex_health` endpoint
   - Authentication middleware

2. **Week 7-8: Multi-repo Support**
   - Multiple datalake path handling
   - Index rebuilding (`pcortex rebuild`)
   - Server management (`pcortex serve`)

### Phase 3: Integration & OSS (4-5 weeks)
**Dependencies:** Phases 1-2, External tool access

1. **Week 9-10: Tool Integration**
   - Claude MCP connection testing
   - VSCode extension compatibility
   - Query performance optimization

2. **Week 11-12: OSS Preparation**
   - Code linting and formatting
   - Comprehensive testing suite
   - Documentation and examples
   - License and contribution guidelines

### Resource Requirements
- **Developer Time:** 12-15 weeks (full-time equivalent)
- **Hardware:** M1/M2 Mac for performance testing
- **External Dependencies:** Claude API access, VSCode with chat extension

## 5. Test Cases

### Unit Test Scenarios

**Configuration Tests:**
```python
def test_parse_multiple_datalake_paths():
    """Test parsing comma-separated datalake paths from .env"""
    os.environ['DATALAKE_REPOS'] = './data/notes,./data/docs'
    config = load_config()
    assert len(config.datalake_repos) == 2
    assert './data/notes' in config.datalake_repos

def test_invalid_datalake_path():
    """Test handling of non-existent datalake paths"""
    os.environ['DATALAKE_REPOS'] = './non-existent-path'
    with pytest.raises(ConfigValidationError):
        load_config()
```

**Parsing Tests:**
```python
def test_markdown_frontmatter_parsing():
    """Test YAML frontmatter extraction from Markdown"""
    content = """---
title: Test Note
tags: [work, project]
---
# Note Content
This is the body."""
    
    parsed = parse_markdown(content)
    assert parsed.frontmatter['title'] == 'Test Note'
    assert 'work' in parsed.frontmatter['tags']
    assert 'Note Content' in parsed.body
```

### Integration Test Cases

**MCP Server Tests:**
```python
def test_query_endpoint_response():
    """Test /prometh_cortex_query endpoint returns valid results"""
    response = requests.post('/prometh_cortex_query', json={
        'query': 'test content',
        'max_results': 5
    })
    assert response.status_code == 200
    data = response.json()
    assert 'results' in data
    assert 'query_time_ms' in data

def test_health_endpoint():
    """Test /prometh_cortex_health endpoint status"""
    response = requests.get('/prometh_cortex_health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'healthy'
    assert 'indexed_files' in data
```

### Performance Benchmarks

**Query Performance:**
- Target: <100ms average query response time
- Test with 1000+ indexed documents
- Measure on M1/M2 Mac hardware
- Include both simple and complex queries

**Indexing Performance:**
- Measure indexing time for varying dataset sizes
- Monitor memory usage during indexing
- Test rebuild performance vs incremental updates

### User Acceptance Test Criteria

**UAT-001: Multi-Datalake Setup**
- User configures 3 datalake directories in .env
- `pcortex build` successfully indexes all directories  
- Query returns results from all configured datalakes

**UAT-002: Claude Integration**
- MCP server starts and runs on configured port
- Claude connects to MCP server without errors
- User queries through Claude receive relevant results with source attribution

**UAT-003: Developer Workflow**
- User can build, query, and rebuild index via CLI
- Performance meets <100ms query requirement
- Server remains stable during extended use

## 6. Risk Assessment

### Technical Risks

| Risk | Severity | Probability | Mitigation Strategy |
|------|----------|-------------|-------------------|
| **Poor performance with large indexes** | High | Medium | Implement chunked indexing, FAISS optimization, index pruning strategies |
| **MCP protocol compatibility issues** | High | Low | Follow MCP specs exactly, comprehensive integration testing with target tools |
| **Local embedding model limitations** | Medium | Medium | Evaluate multiple models, provide model selection configuration option |
| **Memory consumption during indexing** | Medium | High | Implement streaming processing, configurable batch sizes, memory monitoring |

### Dependencies and Blockers

| Dependency | Risk Level | Mitigation |
|------------|------------|------------|
| **Claude MCP support** | Medium | Test with current Claude version, maintain compatibility layer |
| **VSCode chat extension** | Medium | Develop against stable extension version, provide fallback options |
| **LlamaIndex API stability** | Low | Pin version dependencies, monitor for breaking changes |
| **FAISS performance on Mac** | Low | Validate on target hardware early, have alternative backends ready |

### Success/Failure Criteria

**Success Indicators:**
- All user acceptance tests pass
- Query performance consistently <100ms
- Integration works with Claude and VSCode  
- Codebase passes OSS readiness checklist
- No critical security vulnerabilities

**Failure Indicators:**
- Query performance >200ms consistently
- Integration failures with primary tools
- Memory usage >2GB during normal operations
- Critical bugs affecting core functionality
- Unable to achieve OSS quality standards

**Go/No-Go Decision Points:**
- End of Phase 1: Core functionality working
- End of Phase 2: MCP server operational  
- End of Phase 3: Integration testing successful

---

## Implementation Status
**Current Phase:** Pre-Development  
**Next Action:** Begin Phase 1 - Core Infrastructure setup  
**Target Completion:** Q2 2025 (estimated 12-15 weeks development time)