"""MCP (Model Context Protocol) server for Claude Desktop integration.

This module implements a stdio-based MCP server that provides tools for querying
the indexed datalake documents. This is specifically designed for Claude Desktop
integration using the MCP protocol.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier

from prometh_cortex.config import load_config
from prometh_cortex.indexer import DocumentIndexer, IndexerError
from prometh_cortex.mcp.enhanced_tools import setup_enhanced_tools
from prometh_cortex.mcp.timeout_handler import (
    AsyncOperationManager,
    ChunkedQueryProcessor,
    ProgressReporter,
    StartupOptimizer,
)
from prometh_cortex.parser import parse_markdown_file

# Set up logging for MCP server (absolute minimal logging to avoid protocol issues)
# Only log critical errors to avoid any stdout/stderr interference
logging.basicConfig(
    level=logging.CRITICAL,  # Only critical errors
    format="%(message)s",  # Minimal format
    stream=sys.stderr,
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


class StaticBearerTokenVerifier(TokenVerifier):
    """Simple bearer token verifier that checks against a static secret.

    This is used when running the MCP server with SSE or streamable-http
    transport to enforce authentication on all incoming connections.
    Clients must send the token as a Bearer token in the Authorization header.
    """

    def __init__(self, token: str):
        super().__init__()
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if token == self._token:
            return AccessToken(
                token=token,
                client_id="bearer-auth",
                scopes=[],
            )
        return None


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
        progress_interval = getattr(config, "mcp_progress_interval", 5)
        max_startup_time = getattr(config, "mcp_max_startup_time", 50.0)
        lazy_load = getattr(config, "mcp_lazy_load_index", True)

        progress_reporter = ProgressReporter(update_interval=progress_interval)
        startup_optimizer = StartupOptimizer(
            progress_reporter, max_startup_time=max_startup_time
        )
        logger.critical(
            f"Timeout components initialized: {(time.time() - step_start):.2f}s"
        )

        # Use startup optimizer for fast initialization
        step_start = time.time()
        await startup_optimizer.initialize_server(
            config_loader=lambda: config,
            indexer_factory=lambda: DocumentIndexer(config),
        )
        logger.critical(
            f"Startup optimizer completed: {(time.time() - step_start):.2f}s"
        )

        # Create indexer but don't load index if lazy loading is enabled
        step_start = time.time()
        indexer = DocumentIndexer(config)
        if not lazy_load:
            # Load index immediately if lazy loading is disabled
            await startup_optimizer.lazy_load_index(indexer)
            logger.critical(
                f"Index loaded (lazy_load=False): {(time.time() - step_start):.2f}s"
            )
        else:
            logger.critical(
                f"Indexer created (lazy_load=True): {(time.time() - step_start):.2f}s"
            )

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

    if indexer and not hasattr(indexer, "_index_loaded"):
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
    source_type: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    show_query_info: bool = False,
    include_full_content: bool = False,
    include_dreaming: bool = False,
) -> Dict[str, Any]:
    """Query indexed documents with enhanced tag-based filtering and semantic search.

    Per-source chunking support (v0.3.0+): Query across unified index with optional source filtering.

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
        source_type: Optional source type to filter by (default: search all sources)
        filters: Optional additional filters (merged with parsed structured filters)
        show_query_info: Include query parsing information in response for debugging
        include_full_content: Load and include complete document content (not just chunks)
        include_dreaming: When True, includes consolidated (dreaming=true) memories. By default, only active memories are returned.

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

        # Validate source_type if specified
        if source_type:
            valid_sources = [s.name for s in config.sources]
            if source_type not in valid_sources:
                return {
                    "error": f"Source type '{source_type}' not found",
                    "available_sources": valid_sources,
                }

        # Convert legacy filters to vector store filters and apply vector-level filtering
        vector_store_filters = {}
        post_process_filters = {}

        if filters:
            # Separate filters that can be applied at vector store level vs post-processing
            for key, value in filters.items():
                if key in ["datalake", "tags", "source_type"]:
                    # These need post-processing due to complex logic
                    post_process_filters[key] = value
                else:
                    # Direct metadata filters can be handled by vector store
                    vector_store_filters[key] = value

        # Handle dreaming filter
        # If include_dreaming=True, don't add the default dreaming filter (all dreaming states included)
        # If include_dreaming=False (default), let query() apply the default dreaming=false filter
        if include_dreaming and "dreaming" not in vector_store_filters:
            # Explicitly set dreaming to None to signal: include all
            vector_store_filters["dreaming"] = None

        # Perform query with optional source_type filtering
        results = indexer.query(
            query,
            source_type=source_type,
            max_results=(
                max_results * 2 if post_process_filters else max_results
            ),  # Get more if post-filtering
            filters=vector_store_filters if vector_store_filters else None,
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
                        "title": doc.title,
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
                "similarity_score": result["similarity_score"],
            }

            # Add full document content if requested and available
            if include_full_content:
                source_file = result.get("source_file", "")
                if source_file in full_documents_cache:
                    doc_data = full_documents_cache[source_file]
                    formatted_result.update(
                        {
                            "full_document_content": doc_data["content"],
                            "document_title": doc_data["title"],
                            "document_metadata": doc_data["metadata"],
                            "document_searchable_text": (
                                doc_data["searchable_text"][:1000] + "..."
                                if len(doc_data["searchable_text"]) > 1000
                                else doc_data["searchable_text"]
                            ),
                        }
                    )

            formatted_results.append(formatted_result)

        response = {
            "results": formatted_results,
            "query_time_ms": query_time,
            "total_results": len(results),
            "query": query,
            "max_results": max_results,
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
                        "category": metadata.get("category", "Unknown"),
                    }

                    # Add event info if available
                    if metadata.get("event_subject"):
                        source_info["event"] = metadata.get("event_subject")
                        source_info["organizer"] = metadata.get(
                            "event_organizer", "Unknown"
                        )

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
                if source.get("event"):
                    source_citations += f"  _{source.get('event')} - {source.get('organizer', 'Unknown organizer')}_\n"

            # Embed sources in the response text for guaranteed visibility
            response["source_citations_text"] = source_citations.strip()

            # Also add to first result for immediate visibility
            if include_full_content and formatted_results:
                formatted_results[0]["content"] += source_citations

        # Add query parsing information if requested and available
        if show_query_info and results:
            first_result_query_info = results[0].get("query_info", {})
            if first_result_query_info:
                response["query_analysis"] = {
                    "original_query": first_result_query_info.get(
                        "original_query", query
                    ),
                    "semantic_query": first_result_query_info.get(
                        "semantic_query", query
                    ),
                    "applied_filters": first_result_query_info.get(
                        "applied_filters", {}
                    ),
                    "parsed_filters": first_result_query_info.get("parsed_filters", {}),
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
async def prometh_cortex_list_sources() -> Dict[str, Any]:
    """List all available document sources with metadata.

    Per-source chunking support (v0.3.0+): Get information about all configured sources
    including chunking parameters, source patterns, and document counts.

    Returns:
        Dictionary containing list of sources with metadata
    """
    try:
        # Lazy load index to get statistics
        indexer_instance = await lazy_load_index()
        if not indexer_instance:
            return {
                "error": "Indexer not initialized",
                "sources": [s.name for s in config.sources] if config else [],
            }

        # Get source information from indexer
        sources_info = indexer_instance.list_sources()

        # Format response
        response = {
            "collection_name": sources_info.get("collection_name", "prometh_cortex"),
            "sources": sources_info.get("sources", []),
            "total_sources": sources_info.get("total_sources", 0),
            "total_documents": sources_info.get("total_documents", 0),
        }

        # Add source names for quick reference
        response["source_names"] = [s["name"] for s in response.get("sources", [])]

        return response

    except Exception as e:
        logger.critical(f"List sources failed: {e}")
        return {
            "error": str(e),
            "sources": [s.name for s in config.sources] if config else [],
        }


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
            "vector_store_type": config.vector_store_type if config else "unknown",
        }

        # Unified collection + sources info
        if config:
            health_info["collection_name"] = (
                config.collection.name if config.collection else "prometh_cortex"
            )
            health_info["total_sources"] = len(config.sources)
            health_info["source_names"] = [s.name for s in config.sources]

        # Get indexer statistics if available
        try:
            # Try to lazy load index for health check
            indexer_instance = await lazy_load_index()
            if indexer_instance:
                try:
                    index_stats = indexer_instance.get_stats()
                    health_info.update(
                        {
                            "indexed_files": index_stats.get("total_vectors", 0),
                            "index_stats": index_stats,
                        }
                    )
                except Exception as e:
                    # Silently handle index stats failures
                    health_info.update(
                        {
                            "indexed_files": 0,
                            "index_stats": {
                                "status": "index_not_loaded",
                                "error": str(e),
                            },
                        }
                    )
            else:
                health_info.update(
                    {
                        "indexed_files": 0,
                        "index_stats": {"status": "indexer_not_initialized"},
                    }
                )
        except Exception as e:
            # If lazy loading fails, report it but don't crash (silent)
            health_info.update(
                {
                    "indexed_files": 0,
                    "index_stats": {"status": "index_loading_failed", "error": str(e)},
                }
            )

        # Add configuration info
        if config:
            config_info = {
                "total_sources": len(config.sources),
                "max_query_results": config.max_query_results,
            }

            # Add vector store specific info
            if config.vector_store_type == "faiss":
                config_info["rag_index_dir"] = str(config.rag_index_dir)
            else:
                config_info.update(
                    {
                        "qdrant_host": config.qdrant_host,
                        "qdrant_port": config.qdrant_port,
                        "qdrant_collection_name": config.qdrant_collection_name,
                        "qdrant_use_https": config.qdrant_use_https,
                    }
                )

            health_info.update(config_info)

        # Add timing
        health_check_time = (time.time() - start_time) * 1000
        health_info["health_check_time_ms"] = health_check_time

        return health_info

    except Exception as e:
        logger.critical(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e), "indexed_files": 0}


@mcp.tool()
async def prometh_cortex_memory(
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Store a memory document directly into the vector index for instant retrieval (v0.4.0+).

    Writes structured content (session summaries, decisions, patterns, lessons learned)
    directly into the Qdrant index under the prmth_memory source. Instantly queryable via
    prometh_cortex_query with source_type="prmth_memory".

    Use this tool to preserve high-value session insights without waiting for pcortex build.
    Content is deduped by title+content hash, so re-submitting identical summaries is idempotent.

    Args:
        title: Document title (used for search and deduplication)
        content: Markdown body (Context, Decisions, Patterns, Lessons, etc.)
        tags: Optional tags for filtering (e.g., ["session-export", "kubernetes", "incident"])
        metadata: Optional extra metadata dict (source_project, author, session_id, related_links, etc.)

    Returns:
        Dictionary with:
        - status: "success" or error message
        - document_id: Stable ID (memory_<content_hash[:16]>)
        - chunks_count: Number of chunks created
        - source_type: "prmth_memory"
        - created: ISO timestamp

    Example usage (from an agent):
        result = await prometh_cortex_memory(
            title="Kubernetes OOMKill Investigation",
            content="## Context\\nInvestigated OOMKill on app-pod-123...\\n## Decisions\\n- Increase memory limit to 2Gi\\n- Add monitoring alert...",
            tags=["kubernetes", "incident", "memory"],
            metadata={
                "source_project": "platform",
                "author": "prometh-memory",
                "session_id": "abc123"
            }
        )
    """
    try:
        # Lazy load index on first call
        indexer = await lazy_load_index()
        if not indexer:
            return {"error": "Indexer not initialized"}

        # Call indexer method to add memory document
        result = indexer.add_memory_document(
            title=title,
            content=content,
            tags=tags or [],
            metadata=metadata or {},
        )

        return result

    except IndexerError as e:
        logger.critical(f"Memory document error: {e}")
        return {"error": f"Indexer error: {e}"}
    except Exception as e:
        logger.critical(f"Memory document unexpected error: {e}")
        return {"error": f"Internal error: {e}"}


@mcp.tool()
async def prometh_cortex_memory_dream_prepare(project: str) -> Dict[str, Any]:
    """Fetch episodic memories for consolidation.

    Retrieves all active (dreaming=false) episodic memories for a project
    and any prior semantic memories. Used as the first step in the
    consolidation workflow: prepare → (LLM synthesis) → commit.

    Args:
        project: Project name to consolidate memories for (required)

    Returns:
        Dictionary with:
        - status: "success" or error message
        - to_consolidate: List of episodic memories (dreaming=false, memory_type=episodic)
        - prior_semantic: List of prior semantic memories (memory_type=semantic, used as context)
        - total_memories: Count of memories returned
    """
    try:
        indexer = await lazy_load_index()
        if not indexer:
            return {"error": "Indexer not initialized"}

        # Fetch active episodic memories (candidates for consolidation)
        episodic_memories = indexer.list_memories(
            project=project, dreaming=False
        )
        episodic_memories = [
            m for m in episodic_memories if m.get("memory_type") == "episodic"
        ]

        # Fetch prior semantic memories (to include as context, will be superseded)
        prior_semantic = indexer.list_memories(project=project, dreaming=False)
        prior_semantic = [
            m for m in prior_semantic if m.get("memory_type") == "semantic"
        ]

        logger.info(
            f"Dream prepare: {len(episodic_memories)} episodic + {len(prior_semantic)} prior semantic for project {project}"
        )

        return {
            "status": "success",
            "project": project,
            "to_consolidate": episodic_memories,
            "prior_semantic": prior_semantic,
            "total_memories": len(episodic_memories) + len(prior_semantic),
        }

    except Exception as e:
        logger.error(f"Dream prepare failed: {e}")
        return {"error": f"Failed to prepare memories: {e}"}


@mcp.tool()
async def prometh_cortex_memory_dream_commit(
    project: str,
    consolidated_content: str,
    consolidated_title: str,
    source_memory_ids: List[str],
    supersede_memory_ids: Optional[List[str]] = None,
    consolidation_version: int = 1,
) -> Dict[str, Any]:
    """Commit consolidated memory after LLM synthesis.

    Stores the new consolidated semantic memory and marks source memories
    as dreaming=true (consolidated-away). Optionally supersedes prior
    semantic memories if provided.

    Args:
        project: Project name
        consolidated_content: Full consolidated memory content (markdown)
        consolidated_title: Title for the consolidated memory
        source_memory_ids: List of episodic document_ids consumed in consolidation
        supersede_memory_ids: Optional list of prior semantic memory_ids being replaced
        consolidation_version: Version number for this consolidation run (default: 1)

    Returns:
        Dictionary with:
        - status: "success" or error message
        - consolidated_id: document_id of new consolidated memory
        - marked_dreaming: Count of memories marked dreaming=true
        - superseded: Count of prior semantics superseded
    """
    try:
        indexer = await lazy_load_index()
        if not indexer:
            return {"error": "Indexer not initialized"}

        supersede_memory_ids = supersede_memory_ids or []
        all_source_ids = source_memory_ids + supersede_memory_ids

        # Mark all source + superseded memories as dreaming=true
        for mem_id in all_source_ids:
            try:
                indexer.update_memory_metadata(
                    mem_id, {"dreaming": True, "consolidation_version": consolidation_version}
                )
            except Exception as e:
                logger.warning(f"Failed to mark {mem_id} as dreaming: {e}")

        # Store new consolidated memory
        result = indexer.add_memory_document(
            title=consolidated_title,
            content=consolidated_content,
            tags=["consolidated", f"v{consolidation_version}"],
            metadata={
                "project": project,
                "memory_type": "semantic",
                "dreaming": False,
                "consolidation_version": consolidation_version,
                "source_memories": source_memory_ids,
                "supersedes": supersede_memory_ids,
            },
        )

        if result.get("status") != "success":
            return {"error": f"Failed to store consolidated memory: {result}"}

        logger.info(
            f"Dream commit: new semantic {result['document_id']} consolidates {len(all_source_ids)} memories"
        )

        return {
            "status": "success",
            "consolidated_id": result["document_id"],
            "marked_dreaming": len(all_source_ids),
            "superseded": len(supersede_memory_ids),
            "consolidation_version": consolidation_version,
        }

    except Exception as e:
        logger.error(f"Dream commit failed: {e}")
        return {"error": f"Failed to commit consolidated memory: {e}"}


@mcp.tool()
async def prometh_cortex_memory_dream_revert(
    consolidation_id: str, delete_consolidated: bool = True
) -> Dict[str, Any]:
    """Revert a consolidation (mark source memories as active again).

    Restores source and superseded memories to dreaming=false,
    optionally deleting the consolidated semantic memory.

    Args:
        consolidation_id: document_id of the consolidated (semantic) memory to revert
        delete_consolidated: Whether to delete the consolidated memory (default: True)

    Returns:
        Dictionary with:
        - status: "success" or error message
        - restored_memories: Count of memories restored to active
        - deleted_consolidated: Whether consolidated memory was deleted
    """
    try:
        indexer = await lazy_load_index()
        if not indexer:
            return {"error": "Indexer not initialized"}

        # Fetch the consolidated memory to get source/superseded IDs
        consolidated_mem = indexer.list_memories()  # Fetch all, will filter
        consolidated_mem = [
            m for m in consolidated_mem if m.get("document_id") == consolidation_id
        ]

        if not consolidated_mem:
            return {"error": f"Consolidated memory not found: {consolidation_id}"}

        consolidated_mem = consolidated_mem[0]
        source_ids = consolidated_mem.get("source_memories", [])
        supersede_ids = consolidated_mem.get("supersedes", [])
        all_to_restore = source_ids + supersede_ids

        # Restore all source + superseded memories to dreaming=false
        restored_count = 0
        for mem_id in all_to_restore:
            try:
                indexer.update_memory_metadata(mem_id, {"dreaming": False})
                restored_count += 1
            except Exception as e:
                logger.warning(f"Failed to restore {mem_id}: {e}")

        # Delete consolidated memory if requested
        if delete_consolidated:
            try:
                indexer.delete_memories([consolidation_id])
            except Exception as e:
                logger.warning(f"Failed to delete consolidated memory {consolidation_id}: {e}")

        logger.info(
            f"Dream revert: restored {restored_count} memories, deleted={delete_consolidated}"
        )

        return {
            "status": "success",
            "restored_memories": restored_count,
            "deleted_consolidated": delete_consolidated,
        }

    except Exception as e:
        logger.error(f"Dream revert failed: {e}")
        return {"error": f"Failed to revert consolidation: {e}"}


def run_mcp_server(transport: str = "stdio", host: str = "127.0.0.1", port: int = 3100):
    """Run the MCP server with the specified transport.

    Args:
        transport: Transport protocol - "stdio", "sse", or "streamable-http"
        host: Host to bind to (only used for sse/streamable-http)
        port: Port to bind to (only used for sse/streamable-http)
    """
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
        max_startup_time = (
            getattr(config, "mcp_max_startup_time", 50.0) if config else 50.0
        )

        # Log startup time to stderr (won't interfere with MCP protocol on stdout)
        logger.critical(
            f"MCP server startup completed in {total_startup_time:.2f}s (max: {max_startup_time:.2f}s)"
        )

        if total_startup_time > max_startup_time:
            logger.critical(
                f"⚠️  STARTUP EXCEEDED TARGET: {total_startup_time:.2f}s > {max_startup_time:.2f}s"
            )
        else:
            logger.critical(
                f"✅ Startup within target: {total_startup_time:.2f}s < {max_startup_time:.2f}s"
            )

        # Run the MCP server with specified transport
        if transport == "stdio":
            mcp.run(transport="stdio")
        else:
            # Enforce authentication for network transports
            if not config or not config.mcp_auth_token:
                logger.critical(
                    "MCP_AUTH_TOKEN must be set when using SSE or streamable-http transport. "
                    "Set MCP_AUTH_TOKEN env var or auth_token in [server] config."
                )
                sys.exit(1)

            auth_verifier = StaticBearerTokenVerifier(config.mcp_auth_token)
            mcp.auth = auth_verifier
            logger.critical(
                f"Starting MCP server on {host}:{port} with {transport} transport (auth enabled)"
            )
            mcp.run(transport=transport, host=host, port=port)

    except Exception as e:
        total_startup_time = time.time() - startup_start_time
        logger.critical(
            f"MCP server startup failed after {total_startup_time:.2f}s: {e}"
        )
        sys.exit(1)
    finally:
        # Clean up background tasks on shutdown
        if cleanup_task and not cleanup_task.done():
            cleanup_task.cancel()


if __name__ == "__main__":
    run_mcp_server()
