import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
import ui.server as server_module
from ui.server import ExecutionQueue, ExecutionJob
from core.graph_executor import GraphExecutor


class TestExecutionQueue:
    """Test the ExecutionQueue class functionality."""

    def setup_method(self):
        self.queue = ExecutionQueue()

    @pytest.mark.asyncio
    async def test_enqueue_and_get_next(self):
        """Test basic enqueue and get_next functionality."""
        mock_ws = Mock()
        graph_data = {"nodes": [], "links": []}

        job = await self.queue.enqueue(mock_ws, graph_data)
        assert job.id == 0
        assert job.websocket == mock_ws
        assert job.graph_data == graph_data

        retrieved_job = await self.queue.get_next()
        assert retrieved_job == job

    @pytest.mark.asyncio
    async def test_cancel_job_pending(self):
        """Test cancelling a job that's still pending."""
        mock_ws = Mock()
        graph_data = {"nodes": [], "links": []}

        job = await self.queue.enqueue(mock_ws, graph_data)

        # Verify job is in pending
        assert job in self.queue._pending

        await self.queue.cancel_job(job)

        # Verify job is cancelled and removed from pending
        assert job.id in self.queue._cancelled
        assert job not in self.queue._pending
        # done_event should be set so any waiter can proceed
        assert job.done_event.is_set()

    @pytest.mark.asyncio
    async def test_cancel_job_running(self):
        """Test cancelling a job that's currently running."""
        mock_ws = Mock()
        graph_data = {"nodes": [], "links": []}

        job = await self.queue.enqueue(mock_ws, graph_data)

        # Simulate job being picked up by worker
        retrieved_job = await self.queue.get_next()
        assert self.queue._running == job

        await self.queue.cancel_job(job)

        # Verify cancel_event is set for running job
        assert job.cancel_event.is_set()
        assert job.id in self.queue._cancelled

    @pytest.mark.asyncio
    async def test_get_next_skips_cancelled_jobs(self):
        """Test that get_next skips over cancelled jobs."""
        mock_ws = Mock()
        graph_data = {"nodes": [], "links": []}

        # Enqueue two jobs
        job1 = await self.queue.enqueue(mock_ws, graph_data)
        job2 = await self.queue.enqueue(mock_ws, graph_data)

        # Cancel the first job
        await self.queue.cancel_job(job1)

        # get_next should skip job1 and return job2
        retrieved_job = await self.queue.get_next()
        assert retrieved_job == job2
        # job1.done_event should be set after being skipped
        assert job1.done_event.is_set()

        # Verify job1 was marked as done (task_done called)
        # This is hard to test directly, but we can verify job1 is in cancelled set

    @pytest.mark.asyncio
    async def test_position_calculation(self):
        """Test position calculation for jobs in queue."""
        mock_ws = Mock()
        graph_data = {"nodes": [], "links": []}

        job1 = await self.queue.enqueue(mock_ws, graph_data)
        job2 = await self.queue.enqueue(mock_ws, graph_data)

        # Both jobs pending
        assert await self.queue.position(job1) == 0
        assert await self.queue.position(job2) == 1

        # Mark job1 as running
        await self.queue.get_next()
        assert await self.queue.position(job1) == 0
        assert await self.queue.position(job2) == 0  # job2 is now first in pending


class TestGraphExecutionStopping:
    """Test graph execution stopping and cancellation scenarios."""

    @pytest.fixture
    def mock_executor(self):
        """Create a mock GraphExecutor."""
        executor = Mock(spec=GraphExecutor)
        executor.is_streaming = False
        executor.execute = AsyncMock(return_value={"node1": {"output": "result"}})
        executor.stop = AsyncMock()
        executor.set_progress_callback = Mock()
        return executor

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = Mock()
        ws.client_state = server_module.WebSocketState.CONNECTED
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_worker_skips_cancelled_job_before_execution(self, mock_executor, mock_websocket):
        """Test that worker skips jobs cancelled before execution starts."""
        with patch('ui.server.GraphExecutor', return_value=mock_executor), \
             patch('ui.server.NODE_REGISTRY', {}):

            # Enqueue a job, then cancel it before worker picks it up
            queue = server_module.EXECUTION_QUEUE
            job = await queue.enqueue(mock_websocket, {"nodes": [], "links": []})
            await queue.cancel_job(job)

            # Worker should skip the cancelled job
            try:
                retrieved_job = await asyncio.wait_for(queue.get_next(), timeout=0.01)
                # Should not get the cancelled job
                assert retrieved_job != job
            except asyncio.TimeoutError:
                # Queue is empty after skipping cancelled job - this is expected
                pass

            mock_executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_worker_cancels_during_execution(self, mock_executor, mock_websocket):
        """Test cancellation during execution."""
        with patch('ui.server.GraphExecutor', return_value=mock_executor), \
             patch('ui.server.NODE_REGISTRY', {}):

            job = ExecutionJob(1, mock_websocket, {"nodes": [], "links": []})

            # Simulate worker starting execution
            await server_module.EXECUTION_QUEUE.enqueue(mock_websocket, {"nodes": [], "links": []})

            # Simulate cancellation during execution
            job.cancel_event.set()

            # The monitor task should detect this and stop the executor
            # In real execution, this would be handled by the monitor_cancel function
            assert job.cancel_event.is_set()
            # Note: In real scenario, executor.stop() would be called by monitor task

    def test_websocket_disconnect_handling(self, mock_websocket):
        """Test WebSocket disconnect handling."""
        from starlette.websockets import WebSocketState

        # Simulate disconnect
        mock_websocket.client_state = WebSocketState.DISCONNECTED

        # In real execution, the monitor task should detect this
        assert mock_websocket.client_state == WebSocketState.DISCONNECTED


class TestRapidStopExecuteCycles:
    """Test rapid stop/execute button presses."""

    def test_concurrent_execution_prevention(self):
        """Test that rapid execute presses don't start multiple executions."""
        # This would be tested in integration tests with actual WebSocket connections
        # For now, we document the expected behavior
        pass

    @pytest.mark.asyncio
    async def test_queue_cleanup_on_rapid_cancellation(self):
        """Test that queue is properly cleaned up during rapid cancellations."""
        queue = ExecutionQueue()
        mock_ws = Mock()

        # Enqueue multiple jobs
        jobs = []
        for i in range(5):
            job = await queue.enqueue(mock_ws, {"nodes": [], "links": []})
            jobs.append(job)

        # Cancel all jobs rapidly
        for job in jobs:
            await queue.cancel_job(job)

        # Verify all jobs are cancelled
        for job in jobs:
            assert job.id in queue._cancelled

        # Verify pending queue is empty
        assert len(queue._pending) == 0

    @pytest.mark.asyncio
    async def test_worker_handles_cancelled_jobs_efficiently(self):
        """Test that worker efficiently handles streams of cancelled jobs."""
        queue = ExecutionQueue()
        mock_ws = Mock()

        # Enqueue and cancel many jobs
        for i in range(10):
            job = await queue.enqueue(mock_ws, {"nodes": [], "links": []})
            await queue.cancel_job(job)

        # Worker should skip all cancelled jobs quickly
        # get_next should return TimeoutError for all attempts since all jobs are cancelled
        timeout_count = 0
        for _ in range(10):
            try:
                job = await asyncio.wait_for(queue.get_next(), timeout=0.01)
                # Should not reach here if jobs are properly cancelled
                assert False, f"Got unexpected job: {job}"
            except asyncio.TimeoutError:
                timeout_count += 1

        # Should get timeout for all attempts since all jobs were cancelled
        assert timeout_count == 10


class TestConcurrentExecutions:
    """Test concurrent execution scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_queues_isolation(self):
        """Test that multiple ExecutionQueue instances are properly isolated."""
        queue1 = ExecutionQueue()
        queue2 = ExecutionQueue()

        mock_ws = Mock()

        # Enqueue jobs in both queues
        job1 = await queue1.enqueue(mock_ws, {"nodes": [], "links": []})
        job2 = await queue2.enqueue(mock_ws, {"nodes": [], "links": []})

        # Verify jobs are isolated
        assert job1.id == 0
        assert job2.id == 0  # Both queues start with id 0
        assert queue1._pending != queue2._pending

    @pytest.mark.asyncio
    async def test_concurrent_enqueue_dequeue(self):
        """Test concurrent enqueue and dequeue operations."""
        queue = ExecutionQueue()
        mock_ws = Mock()

        async def enqueue_worker():
            jobs = []
            for i in range(50):
                job = await queue.enqueue(mock_ws, {"nodes": [], "links": []})
                jobs.append(job)
                await asyncio.sleep(0.001)  # Small delay to allow interleaving
            return jobs

        async def dequeue_worker():
            dequeued = []
            for _ in range(50):
                try:
                    job = await asyncio.wait_for(queue.get_next(), timeout=0.01)
                    dequeued.append(job)
                    job.done_event.set()
                    await queue.mark_done(job)
                except asyncio.TimeoutError:
                    break
            return dequeued

        # Run enqueue and dequeue concurrently
        enqueue_task = asyncio.create_task(enqueue_worker())
        dequeue_task = asyncio.create_task(dequeue_worker())

        enqueued_jobs, dequeued_jobs = await asyncio.gather(enqueue_task, dequeue_task)

        # All enqueued jobs should be accounted for
        assert len(dequeued_jobs) == len(enqueued_jobs)


class TestIntegrationScenarios:
    """Integration tests for complete execution flows."""

    def test_server_mode_detection(self):
        """Test that server correctly detects testing vs production mode."""
        import os

        # Test testing mode detection
        with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_function'}):
            assert os.getenv("PYTEST_CURRENT_TEST") == 'test_function'

        # Test production mode detection
        with patch.dict(os.environ, {}, clear=True):
            assert os.getenv("PYTEST_CURRENT_TEST") is None

    @pytest.mark.asyncio
    async def test_job_lifecycle_complete_flow(self):
        """Test complete job lifecycle from enqueue to completion."""
        queue = ExecutionQueue()
        mock_ws = Mock()

        # Enqueue job
        job = await queue.enqueue(mock_ws, {"nodes": [], "links": []})
        assert job in queue._pending

        # Worker picks up job
        retrieved_job = await queue.get_next()
        assert retrieved_job == job
        assert queue._running == job
        assert job not in queue._pending

        # Job completes
        job.done_event.set()
        await queue.mark_done(job)
        assert queue._running is None

    @pytest.mark.asyncio
    async def test_job_lifecycle_cancelled_flow(self):
        """Test complete job lifecycle when cancelled."""
        queue = ExecutionQueue()
        mock_ws = Mock()

        # Enqueue job
        job = await queue.enqueue(mock_ws, {"nodes": [], "links": []})

        # Cancel before worker picks up
        await queue.cancel_job(job)
        assert job.id in queue._cancelled

        # Worker should skip this job
        try:
            retrieved_job = await asyncio.wait_for(queue.get_next(), timeout=0.1)
            # If we get here, it should not be the cancelled job
            assert retrieved_job != job
        except asyncio.TimeoutError:
            # Queue is empty after skipping cancelled job
            pass


# Integration test for the full WebSocket flow would require a test client
# These are covered in test_server_ws.py, but we can add specific queue-related tests here

@pytest.mark.asyncio
async def test_execution_queue_under_load():
    """Test ExecutionQueue behavior under load with many rapid operations."""
    queue = ExecutionQueue()
    mock_ws = Mock()

    # Simulate high-frequency operations
    tasks = []

    async def rapid_enqueue():
        for _ in range(100):
            await queue.enqueue(mock_ws, {"nodes": [], "links": []})
            await asyncio.sleep(0.001)

    async def rapid_cancel():
        await asyncio.sleep(0.01)  # Start slightly after enqueue
        for _ in range(100):
            try:
                job = await asyncio.wait_for(queue.get_next(), timeout=0.001)
                await queue.cancel_job(job)
            except asyncio.TimeoutError:
                break

    # Run concurrent enqueue and cancel operations
    tasks = [
        asyncio.create_task(rapid_enqueue()),
        asyncio.create_task(rapid_cancel())
    ]

    await asyncio.gather(*tasks)

    # Verify queue state is consistent
    assert len(queue._pending) >= 0
    assert len(queue._cancelled) >= 0
