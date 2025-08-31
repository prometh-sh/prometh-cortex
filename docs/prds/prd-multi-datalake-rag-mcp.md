# Product Requirements Document (PRD)

## Title
**Multi-Datalake RAG Indexer with Local MCP Integration**

## Author
Ivan Nagy

## Created
2025-08-23

## Status
Draft – Internal Use (Preparation for Open Source Release)

---

## 1. Overview

This project aims to build a local-first, extensible, and developer-friendly system to index one or more datalake repositories and expose their content for retrieval-augmented generation (RAG) workflows. The system must be configurable using environment files and include a local MCP (Modular Command Processor) server to support integration with tools like Claude, Perplexity, or VSCode chat extensions.

---

## 2. Problem Statement

Ivan Nagy manages a structured collection of Markdown notes, reminders, and documents exported from Apple Notes, Obsidian, and other sources. Current solutions do not:

- Support multiple datalake sources easily.
- Allow clean and portable configuration via `.env` or `.envrc`.
- Provide local RAG index consumption with flexibility for different chat agents.
- Enable developer testing and open-source readiness from the beginning.

---

## 3. Goals

- ✅ Support multiple datalake repositories.
- ✅ Allow easy configuration via `.env` / `.envrc`.
- ✅ Build a local RAG index from Markdown files.
- ✅ Expose RAG index through a local MCP server.
- ✅ Prepare codebase and architecture for future open-source release.

---

## 4. Scope

### Must-Have
- Support for multiple datalake paths (`data/notes`, `data/todos`, `data/documents`, etc.)
- Configuration through `.env` or `.envrc` for:
  - Paths to datalake(s)
  - Local RAG index directory
  - MCP server port and auth
- CLI commands to:
  - Index a new datalake repo
  - Rebuild indexes
  - Serve local MCP server
- MCP server that exposes:
  - `/prometh_cortex_query` endpoint (RAG-like search interface)
  - `/prometh_cortex_health` endpoint
- Markdown-compatible frontmatter parsing
- Ability to add semantic search using local embeddings (e.g., `llama-index`, `sentence-transformers`)

### Out of Scope
- Cloud-based RAG pipelines

---

## 5. Architecture

```ascii
+---------------------+
|  .env/.envrc config |
+---------------------+
           |
+---------------------------+
| Datalake Ingest & Parser  |
| - Markdown files          |
| - YAML frontmatter        |
+---------------------------+
           |
+---------------------------+
| Vector Store / Indexing   |
| - LlamaIndex / FAISS      |
| - Local embedding model   |
+---------------------------+
           |
+---------------------------+
|     MCP Local Server      |
| - /query, /health         |
| - For Claude, VSCode,     |
|   Perplexity integrations |
+---------------------------+
```

---

## 6. Configuration

Sample `.env` file:

```bash
# Datalake paths (comma-separated if multiple)
DATALAKE_REPOS=./data/notes,./data/documents

# Index output path
RAG_INDEX_DIR=.rag_index

# MCP server
MCP_PORT=8080
MCP_AUTH_TOKEN=your_local_token
```

Sample `.envrc`:

```bash
use dotenv
layout python
```

---

## 7. CLI Commands

```bash
# Build index
$ pcortex build

# Rebuild all indexes
$ pcortex rebuild

# Start MCP server
$ pcortex serve

# Query locally (e.g., test prompt)
$ pcortex query "What did I discuss about DCoE last week?"
```

---

## 8. Open Source Preparation

### License
Apache 2.0 (TBD)

### Planned Releases
- **v0.1.0 (Private Testing):** local support, datalake repo
- **v0.2.0 (Internal Multi-repo + Refactor)**
- **v1.0.0 (Public OSS)**

---

## 9. Success Criteria

| Metric                          | Goal                              |
|---------------------------------|-----------------------------------|
| Index multiple datalake repos   | ✅ Works via `.env` config         |
| RAG query speed (local)         | < 100ms per query (on M1/M2 Mac)  |
| Claude/VSCode integration       | ✅ Accepts MCP calls               |
| OSS Readiness                   | 🟡 Code linted, structured, tested |

---

## 10. Risks & Considerations

| Risk                                 | Severity | Mitigation                                 |
|--------------------------------------|----------|---------------------------------------------|
| Poor performance with large indexes  | High     | Use chunked indexing + FAISS                |
| Misconfigurations in `.env`          | Medium   | Add schema validator & fallback defaults    |
| Tooling compatibility (Claude, etc.) | Medium   | Follow MCP interface standards              |
| Unstructured Markdown                | Medium   | Require frontmatter + fallback strategies   |
