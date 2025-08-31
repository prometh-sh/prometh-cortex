"""FastAPI application for MCP server endpoints."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from prometh_cortex.config import Config, load_config
from prometh_cortex.indexer import DocumentIndexer, IndexerError
from prometh_cortex.parser import parse_markdown_file


# Global variables for application state
app_config: Optional[Config] = None
indexer: Optional[DocumentIndexer] = None
app_start_time = time.time()


class QueryRequest(BaseModel):
    """Request model for RAG query endpoint."""
    query: str = Field(..., min_length=1, description="Search query text (simple or structured)")
    max_results: Optional[int] = Field(
        default=None, 
        ge=1, le=100,
        description="Maximum number of results to return"
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional additional filters (merged with structured query filters)"
    )
    show_query_info: bool = Field(
        default=False,
        description="Include query parsing information in response for debugging"
    )
    include_full_content: bool = Field(
        default=False,
        description="Load and include complete document content (not just chunks)"
    )


class QueryResult(BaseModel):
    """Individual query result."""
    content: str = Field(..., description="Content snippet from document")
    source_file: str = Field(..., description="Path to source document")
    metadata: Dict[str, Any] = Field(..., description="Document metadata")
    similarity_score: float = Field(..., description="Similarity score (0-1)")
    full_document_content: Optional[str] = Field(None, description="Complete document content (if requested)")
    document_title: Optional[str] = Field(None, description="Document title (if full content loaded)")
    document_metadata: Optional[Dict[str, Any]] = Field(None, description="Complete document metadata (if full content loaded)")
    document_searchable_text: Optional[str] = Field(None, description="Searchable text summary (if full content loaded)")


class QueryResponse(BaseModel):
    """Response model for RAG query endpoint."""
    results: List[QueryResult] = Field(..., description="Query results")
    query_time_ms: float = Field(..., description="Query execution time in milliseconds")
    total_results: int = Field(..., description="Total number of results returned")
    query_analysis: Optional[Dict[str, Any]] = Field(None, description="Query parsing information (if show_query_info=true)")
    full_documents_loaded: Optional[int] = Field(None, description="Number of full documents loaded (if include_full_content=true)")
    unique_documents: Optional[int] = Field(None, description="Number of unique documents processed (if include_full_content=true)")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Source document citations (Perplexity-style)")
    source_count: Optional[int] = Field(None, description="Number of source citations")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str = Field(..., description="Service status")
    indexed_files: int = Field(..., description="Number of indexed documents")
    last_index_update: Optional[str] = Field(None, description="Last index update timestamp")
    uptime_seconds: float = Field(..., description="Server uptime in seconds")
    embedding_model: str = Field(..., description="Embedding model name")
    index_stats: Dict[str, Any] = Field(..., description="Index statistics")


# Security
security = HTTPBearer(auto_error=False)


def get_current_config() -> Config:
    """Dependency to get current configuration."""
    global app_config
    
    if app_config is None:
        # Try to load from environment variable first (set by CLI)
        config_json = os.getenv("PROMETH_CORTEX_CONFIG")
        if config_json:
            try:
                config_data = json.loads(config_json)
                app_config = Config(**config_data)
            except Exception:
                app_config = load_config()
        else:
            app_config = load_config()
    
    return app_config


def get_indexer(config: Config = Depends(get_current_config)) -> DocumentIndexer:
    """Dependency to get document indexer."""
    global indexer
    
    if indexer is None:
        indexer = DocumentIndexer(config)
        indexer.load_index()
    
    return indexer


def verify_auth_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    config: Config = Depends(get_current_config)
) -> bool:
    """Verify authentication token."""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if credentials.credentials != config.mcp_auth_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return True


def create_app(config: Optional[Config] = None) -> FastAPI:
    """Create FastAPI application with MCP endpoints."""
    global app_config
    
    if config:
        app_config = config
    
    app = FastAPI(
        title="Prometh Cortex MCP Server",
        description="Multi-Datalake RAG Indexer with Local MCP Integration",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add CORS middleware for web integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify allowed origins
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    
    @app.post(
        "/prometh_cortex_query",
        response_model=QueryResponse,
        summary="Query RAG Index with Structured Query Support",
        description="Search indexed documents using semantic similarity with optional structured query filters"
    )
    async def query_rag_index(
        request: QueryRequest,
        _: bool = Depends(verify_auth_token),
        indexer: DocumentIndexer = Depends(get_indexer),
        config: Config = Depends(get_current_config)
    ):
        """Query the RAG index for similar documents with structured query support."""
        try:
            start_time = time.time()
            
            # Determine max results
            max_results = request.max_results or config.max_query_results
            
            # Perform query (indexer now handles structured query parsing)
            results = indexer.query(
                request.query, 
                max_results=max_results,
                filters=request.filters  # Additional filters merged with parsed filters
            )
            
            query_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Load full documents if requested
            full_documents_cache = {}
            full_documents_loaded = 0
            
            if request.include_full_content and results:
                # Extract unique source files from results
                unique_files = set()
                for result in results:
                    source_file = result.get("source_file", "")
                    if source_file and Path(source_file).exists():
                        unique_files.add(source_file)
                
                # Load each unique document once (caching)
                for file_path in unique_files:
                    try:
                        file_path_obj = Path(file_path)
                        doc = parse_markdown_file(file_path_obj)
                        full_documents_cache[file_path] = {
                            "content": doc.content,
                            "searchable_text": doc.searchable_text,
                            "metadata": doc.metadata,
                            "title": doc.title
                        }
                        full_documents_loaded += 1
                    except Exception as e:
                        # Continue without failing the entire query
                        pass
            
            # Format response
            query_results = []
            for result in results:
                result_data = {
                    "content": result["content"],
                    "source_file": result["source_file"],
                    "metadata": result["metadata"],
                    "similarity_score": result["similarity_score"]
                }
                
                # Add full document content if requested and available
                if request.include_full_content:
                    source_file = result.get("source_file", "")
                    if source_file in full_documents_cache:
                        doc_data = full_documents_cache[source_file]
                        result_data.update({
                            "full_document_content": doc_data["content"],
                            "document_title": doc_data["title"],
                            "document_metadata": doc_data["metadata"],
                            "document_searchable_text": doc_data["searchable_text"][:1000] + "..." if len(doc_data["searchable_text"]) > 1000 else doc_data["searchable_text"]
                        })
                
                query_results.append(QueryResult(**result_data))
            
            # Prepare response
            response_data = {
                "results": query_results,
                "query_time_ms": query_time,
                "total_results": len(query_results)
            }
            
            # Add full content metadata if requested
            if request.include_full_content:
                response_data["full_documents_loaded"] = full_documents_loaded
                response_data["unique_documents"] = len(full_documents_cache)
            
            # Add source citations for easy reference (like Perplexity/Claude.ai)
            sources = []
            if results:
                seen_files = set()
                
                for i, result in enumerate(results[:5], 1):  # Top 5 sources
                    source_file = result.get("source_file", "")
                    if source_file and source_file not in seen_files:
                        seen_files.add(source_file)
                        
                        metadata = result.get("metadata", {})
                        similarity = result.get("similarity_score", 0)
                        
                        source_info = {
                            "id": f"[{i}]",
                            "title": metadata.get("title", "Untitled"),
                            "file_name": metadata.get("file_name", Path(source_file).name),
                            "created": metadata.get("created", "Unknown date"),
                            "relevance": f"{similarity:.1%}" if similarity else "N/A",
                            "tags": metadata.get("tags", []),
                            "category": metadata.get("category", "Unknown")
                        }
                        
                        # Add event info if available
                        if metadata.get("event_subject"):
                            source_info["event"] = metadata.get("event_subject")
                            source_info["organizer"] = metadata.get("event_organizer", "Unknown")
                        
                        sources.append(source_info)
            
            # Always include sources in response (empty array if no results)
            response_data["sources"] = sources
            response_data["source_count"] = len(sources)
            
            # Add query analysis if requested and available
            if request.show_query_info and results:
                first_result_query_info = results[0].get('query_info', {})
                if first_result_query_info:
                    response_data["query_analysis"] = {
                        "original_query": first_result_query_info.get('original_query', request.query),
                        "semantic_query": first_result_query_info.get('semantic_query', request.query),
                        "applied_filters": first_result_query_info.get('applied_filters', {}),
                        "parsed_filters": first_result_query_info.get('parsed_filters', {})
                    }
            
            return QueryResponse(**response_data)
            
        except IndexerError as e:
            raise HTTPException(status_code=500, detail=f"Indexer error: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    
    @app.get(
        "/prometh_cortex_health",
        response_model=HealthResponse,
        summary="Health Check",
        description="Get server health status and index statistics"
    )
    async def health_check(
        config: Config = Depends(get_current_config)
    ):
        """Get server health status and statistics."""
        try:
            # Get uptime
            uptime = time.time() - app_start_time
            
            # Try to get indexer stats
            index_stats = {"status": "unknown"}
            indexed_files = 0
            
            try:
                temp_indexer = DocumentIndexer(config)
                temp_indexer.load_index()
                index_stats = temp_indexer.get_stats()
                indexed_files = index_stats.get("total_vectors", 0)
            except Exception:
                index_stats = {"status": "index_not_loaded"}
            
            # Check last index update (placeholder - would need to store this)
            last_index_update = None
            config_file = config.rag_index_dir / "config.json"
            if config_file.exists():
                try:
                    with open(config_file) as f:
                        config_data = json.load(f)
                        last_index_update = config_data.get("created_at")
                except Exception:
                    pass
            
            return HealthResponse(
                status="healthy",
                indexed_files=indexed_files,
                last_index_update=last_index_update,
                uptime_seconds=uptime,
                embedding_model=config.embedding_model,
                index_stats=index_stats
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Health check failed: {e}")
    
    @app.get("/", summary="Root", description="API root endpoint")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "Prometh Cortex MCP Server",
            "version": "0.1.0",
            "description": "Multi-Datalake RAG Indexer with Local MCP Integration",
            "endpoints": {
                "query": "/prometh_cortex_query",
                "health": "/prometh_cortex_health",
                "docs": "/docs"
            },
            "status": "running",
            "timestamp": datetime.now().isoformat()
        }
    
    return app


# Create app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    # Load configuration
    config = load_config()
    
    uvicorn.run(
        "prometh_cortex.server.app:app",
        host=config.mcp_host,
        port=config.mcp_port,
        reload=True
    )