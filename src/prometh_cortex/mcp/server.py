"""MCP (Model Context Protocol) server for Claude Desktop integration.

This module implements a stdio-based MCP server that provides tools for querying
the indexed datalake documents. This is specifically designed for Claude Desktop
integration using the MCP protocol.
"""

import json
import logging
import sys
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from prometh_cortex.config import load_config
from prometh_cortex.indexer import DocumentIndexer, IndexerError
from prometh_cortex.parser import parse_markdown_file
from prometh_cortex.mcp.timeout_handler import (
    ProgressReporter,
    StartupOptimizer,
    ChunkedQueryProcessor,
    AsyncOperationManager
)
from prometh_cortex.mcp.enhanced_tools import setup_enhanced_tools


# Set up logging for MCP server (absolute minimal logging to avoid protocol issues)
# Only log critical errors to avoid any stdout/stderr interference
logging.basicConfig(
    level=logging.CRITICAL,  # Only critical errors
    format="%(message)s",  # Minimal format
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Disable all logging from dependencies to speed up startup
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("sentence_transformers").setLevel(logging.CRITICAL)
logging.getLogger("transformers").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("requests").setLevel(logging.CRITICAL)

# Global variables for MCP server state
config = None
indexer = None
mcp = FastMCP("prometh-cortex")

# Timeout handling components
progress_reporter = None
startup_optimizer = None
cleanup_task = None


async def initialize_server():
    """Initialize the MCP server with configuration and indexer using startup optimization."""
    global config, indexer, progress_reporter, startup_optimizer, cleanup_task
    
    try:
        # Load configuration first
        step_start = time.time()
        config = load_config()
        logger.critical(f"Config loaded: {(time.time() - step_start):.2f}s")
        
        # Initialize timeout handling components with config values
        step_start = time.time()
        progress_interval = getattr(config, 'mcp_progress_interval', 5)
        max_startup_time = getattr(config, 'mcp_max_startup_time', 50.0)
        lazy_load = getattr(config, 'mcp_lazy_load_index', True)
        
        progress_reporter = ProgressReporter(update_interval=progress_interval)
        startup_optimizer = StartupOptimizer(progress_reporter, max_startup_time=max_startup_time)
        logger.critical(f"Timeout components initialized: {(time.time() - step_start):.2f}s")
        
        # Use startup optimizer for fast initialization
        step_start = time.time()
        await startup_optimizer.initialize_server(
            config_loader=lambda: config,
            indexer_factory=lambda: DocumentIndexer(config)
        )
        logger.critical(f"Startup optimizer completed: {(time.time() - step_start):.2f}s")
        
        # Create indexer but don't load index if lazy loading is enabled
        step_start = time.time()
        indexer = DocumentIndexer(config)
        if not lazy_load:
            # Load index immediately if lazy loading is disabled
            await startup_optimizer.lazy_load_index(indexer)
            logger.critical(f"Index loaded (lazy_load=False): {(time.time() - step_start):.2f}s")
        else:
            logger.critical(f"Indexer created (lazy_load=True): {(time.time() - step_start):.2f}s")
        
        # Setup enhanced MCP tools with timeout handling
        step_start = time.time()
        await setup_enhanced_tools(mcp, indexer, config)
        logger.critical(f"Enhanced MCP tools setup: {(time.time() - step_start):.2f}s")
        
        # Start cleanup task with configuration
        step_start = time.time()
        from prometh_cortex.mcp.enhanced_tools import cleanup_timeout_operations
        cleanup_task = asyncio.create_task(cleanup_timeout_operations(config))
        logger.critical(f"Cleanup task started: {(time.time() - step_start):.2f}s")
        
        logger.critical("MCP server initialized successfully with timeout handling")
        
    except Exception as e:
        logger.critical(f"MCP server initialization failed: {e}")
        # For MCP protocol, we need to exit cleanly without extra output
        sys.exit(1)


async def lazy_load_index():
    """Load the index lazily on first use to prevent startup timeout."""
    global indexer, startup_optimizer
    
    if indexer and not hasattr(indexer, '_index_loaded'):
        try:
            if startup_optimizer:
                await startup_optimizer.lazy_load_index(indexer)
            else:
                # Fallback to sync loading
                await asyncio.to_thread(indexer.load_index)
                indexer._index_loaded = True
        except Exception as e:
            # Only log critical index loading failures
            logger.critical(f"Index loading failed: {e}")
            raise IndexerError(f"Index loading failed: {e}")
    
    return indexer


@mcp.tool()
async def prometh_cortex_query(
    query: str,
    max_results: Optional[int] = None,
    filters: Optional[Dict[str, Any]] = None,
    show_query_info: bool = False,
    include_full_content: bool = False
) -> Dict[str, Any]:
    """Query indexed documents with enhanced tag-based filtering and semantic search.
    
    RECOMMENDED: Use tags for precise filtering, semantic text for content matching.
    
    Supported query formats:
    - Simple: "meeting notes discussion"
    - Tag filters: "tags:work,urgent" or "tags:meetings|planning" or "tags:project+urgent"  
    - Date filters: "created:2024-12-08" or "created:2024-12-01:2024-12-08"
    - Combined: "tags:meetings,work created:2024-12-08 discussion agenda"
    - Other fields: "author:john status:completed project update"
    
    Args:
        query: The search query text (simple or structured)
        max_results: Maximum number of results to return (default: config value)
        filters: Optional additional filters (merged with parsed structured filters)
        show_query_info: Include query parsing information in response for debugging
        include_full_content: Load and include complete document content (not just chunks)
    
    Returns:
        Dictionary containing query results, timing, metadata, and optionally full document content
    """
    try:
        # Lazy load index on first query
        indexer = await lazy_load_index()
        if not indexer:
            return {"error": "Indexer not initialized"}
        
        start_time = time.time()
        
        # Determine max results
        if max_results is None:
            max_results = config.max_query_results
        
        # Convert legacy filters to vector store filters and apply vector-level filtering
        vector_store_filters = {}
        post_process_filters = {}
        
        if filters:
            # Separate filters that can be applied at vector store level vs post-processing
            for key, value in filters.items():
                if key in ["datalake", "tags"]:
                    # These need post-processing due to complex logic
                    post_process_filters[key] = value
                else:
                    # Direct metadata filters can be handled by vector store
                    vector_store_filters[key] = value
        
        # Perform query with vector store filters
        results = indexer.query(
            query, 
            max_results=max_results * 2 if post_process_filters else max_results,  # Get more if post-filtering
            filters=vector_store_filters if vector_store_filters else None
        )
        
        # Apply post-processing filters if provided
        if post_process_filters:
            filtered_results = []
            for result in results:
                include_result = True
                
                # Apply datalake filter
                if "datalake" in post_process_filters:
                    source_path = result.get("source_file", "")
                    if post_process_filters["datalake"] not in source_path:
                        include_result = False
                
                # Apply tags filter
                if "tags" in post_process_filters and include_result:
                    result_tags = result.get("metadata", {}).get("tags", [])
                    required_tags = post_process_filters["tags"]
                    if not any(tag in result_tags for tag in required_tags):
                        include_result = False
                
                if include_result:
                    filtered_results.append(result)
            
            results = filtered_results[:max_results]
        
        query_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Load full documents if requested
        full_documents_cache = {}
        full_documents_loaded = 0
        
        if include_full_content and results:
            logger.info(f"Loading full content for {len(results)} results")
            
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
                    # Silently skip failed document loads
                    # Continue without failing the entire query
                    pass
        
        # Format response for MCP
        formatted_results = []
        for result in results:
            formatted_result = {
                "content": result["content"],
                "source_file": result["source_file"],
                "metadata": result["metadata"],
                "similarity_score": result["similarity_score"]
            }
            
            # Add full document content if requested and available
            if include_full_content:
                source_file = result.get("source_file", "")
                if source_file in full_documents_cache:
                    doc_data = full_documents_cache[source_file]
                    formatted_result.update({
                        "full_document_content": doc_data["content"],
                        "document_title": doc_data["title"],
                        "document_metadata": doc_data["metadata"],
                        "document_searchable_text": doc_data["searchable_text"][:1000] + "..." if len(doc_data["searchable_text"]) > 1000 else doc_data["searchable_text"]
                    })
            
            formatted_results.append(formatted_result)
        
        response = {
            "results": formatted_results,
            "query_time_ms": query_time,
            "total_results": len(results),
            "query": query,
            "max_results": max_results
        }
        
        # Add full content metadata if requested
        if include_full_content:
            response["full_documents_loaded"] = full_documents_loaded
            response["unique_documents"] = len(full_documents_cache)
        
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
        response["sources"] = sources
        response["source_count"] = len(sources)
        
        # FORCE sources to be visible by embedding them in content
        # This ensures VS Code/GPT-4o will see and display the sources
        if sources and formatted_results:
            source_citations = "\n\n**Sources:**\n"
            for source in sources:
                source_citations += f"• **{source['id']} {source['title']}** ({source['relevance']}) - `{source['file_name']}`\n"
                if source.get('event'):
                    source_citations += f"  _{source.get('event')} - {source.get('organizer', 'Unknown organizer')}_\n"
            
            # Embed sources in the response text for guaranteed visibility
            response["source_citations_text"] = source_citations.strip()
            
            # Also add to first result for immediate visibility
            if include_full_content and formatted_results:
                formatted_results[0]["content"] += source_citations
        
        # Add query parsing information if requested and available
        if show_query_info and results:
            first_result_query_info = results[0].get('query_info', {})
            if first_result_query_info:
                response["query_analysis"] = {
                    "original_query": first_result_query_info.get('original_query', query),
                    "semantic_query": first_result_query_info.get('semantic_query', query),
                    "applied_filters": first_result_query_info.get('applied_filters', {}),
                    "parsed_filters": first_result_query_info.get('parsed_filters', {})
                }
        
        # Removed verbose query logging for MCP protocol compatibility
        return response
        
    except IndexerError as e:
        logger.critical(f"Indexer error: {e}")
        return {"error": f"Indexer error: {e}"}
    except Exception as e:
        logger.critical(f"Query error: {e}")
        return {"error": f"Internal error: {e}"}


@mcp.tool()
async def prometh_cortex_health() -> Dict[str, Any]:
    """Get health status and statistics for the Prometh-Cortex system.
    
    Returns:
        Dictionary containing health status, indexed files count, and system metrics
    """
    try:
        start_time = time.time()
        
        # Basic health info
        health_info = {
            "status": "healthy",
            "embedding_model": config.embedding_model if config else "unknown",
            "vector_store_type": config.vector_store_type if config else "unknown"
        }
        
        # Get indexer statistics if available
        try:
            # Try to lazy load index for health check
            indexer_instance = await lazy_load_index()
            if indexer_instance:
                try:
                    index_stats = indexer_instance.get_stats()
                    health_info.update({
                        "indexed_files": index_stats.get("total_vectors", 0),
                        "index_stats": index_stats
                    })
                except Exception as e:
                    # Silently handle index stats failures
                    health_info.update({
                        "indexed_files": 0,
                        "index_stats": {"status": "index_not_loaded", "error": str(e)}
                    })
            else:
                health_info.update({
                    "indexed_files": 0,
                    "index_stats": {"status": "indexer_not_initialized"}
                })
        except Exception as e:
            # If lazy loading fails, report it but don't crash (silent)
            health_info.update({
                "indexed_files": 0,
                "index_stats": {"status": "index_loading_failed", "error": str(e)}
            })
        
        # Add configuration info
        if config:
            config_info = {
                "datalake_repos": [str(p) for p in config.datalake_repos],
                "max_query_results": config.max_query_results,
                "chunk_size": config.chunk_size,
                "chunk_overlap": config.chunk_overlap
            }
            
            # Add vector store specific info
            if config.vector_store_type == 'faiss':
                config_info["rag_index_dir"] = str(config.rag_index_dir)
            else:
                config_info.update({
                    "qdrant_host": config.qdrant_host,
                    "qdrant_port": config.qdrant_port,
                    "qdrant_collection_name": config.qdrant_collection_name,
                    "qdrant_use_https": config.qdrant_use_https
                })
            
            health_info.update(config_info)
        
        # Add timing
        health_check_time = (time.time() - start_time) * 1000
        health_info["health_check_time_ms"] = health_check_time
        
        return health_info
        
    except Exception as e:
        logger.critical(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "indexed_files": 0
        }


def run_mcp_server():
    """Run the MCP server with stdio transport."""
    # Completely silent startup for MCP protocol compatibility
    startup_start_time = time.time()
    
    async def async_startup():
        """Async startup for MCP server."""
        global cleanup_task, config
        try:
            # Initialize server components with timeout optimization
            await initialize_server()
            
            # Async initialization complete, MCP server will run synchronously
            pass
            
        except KeyboardInterrupt:
            pass  # Silent shutdown
        except Exception as e:
            logger.critical(f"MCP server fatal error: {e}")
            raise
        finally:
            # Clean up background tasks
            if cleanup_task and not cleanup_task.done():
                cleanup_task.cancel()
                try:
                    await cleanup_task
                except asyncio.CancelledError:
                    pass
    
    # Run async initialization first
    try:
        asyncio.run(async_startup())
        
        # Measure and report total startup time
        total_startup_time = time.time() - startup_start_time
        max_startup_time = getattr(config, 'mcp_max_startup_time', 50.0) if config else 50.0
        
        # Log startup time to stderr (won't interfere with MCP protocol on stdout)
        logger.critical(f"MCP server startup completed in {total_startup_time:.2f}s (max: {max_startup_time:.2f}s)")
        
        if total_startup_time > max_startup_time:
            logger.critical(f"⚠️  STARTUP EXCEEDED TARGET: {total_startup_time:.2f}s > {max_startup_time:.2f}s")
        else:
            logger.critical(f"✅ Startup within target: {total_startup_time:.2f}s < {max_startup_time:.2f}s")
        
        # Run the synchronous MCP server
        mcp.run(transport="stdio")
        
    except Exception as e:
        total_startup_time = time.time() - startup_start_time
        logger.critical(f"MCP server startup failed after {total_startup_time:.2f}s: {e}")
        sys.exit(1)
    finally:
        # Clean up background tasks on shutdown
        if cleanup_task and not cleanup_task.done():
            cleanup_task.cancel()


if __name__ == "__main__":
    run_mcp_server()