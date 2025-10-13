# Prometh Cortex

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI version](https://img.shields.io/pypi/v/prometh-cortex.svg)](https://pypi.org/project/prometh-cortex/)
[![Python Support](https://img.shields.io/pypi/pyversions/prometh-cortex.svg)](https://pypi.org/project/prometh-cortex/)
[![Tests](https://github.com/ivannagy/prometh-cortex/actions/workflows/test.yml/badge.svg)](https://github.com/ivannagy/prometh-cortex/actions/workflows/test.yml)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Compatible-green.svg)](https://docs.anthropic.com/en/docs/claude-code)

Multi-Datalake RAG Indexer with Local MCP Integration

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Vector Store Configuration](#vector-store-configuration)
- [CLI Commands](#cli-commands)
- [Integration](#integration)
  - [Claude Desktop](#claude-desktop-integration)
  - [Perplexity](#perplexity-integration)
  - [VSCode](#vscode-with-github-copilot-integration)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Overview

Prometh Cortex is a local-first, extensible system for indexing multiple datalake repositories containing Markdown files and exposing their content for retrieval-augmented generation (RAG) workflows through a local MCP (Modular Command Processor) server.

## Features

- **Multi-Datalake Support**: Index multiple repositories of Markdown documents
- **YAML Frontmatter Parsing**: Rich metadata extraction with structured schema support
- **Dual Vector Store Support**: Choose between local FAISS or cloud-native Qdrant
- **Incremental Indexing**: Smart change detection for efficient updates
- **MCP Server**: Local server compatible with Claude, VSCode, and other tools
- **CLI Interface**: Easy-to-use command line tools for indexing and querying
- **Performance Optimized**: Target <100ms query response time on M1/M2 Mac

## Installation

### From PyPI (Recommended)

```bash
pip install prometh-cortex
```

### From Source (Development)

```bash
git clone https://github.com/ivannagy/prometh-cortex.git
cd prometh-cortex
pip install -e ".[dev]"
```

## Quick Start

1. **Install via pip**:
```bash
pip install prometh-cortex
```

2. **Initialize configuration** (creates `~/.config/prometh-cortex/config.toml`):
```bash
pcortex config --init
```

3. **Edit your config file**:
```bash
# macOS/Linux
nano ~/.config/prometh-cortex/config.toml

# Or use your preferred editor
# Update the [datalake] repos with your document paths
```

4. **Build index**:
```bash
pcortex build
```

5. **Query locally**:
```bash
pcortex query "search for something"
```

6. **Start servers**:
```bash
# For Claude Desktop (MCP protocol)
pcortex mcp

# For Perplexity/VSCode/HTTP integrations
pcortex serve
```

### Configuration File Locations

Prometh-cortex follows the XDG Base Directory Specification. Config files are searched in this order:

1. `./config.toml` - Current directory (highest priority)
2. `~/.config/prometh-cortex/config.toml` - XDG config directory (recommended)
3. `~/.prometh-cortex/config.toml` - Fallback location

**Useful commands**:
```bash
# Initialize config in XDG directory (recommended for system-wide use)
pcortex config --init

# Create sample config in current directory (for project-specific config)
pcortex config --sample

# Show all config search paths
pcortex config --show-paths
```

## Configuration

Create a `config.toml` file with your settings:

```bash
cp config.toml.sample config.toml
# Edit config.toml with your specific paths and settings
```

### Configuration Format (TOML)

```toml
[datalake]
# Add your document directories here
repos = [
    "/path/to/your/notes",
    "/path/to/your/documents", 
    "/path/to/your/projects"
]

[storage]
rag_index_dir = "/path/to/index/storage"

[server]
port = 8080
host = "localhost"
auth_token = "your-secure-token"

[embedding]
model = "sentence-transformers/all-MiniLM-L6-v2"
max_query_results = 10
chunk_size = 512
chunk_overlap = 50

[vector_store]
type = "faiss"  # or "qdrant"

# Qdrant configuration (when type = "qdrant")
[vector_store.qdrant]
host = "localhost"
port = 6333
collection_name = "prometh_cortex"
```

## Vector Store Configuration

Prometh Cortex supports two vector store backends:

### Option 1: FAISS (Default - Local Storage)

**Best for**: Local development, private deployments, no external dependencies

```toml
[vector_store]
type = "faiss"

[storage]
rag_index_dir = ".rag_index"
```

**Advantages**:
- ✅ No external dependencies
- ✅ Fast local queries
- ✅ Works offline
- ✅ Simple setup

**Disadvantages**:
- ❌ Limited to single machine
- ❌ No concurrent write access
- ❌ Manual backup required

### Option 2: Qdrant (Cloud-native Vector Database)

**Best for**: Production deployments, team collaboration, scalable solutions

#### Local Qdrant with Docker

```bash
# Start Qdrant container with persistent storage
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant

[vector_store]
type = "qdrant"

[vector_store.qdrant]
host = "localhost"
port = 6333
collection_name = "prometh_cortex"
```

#### Cloud Qdrant

```bash
[vector_store]
type = "qdrant"

[vector_store.qdrant]
host = "your-cluster.qdrant.io"
port = 6333
collection_name = "prometh_cortex"
api_key = "your-api-key-here"
use_https = true
```

**Advantages**:
- ✅ Concurrent access support
- ✅ Built-in clustering and replication
- ✅ Advanced filtering capabilities
- ✅ REST API access
- ✅ Automatic backups (cloud)
- ✅ Horizontal scaling

**Disadvantages**:
- ❌ Requires external service
- ❌ Network dependency
- ❌ Additional complexity

#### Qdrant Setup Steps

1. **Local Docker Setup**:
   ```bash
   # Create persistent storage directory
   mkdir -p qdrant_storage
   
   # Start Qdrant container
   docker run -d \
     --name qdrant \
     --restart unless-stopped \
     -p 6333:6333 \
     -p 6334:6334 \
     -v $(pwd)/qdrant_storage:/qdrant/storage \
     qdrant/qdrant
   
   # Verify Qdrant is running
   curl http://localhost:6333/health
   ```

2. **Configure Environment**:
   ```bash
# Add to your config.toml:
[vector_store]
type = "qdrant"

[vector_store.qdrant]
host = "localhost"
port = 6333
collection_name = "prometh_cortex"
# api_key = ""  # Optional for local Docker  
# use_https = false  # Default for local
   ```

3. **Build Index**:
   ```bash
   # Initial build or incremental update
   pcortex build
   
   # Force complete rebuild
   pcortex rebuild --confirm
   ```

4. **Verify Setup**:
   ```bash
   # Check health and statistics
   pcortex query "test" --max-results 1
   
   # Or directly check Qdrant
   curl http://localhost:6333/collections/prometh_cortex
   ```

#### Qdrant Cloud Setup

1. **Create Qdrant Cloud Account**:
   - Visit [Qdrant Cloud](https://qdrant.io/cloud/)
   - Create a cluster and get your credentials

2. **Configure Environment**:
   ```bash
# Add to your config.toml:
[vector_store]
type = "qdrant"

[vector_store.qdrant]
host = "your-cluster-id.qdrant.io"
port = 6333
collection_name = "prometh_cortex"
api_key = "your-api-key"
use_https = true
   ```

#### Migration Between Vector Stores

```bash
# Backup current index (if using FAISS)
pcortex build --backup /tmp/backup_$(date +%Y%m%d_%H%M%S)

# Change vector store type in config.toml
sed -i 's/type = "faiss"/type = "qdrant"/' config.toml

# Rebuild index with new vector store
pcortex rebuild --confirm

# Verify migration successful
pcortex query "test migration" --max-results 1
```

## CLI Commands

### Build Index
```bash
# Initial build (automatic incremental updates)
pcortex build

# Force complete rebuild (ignores incremental changes)
pcortex build --force

# Disable incremental indexing
pcortex build --no-incremental

# Rebuild entire index (with confirmation)
pcortex rebuild
pcortex rebuild --confirm  # Skip confirmation prompt
```

### Query Index
```bash
# Basic query
pcortex query "search term"

# Query with options
pcortex query "search term" --max-results 5 --show-content
```

### Start Servers

#### MCP Server (for Claude Desktop)
```bash
# Start MCP server with stdio protocol
pcortex mcp
```

#### HTTP Server (for web integrations)
```bash
# Start HTTP server (default: localhost:8080)
pcortex serve

# Custom host/port
pcortex serve --host 0.0.0.0 --port 9000

# Development mode with auto-reload
pcortex serve --reload
```

## Server Types

### MCP Protocol Server (`pcortex mcp`)
**For Claude Desktop integration**

Provides MCP tools via stdio transport:
- **prometh_cortex_query**: Search indexed documents
- **prometh_cortex_health**: Get system health status

### HTTP REST Server (`pcortex serve`)
**For Perplexity, VSCode, web integrations**

#### Query Endpoint
**POST** `/prometh_cortex_query`

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

#### Health Endpoint
**GET** `/prometh_cortex_health`

Returns server status, index statistics, and performance metrics.

## Supported YAML Frontmatter Schema

```yaml
---
title: Document Title
created: YYYY-MM-DDTHH:MM:SS
author: Author Name
category: #Category
tags:
  - #tag1
  - tag2
focus: Work
uuid: document-uuid
project:
  - name: Project Name
    uuid: project-uuid            # UUID preserved for document linking
reminder:
  - subject: Reminder Text
    uuid: reminder-uuid           # UUID preserved for document linking
    list: List Name
event:
  subject: Event Subject
  uuid: event-uuid                # UUID preserved for document linking
  shortUUID: MF042576B            # Short UUID also preserved
  organizer: Organizer Name
  attendees:
    - Attendee 1
    - Attendee 2
  location: Event Location
  start: YYYY-MM-DDTHH:MM:SS      # Event start time
  end: YYYY-MM-DDTHH:MM:SS        # Event end time
related:
  - Related Item 1
  - Related Item 2
---
```

**Note on UUIDs for Document Linking:**
- Project, reminder, and event UUIDs are **preserved** in vector store metadata
- These UUIDs enable cross-document linking and relationship queries
- Use these UUIDs to find related documents across your datalake
- Query by UUID: `event_uuid:B897515C-1BE9-41B6-8423-3988BE0C9E3E`

### YAML Frontmatter Best Practices

**⚠️ Important**: When using special characters in YAML values, always quote them properly to ensure correct parsing:

#### ✅ Correct Usage:
```yaml
---
title: "[PRJ-0119] Add New Feature"    # Quoted because of brackets
author: "John O'Connor"                # Quoted because of apostrophe
tags:
  - "C#"                               # Quoted because of hash symbol
  - "project-2024"                     # Safe without quotes
category: "Work & Personal"            # Quoted because of ampersand
---
```

#### ❌ Problematic Usage:
```yaml
---
title: [PRJ-0119] Add New Feature      # Brackets will cause parsing errors
author: John O'Connor                  # Apostrophe may cause issues
tags:
  - C#                                 # Hash symbol conflicts with YAML
category: Work & Personal              # Ampersand may cause issues  
---
```

#### Common Characters That Need Quoting:
- **Square brackets** `[]`: `title: "[PROJECT-123] Task Name"`
- **Curly braces** `{}`: `status: "{COMPLETED}"`
- **Hash/Pound** `#`: `tag: "C#"`
- **Colon** `:`: `note: "Time: 3:30 PM"`
- **Ampersand** `&`: `title: "Sales & Marketing"`
- **Asterisk** `*`: `priority: "*HIGH*"`
- **Pipe** `|`: `command: "grep | sort"`
- **Greater/Less than** `<>`: `comparison: "<100ms"`
- **At symbol** `@`: `email: "@company.com"`
- **Apostrophes** `'`: `name: "O'Connor"`

#### Why This Matters:
- **Metadata Parsing**: Improper YAML syntax prevents frontmatter from being extracted
- **Index Quality**: Missing metadata means poor search results and filtering
- **Qdrant Storage**: Malformed YAML leads to incomplete document payloads
- **Search Performance**: Documents without proper metadata are harder to find

#### Validation:
Test your YAML frontmatter before indexing:
```bash
# Quick validation of a document
python -c "
import yaml
import frontmatter

with open('your-document.md', 'r') as f:
    post = frontmatter.load(f)
    print('✅ YAML parsed successfully')
    print(f'Title: {post.metadata.get(\"title\", \"N/A\")}')
    print(f'Fields: {list(post.metadata.keys())}')
"
```

## Integration

### Claude Desktop Integration

Configure Claude Desktop by editing `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "prometh-cortex": {
      "command": "/path/to/your/project/.venv/bin/python",
      "args": [
        "-m", "prometh_cortex.cli.main", "mcp"
      ],
      "env": {
        "DATALAKE_REPOS": "/path/to/your/notes,/path/to/your/documents,/path/to/your/projects",
        "RAG_INDEX_DIR": "/path/to/index/storage",
        "MCP_PORT": "8080",
        "MCP_HOST": "localhost",
        "MCP_AUTH_TOKEN": "your-secure-token",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
        "MAX_QUERY_RESULTS": "10",
        "CHUNK_SIZE": "512",
        "CHUNK_OVERLAP": "50",
        "VECTOR_STORE_TYPE": "faiss"
      }
    }
  }
}
```

**Setup Steps**:

1. **Install in Virtual Environment**:
   ```bash
   cd /path/to/prometh-cortex
   python -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   pip install -e .
   ```

2. **Configure Settings**: Create and customize your configuration:
   ```bash
   # Create configuration file
   cp config.toml.sample config.toml
   
   # Edit config.toml with your specific paths and settings
   # Update the [datalake] repos array with your document directories
   # Set your preferred [storage] rag_index_dir location
   # Customize [server] auth_token for security
   ```

3. **Build your index**:
   ```bash
   source .venv/bin/activate
   pcortex build --force
   ```

4. **Get Absolute Paths**: Update the MCP configuration with your actual paths:
   ```bash
   # Get your virtual environment Python path
   which python  # While .venv is activated
   
   # Get your project directory
   pwd
   ```

5. **Update Claude Desktop Config**: Use absolute paths in your `claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "prometh-cortex": {
         "command": "/path/to/your/project/.venv/bin/python",
         "args": [
           "-m", "prometh_cortex.cli.main", "mcp"
         ],
         "env": {
           "DATALAKE_REPOS": "/path/to/your/notes,/path/to/your/documents,/path/to/your/projects",
           "RAG_INDEX_DIR": "/path/to/index/storage",
           "MCP_PORT": "8080",
           "MCP_HOST": "localhost",
           "MCP_AUTH_TOKEN": "your-secure-token",
           "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
           "MAX_QUERY_RESULTS": "10",
           "CHUNK_SIZE": "512",
           "CHUNK_OVERLAP": "50"
         }
       }
     }
   }
   ```

6. **Verify Configuration**:
   ```bash
   # Test MCP server manually
   source .venv/bin/activate
   pcortex mcp  # Should start without errors
   ```

7. **Restart Claude Desktop**: Completely quit and restart Claude Desktop application.

**Troubleshooting**:
- ✅ **Check Logs**: Look at Claude Desktop console logs for MCP connection errors
- ✅ **Verify Paths**: Ensure all paths in the config are absolute and correct
- ✅ **Test Index**: Run `pcortex query "test"` to verify your index works
- ✅ **Environment**: Make sure environment variables are accessible from the MCP context

**Usage**: After restarting Claude Desktop, you'll have access to these MCP tools:
- **prometh_cortex_query**: Search your indexed documents
  - Ask: "Search my notes for yesterday's meetings"
  - Ask: "Find documents about project planning" 
  - Ask: "What meetings did I have last week?"
- **prometh_cortex_health**: Check system status
  - Ask: "How many documents are indexed in prometh-cortex?"
  - Ask: "What's the health status of my knowledge base?"

### Claude.ai Web Integration

Configure Claude.ai to use your MCP server by adding it as a custom integration:

1. Start your MCP server: `pcortex serve`
2. Use the webhook URL: `http://localhost:8080/prometh_cortex_query`
3. Set authentication header: `Authorization: Bearer your-secret-token`
4. Send queries in JSON format:
   ```json
   {
     "query": "search term",
     "max_results": 10
   }
   ```

### Perplexity Integration

Configure Perplexity to use your local MCP server for document search:

**Prerequisites**:
1. **Start HTTP Server** (not MCP protocol):
   ```bash
   source .venv/bin/activate
   pcortex serve --port 8001  # Use different port than MCP
   ```

2. **Configure for Performance** (important for Perplexity timeouts):
   ```bash
# Edit your config.toml for faster responses
# In the [embedding] section, set:
# max_query_results = 3  # Reduce from default 10 to 3
   ```

3. **Verify Health**:
   ```bash
   curl -H "Authorization: Bearer your-secret-token" \
        http://localhost:8001/prometh_cortex_health
   ```

**Integration Setup**:
1. **Server Configuration**:
   - Protocol: `HTTP`
   - URL: `http://localhost:8001/prometh_cortex_query`
   - Method: `POST`
   - Headers: `Authorization: Bearer your-secret-token`
   - Content-Type: `application/json`

2. **Query Format**:
   ```json
   {
     "query": "your search query",
     "max_results": 3
   }
   ```

3. **Example Request**:
   ```bash
   curl -X POST http://localhost:8001/prometh_cortex_query \
     -H "Authorization: Bearer your-secret-token" \
     -H "Content-Type: application/json" \
     -d '{"query": "meeting notes", "max_results": 3}'
   ```

**Performance Optimization**:
- ✅ **Reduced Results**: Use `max_results: 3` instead of 10 to avoid timeouts
- ✅ **Dedicated Port**: Use separate port (8001) for Perplexity vs other integrations
- ✅ **Quick Queries**: Response time optimized to <400ms for timeout compatibility

**Usage in Perplexity**: 
- Ask: "Search my local documents for project updates"
- Ask: "Find my notes about last week's meetings"
- Ask: "What information do I have about [specific topic]?"

### VSCode with GitHub Copilot Integration

Configure VSCode to use your MCP server with GitHub Copilot:

#### Option 1: VSCode MCP Extension (Recommended)

1. **Install MCP for VSCode**:
   ```bash
   # Install the VSCode MCP extension
   code --install-extension ms-vscode.mcp
   ```

2. **Configure MCP Settings**: Add to your VSCode `settings.json` or create `.vscode/mcp.json`:
   ```json
   {
     "mcpServers": {
       "prometh-cortex": {
         "command": "/path/to/your/project/.venv/bin/python",
         "args": [
           "-m", "prometh_cortex.cli.main", "mcp"
         ],
         "env": {
           "DATALAKE_REPOS": "/path/to/your/notes,/path/to/your/documents,/path/to/your/projects",
           "RAG_INDEX_DIR": "/path/to/index/storage",
           "MCP_PORT": "8080",
           "MCP_HOST": "localhost",
           "MCP_AUTH_TOKEN": "your-secure-token",
           "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
           "MAX_QUERY_RESULTS": "10",
           "CHUNK_SIZE": "512",
           "CHUNK_OVERLAP": "50"
         }
       }
     }
   }
   ```

3. **Update User Settings**: Add to your VSCode `settings.json`:
   ```json
   {
     "mcp.servers": {
       "prometh-cortex": {
         "enabled": true
       }
     }
   }
   ```

4. **Verify Integration**:
   - Open Command Palette (`Cmd+Shift+P`)
   - Run "MCP: List Servers" 
   - You should see "prometh-cortex" listed and active

#### Option 2: Direct HTTP Integration

Add to your VSCode `settings.json`:
```json
{
  "github.copilot.advanced": {
    "debug.useElectronPrompts": true,
    "debug.useNodeUserForPrompts": true
  },
  "prometh-cortex.server.url": "http://localhost:8001",
  "prometh-cortex.server.token": "your-secret-token"
}
```

Start the HTTP server:
```bash
source .venv/bin/activate
pcortex serve --port 8001
```

#### Option 3: Custom Task Integration

Create `.vscode/tasks.json` for quick queries:
```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Query Prometh-Cortex",
      "type": "shell",
      "command": "curl",
      "args": [
        "-H", "Authorization: Bearer your-secret-token",
        "-H", "Content-Type: application/json",
        "-d", "{\"query\": \"${input:searchQuery}\", \"max_results\": 5}",
        "http://localhost:8001/prometh_cortex_query"
      ],
      "group": "build",
      "presentation": {
        "echo": true,
        "reveal": "always",
        "panel": "new"
      }
    }
  ],
  "inputs": [
    {
      "id": "searchQuery",
      "description": "Enter your search query",
      "default": "meeting notes",
      "type": "promptString"
    }
  ]
}
```

**Setup Steps**:
1. **Build Index**: Ensure your RAG index is built and up-to-date
   ```bash
   source .venv/bin/activate
   pcortex build --force
   ```

2. **Start MCP Server** (for Option 1):
   ```bash
   # MCP server runs automatically when VSCode starts
   # Check VSCode Output panel for MCP logs
   ```

3. **Start HTTP Server** (for Options 2-3):
   ```bash
   source .venv/bin/activate
   pcortex serve --port 8001
   ```

**Usage**:
- **Option 1**: Use MCP commands directly in GitHub Copilot chat
  - Ask: "Search my documents for project planning notes"
  - Ask: "Find my meeting notes from last week"
- **Option 2**: GitHub Copilot will automatically query your local documents
- **Option 3**: Press `Ctrl+Shift+P` → "Tasks: Run Task" → "Query Prometh-Cortex"

**Troubleshooting**:
- ✅ **Check MCP Output**: View "Output" panel in VSCode, select "MCP" from dropdown
- ✅ **Verify Paths**: Ensure all paths are absolute and accessible
- ✅ **Test Manually**: Run `pcortex mcp` or `pcortex serve` to verify functionality
- ✅ **Restart VSCode**: After configuration changes, restart VSCode completely
  "inputs": [
    {
      "id": "searchQuery",
      "description": "Enter your search query",
      "default": "meeting notes",
      "type": "promptString"
    }
  ]
}
```

**Usage**: Press `Ctrl+Shift+P` → "Tasks: Run Task" → "Query Prometh-Cortex"

### General MCP Configuration Guide

**Two Server Types Available**:

1. **MCP Protocol Server** (`pcortex mcp`):
   - **Purpose**: AI assistant integration (Claude Desktop, VSCode MCP)
   - **Protocol**: stdio-based MCP
   - **Port**: No network port (stdio communication)
   - **Usage**: Direct integration with MCP-compatible clients

2. **HTTP REST Server** (`pcortex serve`):
   - **Purpose**: Web applications, HTTP clients (Perplexity, custom integrations)
   - **Protocol**: HTTP REST API
   - **Port**: Configurable (default: 8080)
   - **Usage**: Traditional HTTP API access

**Configuration Prerequisites**: 

1. **Environment Setup**:
   ```bash
   # Create and activate virtual environment
   python -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   
   # Install in development mode
   pip install -e .
   ```

2. **Create Configuration**:
   ```bash
   # Create configuration from sample
   cp config.toml.sample config.toml
   # Edit config.toml with your specific settings
   ```

3. **Build Index**:
   ```bash
   pcortex build --force
   ```

4. **Test Configuration**:
   ```bash
   # Test MCP server
   pcortex mcp  # Should start without errors, Ctrl+C to stop
   
   # Test HTTP server
   pcortex serve  # Should show server info, Ctrl+C to stop
   
   # Test query functionality
   pcortex query "test search"
   ```

**Common Integration Pattern**:

For **HTTP integrations** (Perplexity, web apps):
```bash
# Start HTTP server
pcortex serve --port 8001

# Query endpoint
POST http://localhost:8001/prometh_cortex_query
Authorization: Bearer your-secret-token
Content-Type: application/json

{
  "query": "your search query",
  "max_results": 10,
  "filters": {
    "datalake": "notes",
    "tags": ["work"]
  }
}

# Health check
GET http://localhost:8001/prometh_cortex_health
Authorization: Bearer your-secret-token
```

For **MCP integrations** (Claude Desktop, VSCode):
```json
{
  "mcpServers": {
    "prometh-cortex": {
      "command": "/path/to/your/project/.venv/bin/python",
      "args": [
        "-m", "prometh_cortex.cli.main", "mcp"
      ],
      "env": {
        "DATALAKE_REPOS": "/path/to/your/notes,/path/to/your/documents,/path/to/your/projects",
        "RAG_INDEX_DIR": "/path/to/index/storage",
        "MCP_PORT": "8080",
        "MCP_HOST": "localhost",
        "MCP_AUTH_TOKEN": "your-secure-token",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
        "MAX_QUERY_RESULTS": "10",
        "CHUNK_SIZE": "512",
        "CHUNK_OVERLAP": "50",
        "VECTOR_STORE_TYPE": "faiss"
      }
    }
  }
}
```

**Performance Tuning**:
- **For Perplexity**: Set `max_query_results = 3` in config.toml to avoid timeouts
- **For Development**: Use `--reload` flag with `pcortex serve`
- **For Production**: Use production WSGI server instead of development server

**Auto-start Script**:
Create `start_servers.sh` for easy management:
```bash
#!/bin/bash
# Kill existing servers
pkill -f "pcortex serve" 2>/dev/null || true
pkill -f "pcortex mcp" 2>/dev/null || true

# Activate virtual environment
source .venv/bin/activate

# Start HTTP server in background
nohup pcortex serve --port 8001 > /tmp/prometh-cortex-http.log 2>&1 &

echo "Prometh-Cortex servers started"
echo "HTTP Server: http://localhost:8001"
echo "MCP Server: Available for stdio connections"
echo "Logs: /tmp/prometh-cortex-http.log"
```

**Troubleshooting Checklist**:
- ✅ **Virtual Environment**: Always use absolute paths to `.venv/bin/python`
- ✅ **Configuration**: Set `datalake.repos` and `storage.rag_index_dir` in config.toml 
- ✅ **Index Built**: Run `pcortex build` before using servers
- ✅ **Ports Available**: Check port conflicts with `lsof -i :8080`
- ✅ **Logs Check**: Monitor server logs for configuration errors
- ✅ **Path Permissions**: Ensure read access to datalake and write access to index directory

## Development

### Setup Development Environment
```bash
# Clone repository
git clone https://github.com/ivannagy/prometh-cortex.git
cd prometh-cortex

# Install with development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Run Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/prometh_cortex

# Run specific test types
pytest tests/unit/
pytest tests/integration/
```

### Code Quality
```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

## Performance

- **Query Speed**: Target <100ms on M1/M2 Mac
- **Index Size**: Scales to thousands of documents
- **Memory Usage**: Optimized chunking and streaming processing
- **Storage**: Efficient FAISS local storage or scalable Qdrant
- **Incremental Updates**: Only processes changed documents

## Architecture

```
┌─────────────────────┐
│    config.toml      │
└──────────┬──────────┘
           │
┌──────────▼──────────────────┐
│ Datalake Ingest & Parser    │
│ - Markdown files            │
│ - YAML frontmatter          │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────┐
│ Vector Store / Indexing     │
│ - FAISS (local) or Qdrant   │
│ - Local embedding model     │
│ - Incremental indexing      │
└──────────┬──────────────────┘
           │
┌──────────▼──────────────────┐
│     MCP Local Server        │
│ - /prometh_cortex_query     │
│ - /prometh_cortex_health    │
└─────────────────────────────┘
```

## License

Apache 2.0 License - see [LICENSE](LICENSE) for details.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes with clear, descriptive commits
4. Add tests for new functionality
5. Ensure all tests pass: `pytest`
6. Format code: `black src/ tests/` and `isort src/ tests/`
7. Submit a pull request with a clear description

### Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold this code.

### Security

Found a security vulnerability? Please see [SECURITY.md](SECURITY.md) for responsible disclosure guidelines.

## Support

### Getting Help

- **Documentation**: See the [/docs](docs/) directory for detailed guides
- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/ivannagy/prometh-cortex/issues)
- **Discussions**: Ask questions or share ideas in [GitHub Discussions](https://github.com/ivannagy/prometh-cortex/discussions)
- **Security**: For security issues, see [SECURITY.md](SECURITY.md)

### Resources

- **PyPI Package**: https://pypi.org/project/prometh-cortex/
- **Source Code**: https://github.com/ivannagy/prometh-cortex
- **Changelog**: See [CHANGELOG.md](CHANGELOG.md) for version history

### Community

We encourage community participation! Whether you're fixing bugs, adding features, improving documentation, or helping others, all contributions are valued.

---

**Made with ❤️ for the knowledge management community**