"""Unit tests for MCP timeout handling components."""

import asyncio
import pytest
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from prometh_cortex.mcp.timeout_handler import (
    ProgressReporter,
    ChunkedQueryProcessor,
    AsyncOperationManager,
    StartupOptimizer,
    OperationStatus,
    ProgressReport,
    OperationResult
)


class TestProgressReporter:
    """Test progress reporter functionality."""
    
    @pytest.fixture
    def reporter(self):
        """Create a progress reporter with short update interval for testing."""
        return ProgressReporter(update_interval=0.1)
    
    @pytest.mark.asyncio
    async def test_progress_reporter_lifecycle(self, reporter):
        """Test complete progress reporting lifecycle."""
        operation_id = await reporter.start_operation("test-op", 60.0, "Starting test")
        
        assert operation_id in reporter._operations
        progress = await reporter.get_status(operation_id)
        assert progress.operation_id == operation_id
        assert progress.status == OperationStatus.IN_PROGRESS
        assert progress.progress == 0.0
        assert progress.message == "Starting test"
        
        # Update progress
        updated = await reporter.update_progress(operation_id, 0.5, "Half done")
        assert updated is True
        
        progress = await reporter.get_status(operation_id)
        assert progress.progress == 0.5
        assert progress.message == "Half done"
        
        # Complete operation
        await reporter.complete_operation(operation_id, {"result": "success"})
        
        progress = await reporter.get_status(operation_id)
        assert progress.status == OperationStatus.COMPLETED
        assert progress.progress == 1.0
    
    @pytest.mark.asyncio
    async def test_progress_update_throttling(self, reporter):
        """Test that progress updates are throttled."""
        operation_id = await reporter.start_operation("throttle-test", 10.0)
        
        # First update should work
        updated1 = await reporter.update_progress(operation_id, 0.1, "Update 1")
        assert updated1 is True
        
        # Immediate second update should be throttled
        updated2 = await reporter.update_progress(operation_id, 0.2, "Update 2")
        assert updated2 is False
        
        # After interval, should work again
        await asyncio.sleep(0.12)  # Slightly longer than update_interval
        updated3 = await reporter.update_progress(operation_id, 0.3, "Update 3")
        assert updated3 is True
    
    @pytest.mark.asyncio
    async def test_operation_failure(self, reporter):
        """Test operation failure handling."""
        operation_id = await reporter.start_operation("fail-test", 10.0)
        
        test_error = ValueError("Test error")
        await reporter.fail_operation(operation_id, test_error)
        
        progress = await reporter.get_status(operation_id)
        assert progress.status == OperationStatus.FAILED
        assert "Test error" in progress.message
    
    def test_cleanup_completed_operations(self, reporter):
        """Test cleanup of old operations."""
        # Create some fake old operations
        old_time = datetime.now() - timedelta(hours=25)
        
        old_progress = ProgressReport(
            operation_id="old-op",
            status=OperationStatus.COMPLETED,
            progress=1.0,
            message="Old operation",
            started_at=old_time
        )
        
        recent_progress = ProgressReport(
            operation_id="recent-op",
            status=OperationStatus.COMPLETED,
            progress=1.0,
            message="Recent operation",
            started_at=datetime.now()
        )
        
        reporter._operations["old-op"] = old_progress
        reporter._operations["recent-op"] = recent_progress
        
        # Run cleanup
        cleaned = reporter.cleanup_completed_operations(max_age_hours=24)
        
        assert cleaned == 1
        assert "old-op" not in reporter._operations
        assert "recent-op" in reporter._operations


class TestChunkedQueryProcessor:
    """Test chunked query processor."""
    
    @pytest.fixture
    def progress_reporter(self):
        return ProgressReporter(update_interval=0.01)
    
    @pytest.fixture
    def processor(self, progress_reporter):
        return ChunkedQueryProcessor(progress_reporter, default_chunk_size=3)
    
    @pytest.mark.asyncio
    async def test_chunked_query_processing(self, processor):
        """Test basic chunked query processing."""
        # Mock query function that returns different results for different chunks
        mock_results = [
            [{"doc": f"result_{i}"} for i in range(3)],  # First chunk
            [{"doc": f"result_{i}"} for i in range(3, 6)],  # Second chunk
            []  # Third chunk (empty, should stop)
        ]
        
        async def mock_query_func(query, max_results=None, skip=0):
            chunk_idx = skip // 3 if skip else 0
            if chunk_idx < len(mock_results):
                return mock_results[chunk_idx]
            return []
        
        all_chunks = []
        async for chunk_result in processor.process_chunked_query(
            mock_query_func,
            "test query",
            chunk_size=3,
            max_chunks=3
        ):
            all_chunks.append(chunk_result)
        
        assert len(all_chunks) == 2  # Should stop at empty chunk
        assert all_chunks[0]["chunk_count"] == 3
        assert all_chunks[1]["chunk_count"] == 3
        assert all_chunks[0]["total_results_so_far"] == 3
        assert all_chunks[1]["total_results_so_far"] == 6
    
    @pytest.mark.asyncio
    async def test_chunked_query_with_max_results(self, processor):
        """Test chunked query with max results limit."""
        async def mock_query_func(query, max_results=None, skip=0):
            return [{"doc": f"result_{i}"} for i in range(skip, skip + 3)]
        
        chunks = []
        async for chunk_result in processor.process_chunked_query(
            mock_query_func,
            "test query",
            chunk_size=3,
            max_chunks=5,
            max_results=5
        ):
            chunks.append(chunk_result)
            # Should stop when we reach max_results
            if chunk_result["total_results_so_far"] >= 5:
                break
        
        # Should have processed chunks until we hit max_results
        total_results = sum(chunk["chunk_count"] for chunk in chunks)
        assert total_results >= 5


class TestAsyncOperationManager:
    """Test async operation manager."""
    
    @pytest.fixture
    def progress_reporter(self):
        return ProgressReporter(update_interval=0.01)
    
    @pytest.fixture
    def manager(self, progress_reporter):
        return AsyncOperationManager(progress_reporter, max_concurrent_operations=3)
    
    @pytest.mark.asyncio
    async def test_submit_and_get_operation(self, manager):
        """Test submitting and retrieving async operations."""
        async def test_operation(result_value="success"):
            await asyncio.sleep(0.1)
            return result_value
        
        # Submit operation
        operation_id = await manager.submit_operation(test_operation, result_value="test_result")
        
        # Check initial status
        status = await manager.get_operation_status(operation_id)
        assert status.operation_id == operation_id
        assert status.status in [OperationStatus.PENDING, OperationStatus.IN_PROGRESS]
        
        # Wait for completion
        await asyncio.sleep(0.2)
        
        # Check final status
        status = await manager.get_operation_status(operation_id)
        assert status.status == OperationStatus.COMPLETED
        
        # Get result
        result = await manager.get_operation_result(operation_id)
        assert result == "test_result"
    
    @pytest.mark.asyncio
    async def test_operation_failure(self, manager):
        """Test handling of failed operations."""
        async def failing_operation():
            await asyncio.sleep(0.05)
            raise ValueError("Test failure")
        
        operation_id = await manager.submit_operation(failing_operation)
        
        # Wait for failure
        await asyncio.sleep(0.1)
        
        # Check status
        status = await manager.get_operation_status(operation_id)
        assert status.status == OperationStatus.FAILED
        assert "Test failure" in status.error
        
        # Getting result should raise exception
        with pytest.raises(RuntimeError, match="Operation failed"):
            await manager.get_operation_result(operation_id)
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_limit(self, manager):
        """Test concurrent operations limit."""
        async def long_operation():
            await asyncio.sleep(0.5)
            return "done"
        
        # Submit max concurrent operations
        operation_ids = []
        for i in range(3):  # max_concurrent_operations = 3
            op_id = await manager.submit_operation(long_operation)
            operation_ids.append(op_id)
        
        # Should reject additional operation
        with pytest.raises(RuntimeError, match="Too many concurrent operations"):
            await manager.submit_operation(long_operation)
        
        # Clean up
        for op_id in operation_ids:
            await manager.cancel_operation(op_id)
    
    @pytest.mark.asyncio
    async def test_operation_cancellation(self, manager):
        """Test operation cancellation."""
        async def long_operation():
            await asyncio.sleep(1.0)
            return "completed"
        
        operation_id = await manager.submit_operation(long_operation)
        
        # Cancel immediately
        cancelled = await manager.cancel_operation(operation_id)
        assert cancelled is True
        
        # Wait a bit
        await asyncio.sleep(0.1)
        
        # Check status
        status = await manager.get_operation_status(operation_id)
        assert status.status == OperationStatus.CANCELLED


class TestStartupOptimizer:
    """Test startup optimizer."""
    
    @pytest.fixture
    def progress_reporter(self):
        return ProgressReporter(update_interval=0.01)
    
    @pytest.fixture
    def optimizer(self, progress_reporter):
        return StartupOptimizer(progress_reporter, max_startup_time=1.0)  # Short timeout for tests
    
    @pytest.mark.asyncio
    async def test_startup_time_requirement(self, optimizer):
        """Test that startup completes within time limit."""
        start_time = time.time()
        
        async def mock_config_loader():
            await asyncio.sleep(0.1)
            return {"test": "config"}
        
        async def mock_indexer_factory():
            await asyncio.sleep(0.1)
            return Mock()
        
        await optimizer.initialize_server(mock_config_loader, mock_indexer_factory)
        
        startup_duration = time.time() - start_time
        assert startup_duration < 1.0, f"Startup took {startup_duration}s, exceeds 1.0s limit"
    
    @pytest.mark.asyncio
    async def test_startup_timeout_handling(self, optimizer):
        """Test handling of startup timeout."""
        async def slow_config_loader():
            await asyncio.sleep(2.0)  # Longer than max_startup_time
            return {"test": "config"}
        
        with pytest.raises(RuntimeError, match="Startup stage 'config' timed out"):
            await optimizer.initialize_server(slow_config_loader)
    
    @pytest.mark.asyncio
    async def test_lazy_index_loading(self, optimizer):
        """Test lazy index loading."""
        mock_indexer = Mock()
        mock_indexer.load_index = AsyncMock()
        
        # First call should load index
        await optimizer.lazy_load_index(mock_indexer)
        mock_indexer.load_index.assert_called_once()
        assert mock_indexer._index_loaded is True
        
        # Second call should not load again
        mock_indexer.load_index.reset_mock()
        await optimizer.lazy_load_index(mock_indexer)
        mock_indexer.load_index.assert_not_called()
    
    def test_startup_status_reporting(self, optimizer):
        """Test startup status reporting."""
        # Before startup
        status = optimizer.get_startup_status()
        assert status["status"] == "not_started"
        
        # During startup (simulate)
        optimizer._startup_start_time = time.time()
        status = optimizer.get_startup_status()
        assert status["status"] == "in_progress"
        assert "elapsed_time" in status
        assert "progress" in status


# Integration tests for timeout handling
class TestTimeoutIntegration:
    """Integration tests for timeout handling components."""
    
    @pytest.mark.asyncio
    async def test_chunked_processor_with_progress_reporting(self):
        """Test chunked processor integration with progress reporting."""
        reporter = ProgressReporter(update_interval=0.01)
        processor = ChunkedQueryProcessor(reporter, default_chunk_size=2)
        
        async def mock_query(query, max_results=None, skip=0):
            await asyncio.sleep(0.05)  # Simulate processing time
            chunk_idx = skip // 2 if skip else 0
            if chunk_idx < 3:
                return [f"result_{chunk_idx}_{i}" for i in range(2)]
            return []
        
        operation_id = None
        chunk_count = 0
        
        async for chunk_result in processor.process_chunked_query(
            mock_query, "test", chunk_size=2, max_chunks=3
        ):
            if operation_id is None:
                operation_id = chunk_result["operation_id"]
            chunk_count += 1
            
            # Check that progress is being reported
            progress = await reporter.get_status(operation_id)
            assert progress is not None
            assert progress.status == OperationStatus.IN_PROGRESS
        
        # Final progress should be completed
        final_progress = await reporter.get_status(operation_id)
        assert final_progress.status == OperationStatus.COMPLETED
        assert final_progress.progress == 1.0
        assert chunk_count == 3
    
    @pytest.mark.asyncio
    async def test_async_manager_with_progress_reporting(self):
        """Test async manager integration with progress reporting."""
        reporter = ProgressReporter(update_interval=0.01)
        manager = AsyncOperationManager(reporter, max_concurrent_operations=2)
        
        async def tracked_operation():
            await asyncio.sleep(0.1)
            return "operation_result"
        
        # Submit operation
        operation_id = await manager.submit_operation(tracked_operation)
        
        # Wait for completion
        await asyncio.sleep(0.15)
        
        # Check both manager and reporter status
        manager_status = await manager.get_operation_status(operation_id)
        assert manager_status.status == OperationStatus.COMPLETED
        assert manager_status.result == "operation_result"
        
        # Operation should exist in manager results
        assert operation_id in manager._results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])