"""MCP timeout handling components for preventing connection timeouts during long operations."""

import asyncio
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class OperationStatus(Enum):
    """Status of an async operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressReport:
    """Progress report for long-running operations."""
    operation_id: str
    status: OperationStatus
    progress: float  # 0.0 to 1.0
    message: str
    started_at: datetime
    estimated_completion: Optional[datetime] = None
    current_step: Optional[str] = None
    total_steps: Optional[int] = None
    completed_steps: int = 0


@dataclass 
class OperationResult:
    """Result of a completed operation."""
    operation_id: str
    status: OperationStatus
    result: Any = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    progress_history: List[ProgressReport] = field(default_factory=list)


class ProgressReporter:
    """Manages progress reporting for long-running MCP operations."""
    
    def __init__(self, update_interval: float = 5.0):
        """
        Initialize progress reporter.
        
        Args:
            update_interval: Minimum seconds between progress updates
        """
        self.update_interval = update_interval
        self._operations: Dict[str, ProgressReport] = {}
        self._last_update: Dict[str, float] = {}
        
    async def start_operation(self, operation_id: str, estimated_duration: float, message: str = "Starting operation") -> str:
        """
        Start tracking a new operation.
        
        Args:
            operation_id: Unique identifier for the operation
            estimated_duration: Expected duration in seconds
            message: Initial status message
            
        Returns:
            Operation ID
        """
        if not operation_id:
            operation_id = str(uuid.uuid4())
            
        now = datetime.now()
        estimated_completion = now + timedelta(seconds=estimated_duration) if estimated_duration > 0 else None
        
        progress = ProgressReport(
            operation_id=operation_id,
            status=OperationStatus.IN_PROGRESS,
            progress=0.0,
            message=message,
            started_at=now,
            estimated_completion=estimated_completion
        )
        
        self._operations[operation_id] = progress
        self._last_update[operation_id] = time.time()
        
        logger.debug(f"Started operation {operation_id}: {message}")
        return operation_id
    
    async def update_progress(self, operation_id: str, progress: float, message: str, 
                            current_step: Optional[str] = None, completed_steps: int = 0) -> bool:
        """
        Update progress for an operation.
        
        Args:
            operation_id: Operation to update
            progress: Progress value (0.0 to 1.0)
            message: Status message
            current_step: Current step description
            completed_steps: Number of completed steps
            
        Returns:
            True if update was sent (not throttled)
        """
        if operation_id not in self._operations:
            logger.warning(f"Attempted to update unknown operation: {operation_id}")
            return False
            
        now = time.time()
        last_update = self._last_update.get(operation_id, 0)
        
        # Throttle updates based on interval
        if now - last_update < self.update_interval:
            return False
            
        progress_report = self._operations[operation_id]
        progress_report.progress = min(1.0, max(0.0, progress))
        progress_report.message = message
        progress_report.current_step = current_step
        progress_report.completed_steps = completed_steps
        
        # Update estimated completion based on current progress
        if progress > 0 and progress_report.estimated_completion:
            elapsed = datetime.now() - progress_report.started_at
            estimated_total = elapsed.total_seconds() / progress
            progress_report.estimated_completion = progress_report.started_at + timedelta(seconds=estimated_total)
        
        self._last_update[operation_id] = now
        logger.debug(f"Updated operation {operation_id}: {progress:.1%} - {message}")
        return True
    
    async def complete_operation(self, operation_id: str, result: Any, message: str = "Operation completed") -> None:
        """
        Mark operation as completed.
        
        Args:
            operation_id: Operation to complete
            result: Operation result
            message: Completion message
        """
        if operation_id not in self._operations:
            logger.warning(f"Attempted to complete unknown operation: {operation_id}")
            return
            
        progress_report = self._operations[operation_id]
        progress_report.status = OperationStatus.COMPLETED
        progress_report.progress = 1.0
        progress_report.message = message
        
        logger.info(f"Completed operation {operation_id}: {message}")
    
    async def fail_operation(self, operation_id: str, error: Exception, message: str = None) -> None:
        """
        Mark operation as failed.
        
        Args:
            operation_id: Operation to fail
            error: Exception that caused failure
            message: Optional custom error message
        """
        if operation_id not in self._operations:
            logger.warning(f"Attempted to fail unknown operation: {operation_id}")
            return
            
        progress_report = self._operations[operation_id]
        progress_report.status = OperationStatus.FAILED
        progress_report.message = message or str(error)
        
        logger.error(f"Failed operation {operation_id}: {progress_report.message}")
    
    async def get_status(self, operation_id: str) -> Optional[ProgressReport]:
        """Get current status of an operation."""
        return self._operations.get(operation_id)
    
    def cleanup_completed_operations(self, max_age_hours: int = 24) -> int:
        """
        Remove old completed operations.
        
        Args:
            max_age_hours: Maximum age of completed operations to keep
            
        Returns:
            Number of operations cleaned up
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cleaned_count = 0
        
        for operation_id, progress in list(self._operations.items()):
            if (progress.status in [OperationStatus.COMPLETED, OperationStatus.FAILED] and 
                progress.started_at < cutoff_time):
                del self._operations[operation_id]
                self._last_update.pop(operation_id, None)
                cleaned_count += 1
                
        logger.debug(f"Cleaned up {cleaned_count} old operations")
        return cleaned_count


class ChunkedQueryProcessor:
    """Processes large queries in manageable chunks to prevent timeouts."""
    
    def __init__(self, progress_reporter: ProgressReporter, default_chunk_size: int = 50):
        """
        Initialize chunked query processor.
        
        Args:
            progress_reporter: Progress reporter instance
            default_chunk_size: Default number of documents per chunk
        """
        self.progress_reporter = progress_reporter
        self.default_chunk_size = default_chunk_size
    
    async def process_chunked_query(
        self,
        query_func: Callable,
        query: str,
        chunk_size: int = None,
        max_chunks: int = 10,
        max_results: int = None,
        operation_id: str = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a query in chunks with progress reporting.
        
        Args:
            query_func: Function to execute query (e.g., indexer.query)
            query: Search query
            chunk_size: Documents per chunk (default: instance default)
            max_chunks: Maximum number of chunks to process
            max_results: Maximum total results to return
            operation_id: Optional operation ID for progress tracking
            
        Yields:
            Dict containing chunk results and progress information
        """
        if chunk_size is None:
            chunk_size = self.default_chunk_size
            
        if operation_id is None:
            operation_id = str(uuid.uuid4())
        
        # Start progress reporting
        await self.progress_reporter.start_operation(
            operation_id, 
            estimated_duration=max_chunks * 5.0,  # Estimate 5 seconds per chunk
            message=f"Starting chunked query: {query[:50]}..."
        )
        
        all_results = []
        processed_chunks = 0
        
        try:
            for chunk_idx in range(max_chunks):
                chunk_start_time = time.time()
                
                # Update progress
                progress = chunk_idx / max_chunks
                await self.progress_reporter.update_progress(
                    operation_id,
                    progress,
                    f"Processing chunk {chunk_idx + 1}/{max_chunks}",
                    current_step=f"Chunk {chunk_idx + 1}",
                    completed_steps=chunk_idx
                )
                
                # Get results for this chunk with offset
                try:
                    chunk_results = await asyncio.to_thread(
                        query_func,
                        query,
                        max_results=chunk_size,
                        # Note: Real implementation would need skip/offset support in indexer
                        skip=chunk_idx * chunk_size
                    )
                except Exception as e:
                    # If skip/offset not supported, fall back to getting all and slicing
                    if chunk_idx == 0:
                        all_raw_results = await asyncio.to_thread(
                            query_func,
                            query,
                            max_results=max_chunks * chunk_size
                        )
                        chunk_results = all_raw_results[chunk_idx * chunk_size:(chunk_idx + 1) * chunk_size]
                    else:
                        chunk_results = all_raw_results[chunk_idx * chunk_size:(chunk_idx + 1) * chunk_size]
                
                if not chunk_results:
                    # No more results, break early
                    break
                
                all_results.extend(chunk_results)
                processed_chunks += 1
                
                chunk_time = time.time() - chunk_start_time
                
                # Yield chunk result
                yield {
                    "operation_id": operation_id,
                    "chunk_index": chunk_idx,
                    "chunk_results": chunk_results,
                    "chunk_count": len(chunk_results),
                    "total_results_so_far": len(all_results),
                    "progress": progress,
                    "processed_chunks": processed_chunks,
                    "total_chunks": max_chunks,
                    "chunk_processing_time_ms": chunk_time * 1000,
                    "estimated_time_remaining": (max_chunks - chunk_idx - 1) * chunk_time
                }
                
                # Stop if we have enough results
                if max_results and len(all_results) >= max_results:
                    break
                    
                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.1)
            
            # Complete the operation
            await self.progress_reporter.complete_operation(
                operation_id,
                all_results[:max_results] if max_results else all_results,
                f"Processed {processed_chunks} chunks, {len(all_results)} total results"
            )
            
        except Exception as e:
            await self.progress_reporter.fail_operation(operation_id, e)
            raise


class AsyncOperationManager:
    """Manages long-running operations with polling support."""
    
    def __init__(self, progress_reporter: ProgressReporter, max_concurrent_operations: int = 10):
        """
        Initialize async operation manager.
        
        Args:
            progress_reporter: Progress reporter instance
            max_concurrent_operations: Maximum concurrent operations
        """
        self.progress_reporter = progress_reporter
        self.max_concurrent_operations = max_concurrent_operations
        self._operations: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, OperationResult] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        
    async def submit_operation(self, operation: Callable, operation_id: str = None, **kwargs) -> str:
        """
        Submit an operation for async execution.
        
        Args:
            operation: Callable to execute
            operation_id: Optional operation ID
            **kwargs: Arguments to pass to operation
            
        Returns:
            Operation ID
        """
        if operation_id is None:
            operation_id = str(uuid.uuid4())
            
        if len(self._operations) >= self.max_concurrent_operations:
            raise RuntimeError(f"Too many concurrent operations (max: {self.max_concurrent_operations})")
        
        # Create operation result
        result = OperationResult(
            operation_id=operation_id,
            status=OperationStatus.PENDING
        )
        self._results[operation_id] = result
        
        # Submit task
        task = asyncio.create_task(self._execute_operation(operation_id, operation, **kwargs))
        self._operations[operation_id] = task
        
        logger.info(f"Submitted async operation {operation_id}")
        return operation_id
    
    async def _execute_operation(self, operation_id: str, operation: Callable, **kwargs) -> Any:
        """Execute an operation with progress tracking."""
        try:
            self._results[operation_id].status = OperationStatus.IN_PROGRESS
            
            # Execute the operation
            if asyncio.iscoroutinefunction(operation):
                result = await operation(**kwargs)
            else:
                result = await asyncio.to_thread(operation, **kwargs)
            
            # Store result
            operation_result = self._results[operation_id]
            operation_result.status = OperationStatus.COMPLETED
            operation_result.result = result
            operation_result.completed_at = datetime.now()
            
            logger.info(f"Completed async operation {operation_id}")
            return result
            
        except Exception as e:
            # Store error
            operation_result = self._results[operation_id]
            operation_result.status = OperationStatus.FAILED
            operation_result.error = str(e)
            operation_result.completed_at = datetime.now()
            
            logger.error(f"Failed async operation {operation_id}: {e}")
            raise
        finally:
            # Clean up task reference
            self._operations.pop(operation_id, None)
    
    async def get_operation_status(self, operation_id: str) -> Optional[OperationResult]:
        """Get status of an operation."""
        return self._results.get(operation_id)
    
    async def get_operation_result(self, operation_id: str) -> Any:
        """
        Get result of a completed operation.
        
        Args:
            operation_id: Operation ID
            
        Returns:
            Operation result
            
        Raises:
            ValueError: If operation doesn't exist or isn't completed
        """
        result = self._results.get(operation_id)
        if not result:
            raise ValueError(f"Operation {operation_id} not found")
            
        if result.status == OperationStatus.COMPLETED:
            return result.result
        elif result.status == OperationStatus.FAILED:
            raise RuntimeError(f"Operation failed: {result.error}")
        else:
            raise ValueError(f"Operation {operation_id} is not completed (status: {result.status})")
    
    async def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancel a running operation.
        
        Args:
            operation_id: Operation to cancel
            
        Returns:
            True if operation was cancelled
        """
        task = self._operations.get(operation_id)
        if task and not task.done():
            task.cancel()
            
            result = self._results.get(operation_id)
            if result:
                result.status = OperationStatus.CANCELLED
                result.completed_at = datetime.now()
            
            logger.info(f"Cancelled operation {operation_id}")
            return True
        return False
    
    def cleanup_completed_operations(self, max_age_hours: int = 24) -> int:
        """Clean up old completed operations."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cleaned_count = 0
        
        for operation_id, result in list(self._results.items()):
            if (result.status in [OperationStatus.COMPLETED, OperationStatus.FAILED, OperationStatus.CANCELLED] and
                result.completed_at and result.completed_at < cutoff_time):
                del self._results[operation_id]
                cleaned_count += 1
                
        logger.debug(f"Cleaned up {cleaned_count} old async operations")
        return cleaned_count


class StartupOptimizer:
    """Optimizes MCP server startup to meet <50s requirement."""
    
    def __init__(self, progress_reporter: ProgressReporter, max_startup_time: float = 50.0):
        """
        Initialize startup optimizer.
        
        Args:
            progress_reporter: Progress reporter instance
            max_startup_time: Maximum allowed startup time in seconds
        """
        self.progress_reporter = progress_reporter
        self.max_startup_time = max_startup_time
        self._startup_start_time = None
        self._initialization_stages = [
            ("config", "Loading configuration"),
            ("validation", "Validating configuration"),
            ("indexer", "Initializing indexer (lazy)"),
            ("server", "Starting MCP server"),
            ("ready", "Server ready")
        ]
    
    async def initialize_server(self, config_loader: Callable = None, indexer_factory: Callable = None) -> None:
        """
        Initialize server with startup optimization.
        
        Args:
            config_loader: Function to load configuration
            indexer_factory: Function to create indexer instance
        """
        operation_id = "server_startup"
        self._startup_start_time = time.time()
        
        await self.progress_reporter.start_operation(
            operation_id,
            estimated_duration=self.max_startup_time * 0.8,  # Target 80% of max time
            message="Starting MCP server initialization"
        )
        
        try:
            total_stages = len(self._initialization_stages)
            
            for idx, (stage, message) in enumerate(self._initialization_stages):
                stage_start = time.time()
                
                # Report progress
                progress = idx / total_stages
                await self.progress_reporter.update_progress(
                    operation_id,
                    progress,
                    message,
                    current_step=stage,
                    completed_steps=idx
                )
                
                # Execute stage
                if stage == "config" and config_loader:
                    await self._execute_with_timeout(config_loader, stage, 10.0)
                elif stage == "validation":
                    # Fast validation step
                    await asyncio.sleep(0.1)
                elif stage == "indexer" and indexer_factory:
                    # Create indexer but don't load index (lazy loading)
                    await self._execute_with_timeout(indexer_factory, stage, 15.0)
                elif stage == "server":
                    # Server setup (minimal)
                    await asyncio.sleep(0.1)
                elif stage == "ready":
                    # Final setup
                    await asyncio.sleep(0.1)
                
                stage_time = time.time() - stage_start
                logger.debug(f"Startup stage '{stage}' completed in {stage_time:.2f}s")
                
                # Check if we're approaching timeout
                elapsed = time.time() - self._startup_start_time
                if elapsed > self.max_startup_time * 0.9:
                    logger.warning(f"Startup taking longer than expected: {elapsed:.2f}s")
            
            # Complete startup
            total_time = time.time() - self._startup_start_time
            await self.progress_reporter.complete_operation(
                operation_id,
                {"startup_time": total_time},
                f"Server started successfully in {total_time:.2f}s"
            )
            
            if total_time > self.max_startup_time:
                logger.warning(f"Startup exceeded target time: {total_time:.2f}s > {self.max_startup_time}s")
            
        except Exception as e:
            elapsed = time.time() - self._startup_start_time
            await self.progress_reporter.fail_operation(
                operation_id, 
                e, 
                f"Server startup failed after {elapsed:.2f}s"
            )
            raise
    
    async def _execute_with_timeout(self, func: Callable, stage: str, timeout: float) -> Any:
        """Execute a function with timeout."""
        try:
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(func(), timeout=timeout)
            else:
                return await asyncio.wait_for(asyncio.to_thread(func), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Startup stage '{stage}' timed out after {timeout}s")
    
    async def lazy_load_index(self, indexer, operation_id: str = None) -> None:
        """
        Load index lazily on first use.
        
        Args:
            indexer: Indexer instance
            operation_id: Optional operation ID
        """
        if operation_id is None:
            operation_id = "lazy_index_load"
        
        if hasattr(indexer, '_index_loaded') and indexer._index_loaded:
            return  # Already loaded
        
        load_start = time.time()
        
        await self.progress_reporter.start_operation(
            operation_id,
            estimated_duration=30.0,  # Estimate 30 seconds for index loading
            message="Loading index for first query"
        )
        
        try:
            # Update progress during loading
            await self.progress_reporter.update_progress(
                operation_id, 0.2, "Initializing vector store"
            )
            
            # Load the index
            if asyncio.iscoroutinefunction(indexer.load_index):
                await indexer.load_index()
            else:
                await asyncio.to_thread(indexer.load_index)
            
            indexer._index_loaded = True
            
            load_time = time.time() - load_start
            await self.progress_reporter.complete_operation(
                operation_id,
                {"load_time": load_time},
                f"Index loaded successfully in {load_time:.2f}s"
            )
            
        except Exception as e:
            load_time = time.time() - load_start
            await self.progress_reporter.fail_operation(
                operation_id,
                e,
                f"Index loading failed after {load_time:.2f}s"
            )
            raise
    
    async def report_startup_progress(self, stage: str, progress: float) -> None:
        """Report startup progress (for external callers)."""
        logger.info(f"Startup progress: {stage} ({progress:.1%})")
    
    def get_startup_status(self) -> Dict[str, Any]:
        """Get current startup status."""
        if self._startup_start_time is None:
            return {"status": "not_started"}
        
        elapsed = time.time() - self._startup_start_time
        return {
            "status": "in_progress" if elapsed < self.max_startup_time else "timeout_risk",
            "elapsed_time": elapsed,
            "max_startup_time": self.max_startup_time,
            "progress": min(1.0, elapsed / self.max_startup_time)
        }