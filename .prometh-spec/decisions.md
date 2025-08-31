# Multi-Datalake RAG Indexer - Technical Decisions

## Architecture Decisions

### ADR-001: Local-First RAG Architecture
**Date:** 2025-08-23
**Status:** Proposed
**Decision:** Build local-first system with no cloud dependencies for core functionality
**Rationale:** Ensures privacy, reduces latency, and provides full control over data processing
**Consequences:** Higher local resource requirements, need for efficient local embeddings

### ADR-002: MCP Protocol for Integration
**Date:** 2025-08-23
**Status:** Proposed  
**Decision:** Use MCP (Modular Command Processor) protocol for chat tool integrations
**Rationale:** Standardized interface for Claude, VSCode, and other tools
**Consequences:** Need to follow MCP specifications exactly for compatibility

### ADR-003: Configuration via .env/.envrc
**Date:** 2025-08-23
**Status:** Proposed
**Decision:** Use dotenv pattern for configuration with .envrc support
**Rationale:** Developer-friendly, portable, works with direnv tooling
**Consequences:** Need robust validation and fallback mechanisms

### ADR-004: LlamaIndex + FAISS for Vector Store
**Date:** 2025-08-23
**Status:** Proposed
**Decision:** Use LlamaIndex framework with FAISS backend for vector operations
**Rationale:** Mature ecosystem, good performance, local-first capability
**Consequences:** Dependency on these specific libraries, need to handle version updates

### ADR-005: CLI-First Interface
**Date:** 2025-08-23
**Status:** Proposed
**Decision:** Primary interface via `ragindex` CLI commands (build, rebuild, serve, query)
**Rationale:** Developer-friendly, scriptable, clear separation of concerns
**Consequences:** Need comprehensive CLI help and error handling

### ADR-006: MCP Timeout Handling Strategy  
**Date:** 2025-08-31
**Status:** Proposed
**Decision:** Implement multi-layered timeout handling: progress notifications, chunked processing, async operations, and client configuration
**Rationale:** MCP error 32001 (request timeout) prevents reliable operation with large document sets; need comprehensive solution addressing all timeout scenarios
**Consequences:** Increased complexity but significantly improved reliability for long-running operations
**Reference:** https://mcpcat.io/guides/fixing-mcp-error-32001-request-timeout/

**Last Updated:** 2025-08-31