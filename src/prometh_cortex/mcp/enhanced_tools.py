"""Enhanced MCP tools with timeout handling capabilities."""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional
import logging

from fastmcp import FastMCP

from prometh_cortex.mcp.timeout_handler import (
    ProgressReporter, 
    ChunkedQueryProcessor, 
    AsyncOperationManager,
    OperationStatus
)

logger = logging.getLogger(__name__)

# Global instances for timeout handling - initialized by setup_enhanced_tools
progress_reporter = None
chunked_processor = None
async_manager = None


async def setup_enhanced_tools(mcp: FastMCP, indexer, config):
    """Setup enhanced MCP tools with timeout handling."""
    global progress_reporter, chunked_processor, async_manager
    
    # Initialize components with configuration values
    progress_interval = getattr(config, 'mcp_progress_interval', 5)
    chunk_size = getattr(config, 'mcp_chunk_size', 50)  
    max_concurrent = getattr(config, 'mcp_max_concurrent_ops', 10)
    
    progress_reporter = ProgressReporter(update_interval=progress_interval)
    chunked_processor = ChunkedQueryProcessor(progress_reporter, default_chunk_size=chunk_size)
    async_manager = AsyncOperationManager(progress_reporter, max_concurrent_operations=max_concurrent)
    
    logger.debug(f"Initialized timeout components: interval={progress_interval}s, chunk_size={chunk_size}, max_concurrent={max_concurrent}")
    
    @mcp.tool()
    async def prometh_cortex_query_chunked(
        query: str,
        max_results: Optional[int] = None,
        chunk_size: int = 50,
        progress_callback: bool = True,
        timeout_seconds: int = 300,
        filters: Optional[Dict[str, Any]] = None,
        include_full_content: bool = False
    ) -> Dict[str, Any]:
        """
        Query with chunked processing and progress reporting to handle large result sets.
        
        This tool processes large queries in manageable chunks to prevent timeouts while
        providing real-time progress feedback.
        
        Args:
            query: The search query text
            max_results: Maximum number of total results to return
            chunk_size: Number of documents to process per chunk (default: 50)
            progress_callback: Enable progress reporting (default: True)
            timeout_seconds: Maximum time to spend on query (default: 300s)
            filters: Optional additional filters
            include_full_content: Load complete document content
            
        Returns:
            Dictionary containing chunked results with progress information:
            {
                "operation_id": "uuid-string",
                "status": "in_progress|completed|failed",
                "progress": 0.0-1.0,
                "partial_results": [...],
                "total_chunks": int,
                "completed_chunks": int,
                "processing_time_ms": float,
                "estimated_time_remaining": float
            }
        """
        try:
            operation_id = str(uuid.uuid4())
            start_time = time.time()
            
            # Ensure indexer is loaded
            if not hasattr(indexer, '_index_loaded') or not indexer._index_loaded:
                await progress_reporter.start_operation(
                    operation_id + "_index_load",
                    estimated_duration=30.0,
                    message="Loading index for first query"
                )
                await asyncio.to_thread(indexer.load_index)
                indexer._index_loaded = True
                await progress_reporter.complete_operation(
                    operation_id + "_index_load",
                    None,
                    "Index loaded successfully"
                )
            
            # Determine max results
            if max_results is None:
                max_results = config.max_query_results
            
            max_chunks = min(10, (max_results + chunk_size - 1) // chunk_size)
            all_results = []
            completed_chunks = 0
            
            # Start chunked processing
            await progress_reporter.start_operation(
                operation_id,
                estimated_duration=min(timeout_seconds * 0.8, max_chunks * 10.0),
                message=f"Starting chunked query: {query[:50]}..."
            )
            
            async def query_wrapper(q, max_r, skip=None):
                """Wrapper for indexer query to handle sync/async."""
                # For now, treat as sync since current indexer is sync
                return indexer.query(q, max_results=max_r, filters=filters)
            
            # Process chunks
            async for chunk_result in chunked_processor.process_chunked_query(
                query_wrapper,
                query,
                chunk_size=chunk_size,
                max_chunks=max_chunks,
                max_results=max_results,
                operation_id=operation_id
            ):
                chunk_results = chunk_result["chunk_results"]
                all_results.extend(chunk_results)
                completed_chunks += 1
                
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    await progress_reporter.fail_operation(
                        operation_id,
                        TimeoutError(f"Query timed out after {elapsed:.2f}s"),
                        "Query timeout exceeded"
                    )
                    break
                
                # Update progress
                progress = completed_chunks / max_chunks
                await progress_reporter.update_progress(
                    operation_id,
                    progress,
                    f"Processed {completed_chunks}/{max_chunks} chunks, {len(all_results)} results",
                    completed_steps=completed_chunks
                )
            
            # Complete operation
            total_time = (time.time() - start_time) * 1000
            
            # Get final progress status
            progress_status = await progress_reporter.get_status(operation_id)
            
            response = {
                "operation_id": operation_id,
                "status": progress_status.status.value if progress_status else "completed",
                "progress": progress_status.progress if progress_status else 1.0,
                "results": all_results[:max_results] if max_results else all_results,
                "total_results": len(all_results),
                "total_chunks": max_chunks,
                "completed_chunks": completed_chunks,
                "processing_time_ms": total_time,
                "chunk_size": chunk_size,
                "query": query
            }
            
            # Add progress history if available
            if progress_status:
                response.update({
                    "started_at": progress_status.started_at.isoformat(),
                    "estimated_completion": progress_status.estimated_completion.isoformat() if progress_status.estimated_completion else None,
                    "message": progress_status.message
                })
            
            return response
            
        except Exception as e:
            logger.error(f"Chunked query failed: {e}")
            return {
                "operation_id": operation_id if 'operation_id' in locals() else "unknown",
                "status": "failed",
                "error": str(e),
                "results": [],
                "total_results": 0
            }
    
    @mcp.tool()
    async def prometh_cortex_query_async(
        query: str,
        max_results: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        include_full_content: bool = False
    ) -> Dict[str, Any]:
        """
        Submit query for async processing to handle very long-running operations.
        
        This tool submits queries for background processing and returns immediately
        with an operation ID that can be polled for status and results.
        
        Args:
            query: The search query text
            max_results: Maximum number of results to return
            filters: Optional additional filters
            include_full_content: Load complete document content
            
        Returns:
            Dictionary containing operation submission info:
            {
                "operation_id": "uuid-string",
                "status": "submitted",
                "estimated_duration": seconds,
                "poll_interval": seconds,
                "message": "Operation submitted successfully"
            }
        """
        try:
            # Define the async operation
            async def async_query_operation():
                """Execute the query asynchronously."""
                # Ensure indexer is loaded
                if not hasattr(indexer, '_index_loaded') or not indexer._index_loaded:
                    await asyncio.to_thread(indexer.load_index)
                    indexer._index_loaded = True
                
                # Determine max results
                query_max_results = max_results or config.max_query_results
                
                # Execute query
                results = await asyncio.to_thread(
                    indexer.query,
                    query,
                    max_results=query_max_results,
                    filters=filters
                )
                
                # Format response
                return {
                    "results": results,
                    "query": query,
                    "total_results": len(results),
                    "max_results": query_max_results,
                    "include_full_content": include_full_content
                }
            
            # Submit operation
            operation_id = await async_manager.submit_operation(async_query_operation)
            
            # Estimate duration based on max_results
            estimated_results = max_results or config.max_query_results
            estimated_duration = min(300, max(30, estimated_results * 0.5))  # 0.5s per result, 30s-300s range
            
            return {
                "operation_id": operation_id,
                "status": "submitted",
                "estimated_duration": estimated_duration,
                "poll_interval": 10,  # Recommend polling every 10 seconds
                "message": f"Query submitted for async processing: {query[:100]}...",
                "query": query
            }
            
        except Exception as e:
            logger.error(f"Async query submission failed: {e}")
            return {
                "operation_id": None,
                "status": "failed",
                "error": str(e),
                "message": "Failed to submit query for async processing"
            }
    
    @mcp.tool()
    async def prometh_cortex_get_operation_status(
        operation_id: str
    ) -> Dict[str, Any]:
        """
        Get status and results of async operation.
        
        Use this tool to check the progress of operations submitted via
        prometh_cortex_query_async or to monitor chunked query progress.
        
        Args:
            operation_id: Operation ID returned from async query submission
            
        Returns:
            Dictionary containing operation status:
            {
                "operation_id": str,
                "status": "pending|in_progress|completed|failed|cancelled",
                "progress": 0.0-1.0,
                "result": Any | None,
                "error": str | None,
                "started_at": datetime,
                "completed_at": datetime | None,
                "estimated_completion": datetime | None,
                "message": str
            }
        """
        try:
            # Check async operation status first
            async_result = await async_manager.get_operation_status(operation_id)
            
            if async_result:
                response = {
                    "operation_id": operation_id,
                    "status": async_result.status.value,
                    "started_at": async_result.started_at.isoformat(),
                    "completed_at": async_result.completed_at.isoformat() if async_result.completed_at else None,
                    "progress": 1.0 if async_result.status == OperationStatus.COMPLETED else 0.8
                }
                
                if async_result.status == OperationStatus.COMPLETED:
                    response["result"] = async_result.result
                    response["message"] = "Operation completed successfully"
                elif async_result.status == OperationStatus.FAILED:
                    response["error"] = async_result.error
                    response["message"] = f"Operation failed: {async_result.error}"
                else:
                    response["message"] = "Operation in progress"
                
                return response
            
            # Check progress reporter status
            progress_status = await progress_reporter.get_status(operation_id)
            
            if progress_status:
                return {
                    "operation_id": operation_id,
                    "status": progress_status.status.value,
                    "progress": progress_status.progress,
                    "message": progress_status.message,
                    "started_at": progress_status.started_at.isoformat(),
                    "estimated_completion": progress_status.estimated_completion.isoformat() if progress_status.estimated_completion else None,
                    "current_step": progress_status.current_step,
                    "completed_steps": progress_status.completed_steps,
                    "total_steps": progress_status.total_steps
                }
            
            # Operation not found
            return {
                "operation_id": operation_id,
                "status": "not_found",
                "error": "Operation not found or expired",
                "message": f"No operation found with ID: {operation_id}"
            }
            
        except Exception as e:
            logger.error(f"Failed to get operation status: {e}")
            return {
                "operation_id": operation_id,
                "status": "error",
                "error": str(e),
                "message": "Failed to retrieve operation status"
            }
    
    @mcp.tool()
    async def prometh_cortex_cancel_operation(
        operation_id: str
    ) -> Dict[str, Any]:
        """
        Cancel a running async operation.
        
        Args:
            operation_id: Operation ID to cancel
            
        Returns:
            Dictionary containing cancellation result
        """
        try:
            cancelled = await async_manager.cancel_operation(operation_id)
            
            if cancelled:
                return {
                    "operation_id": operation_id,
                    "status": "cancelled",
                    "message": "Operation cancelled successfully"
                }
            else:
                return {
                    "operation_id": operation_id,
                    "status": "not_cancelled",
                    "message": "Operation could not be cancelled (not found or already completed)"
                }
                
        except Exception as e:
            logger.error(f"Failed to cancel operation: {e}")
            return {
                "operation_id": operation_id,
                "status": "error",
                "error": str(e),
                "message": "Failed to cancel operation"
            }
    
    @mcp.tool()
    async def prometh_cortex_timeout_health() -> Dict[str, Any]:
        """
        Get health status for timeout handling components.
        
        Returns:
            Dictionary containing timeout system health information
        """
        try:
            # Clean up old operations
            cleaned_progress = progress_reporter.cleanup_completed_operations(max_age_hours=24)
            cleaned_async = async_manager.cleanup_completed_operations(max_age_hours=24)
            
            return {
                "status": "healthy",
                "active_operations": {
                    "progress_tracked": len(progress_reporter._operations),
                    "async_running": len(async_manager._operations),
                    "async_completed": len(async_manager._results)
                },
                "cleanup": {
                    "cleaned_progress_operations": cleaned_progress,
                    "cleaned_async_operations": cleaned_async
                },
                "configuration": {
                    "progress_update_interval": progress_reporter.update_interval,
                    "max_concurrent_operations": async_manager.max_concurrent_operations,
                    "default_chunk_size": chunked_processor.default_chunk_size
                },
                "capabilities": [
                    "chunked_query_processing",
                    "async_operation_management", 
                    "progress_reporting",
                    "operation_cancellation",
                    "automatic_cleanup"
                ]
            }
            
        except Exception as e:
            logger.error(f"Timeout health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": "Timeout handling system health check failed"
            }


async def cleanup_timeout_operations(config=None):
    """Periodic cleanup task for timeout operations."""
    # Get cleanup interval from config
    cleanup_interval = getattr(config, 'mcp_cleanup_interval', 300) if config else 300
    operation_ttl_hours = getattr(config, 'mcp_operation_ttl', 1800) // 3600 if config else 24  # Convert seconds to hours
    
    while True:
        try:
            # Clean up at configured interval  
            await asyncio.sleep(cleanup_interval)
            
            # Clean up old operations
            if progress_reporter and async_manager:
                progress_cleaned = progress_reporter.cleanup_completed_operations(max_age_hours=operation_ttl_hours)
                async_cleaned = async_manager.cleanup_completed_operations(max_age_hours=operation_ttl_hours)
                
                if progress_cleaned > 0 or async_cleaned > 0:
                    logger.info(f"Cleaned up {progress_cleaned} progress operations and {async_cleaned} async operations")
                
        except Exception as e:
            logger.error(f"Cleanup task failed: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying


def get_timeout_components():
    """Get timeout handling components for external use."""
    return {
        "progress_reporter": progress_reporter,
        "chunked_processor": chunked_processor,
        "async_manager": async_manager
    }