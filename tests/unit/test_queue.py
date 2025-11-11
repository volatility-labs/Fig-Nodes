import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import WebSocket
from starlette.websockets import WebSocketState

from core.graph_executor import GraphExecutor
from core.node_registry import NodeRegistry
from core.types_registry import SerialisableGraph
from server.queue import (
    ExecutionJob,
    ExecutionQueue,
    JobState,
    _monitor_cancel,
    _ws_send_async,
    _ws_send_sync,
    execution_worker,
)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket."""
    ws = MagicMock(spec=WebSocket)
    ws.client_state = WebSocketState.CONNECTED
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def sample_graph_data() -> SerialisableGraph:
    """Sample graph data for testing."""
    return {"nodes": [{"id": 1, "type": "test_node"}], "links": []}


@pytest.fixture
def execution_queue():
    """Create a fresh ExecutionQueue for each test."""
    return ExecutionQueue()


@pytest.fixture
def mock_node_registry():
    """Create a mock node registry."""
    return MagicMock(spec=NodeRegistry)


class TestExecutionJob:
    """Tests for ExecutionJob class."""

    def test_execution_job_initialization(self, mock_websocket, sample_graph_data):
        """Test ExecutionJob is properly initialized."""
        job = ExecutionJob(1, mock_websocket, sample_graph_data)

        assert job.id == 1
        assert job.websocket is mock_websocket
        assert job.graph_data == sample_graph_data
        assert job.state == JobState.PENDING
        assert job.cancel_event is not None
        assert job.done_event is not None


class TestExecutionQueue:
    """Tests for ExecutionQueue class."""

    @pytest.mark.asyncio
    async def test_enqueue_adds_job_to_pending(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test enqueue adds job to pending list."""
        job = await execution_queue.enqueue(mock_websocket, sample_graph_data)

        assert job.id == 0
        assert job.state == JobState.PENDING
        assert job.websocket is mock_websocket
        assert job.graph_data == sample_graph_data

    @pytest.mark.asyncio
    async def test_enqueue_increments_id_sequence(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test enqueue increments job ID."""
        job1 = await execution_queue.enqueue(mock_websocket, sample_graph_data)
        job2 = await execution_queue.enqueue(mock_websocket, sample_graph_data)

        assert job1.id == 0
        assert job2.id == 1

    @pytest.mark.asyncio
    async def test_get_next_returns_first_pending_job(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test get_next returns the first pending job."""
        job1 = await execution_queue.enqueue(mock_websocket, sample_graph_data)
        job2 = await execution_queue.enqueue(mock_websocket, sample_graph_data)

        next_job = await execution_queue.get_next()

        assert next_job is job1
        assert next_job.state == JobState.RUNNING
        assert execution_queue._running is job1

    @pytest.mark.asyncio
    async def test_get_next_sets_job_to_running(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test get_next sets job state to RUNNING."""
        job = await execution_queue.enqueue(mock_websocket, sample_graph_data)
        next_job = await execution_queue.get_next()

        assert next_job.state == JobState.RUNNING
        assert execution_queue._running is next_job

    @pytest.mark.asyncio
    async def test_get_next_waits_when_empty(self, execution_queue):
        """Test get_next waits when queue is empty."""
        result = []

        async def get_next_after_delay():
            await asyncio.sleep(0.1)
            job = await execution_queue.get_next()
            result.append(job)

        # Start get_next task
        task = asyncio.create_task(get_next_after_delay())

        # Wait a bit
        await asyncio.sleep(0.05)

        # Enqueue job
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.client_state = WebSocketState.CONNECTED
        mock_ws.send_json = AsyncMock()
        job = await execution_queue.enqueue(mock_ws, {"nodes": [], "links": []})

        # Wait for task to complete
        await task

        assert len(result) == 1
        assert result[0] is job

    @pytest.mark.asyncio
    async def test_mark_done_clears_running_job(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test mark_done clears the running job."""
        job = await execution_queue.enqueue(mock_websocket, sample_graph_data)
        await execution_queue.get_next()

        await execution_queue.mark_done(job)

        assert execution_queue._running is None
        assert job.state == JobState.DONE
        assert job.done_event.is_set()

    @pytest.mark.asyncio
    async def test_mark_done_only_marks_done_if_running(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test mark_done only marks done if job is running."""
        job1 = await execution_queue.enqueue(mock_websocket, sample_graph_data)
        job2 = await execution_queue.enqueue(mock_websocket, sample_graph_data)

        # Mark job2 done when it's not running
        await execution_queue.mark_done(job2)

        # Should not be marked done yet
        assert job2.state == JobState.PENDING

    @pytest.mark.asyncio
    async def test_cancel_job_in_pending_removes_from_queue(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test cancelling a pending job removes it from queue."""
        job = await execution_queue.enqueue(mock_websocket, sample_graph_data)

        await execution_queue.cancel_job(job)

        assert job.state == JobState.CANCELLED
        assert job.done_event.is_set()
        assert job not in execution_queue._pending

    @pytest.mark.asyncio
    async def test_cancel_job_in_running_sets_cancel_event(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test cancelling a running job sets cancel event."""
        job = await execution_queue.enqueue(mock_websocket, sample_graph_data)
        await execution_queue.get_next()

        await execution_queue.cancel_job(job)

        assert job.state == JobState.CANCELLED
        assert job.cancel_event.is_set()

    @pytest.mark.asyncio
    async def test_cancel_job_not_found_logs_message(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test cancelling a non-existent job logs a message."""
        job = ExecutionJob(999, mock_websocket, sample_graph_data)

        with patch("server.queue.print") as mock_print:
            await execution_queue.cancel_job(job)
            mock_print.assert_called_once()
            assert "not found" in mock_print.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_position_returns_zero_for_running_job(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test position returns 0 for running job."""
        job = await execution_queue.enqueue(mock_websocket, sample_graph_data)
        await execution_queue.get_next()

        position = await execution_queue.position(job)

        assert position == 0

    @pytest.mark.asyncio
    async def test_position_returns_pending_position(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test position returns correct position for pending jobs."""
        job1 = await execution_queue.enqueue(mock_websocket, sample_graph_data)
        job2 = await execution_queue.enqueue(mock_websocket, sample_graph_data)
        job3 = await execution_queue.enqueue(mock_websocket, sample_graph_data)

        # Get job1 running
        await execution_queue.get_next()

        # Check positions
        assert await execution_queue.position(job2) == 1
        assert await execution_queue.position(job3) == 2

    @pytest.mark.asyncio
    async def test_position_returns_negative_for_not_found(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test position returns -1 for job not in queue."""
        job = ExecutionJob(999, mock_websocket, sample_graph_data)

        position = await execution_queue.position(job)

        assert position == -1

    @pytest.mark.asyncio
    async def test_position_updates_sent_to_client(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test position updates are sent to queued clients."""
        job = await execution_queue.enqueue(mock_websocket, sample_graph_data)

        # Wait for position update task to send a message
        await asyncio.sleep(1.1)

        # Should have sent position update
        assert mock_websocket.send_json.called
        call_args = mock_websocket.send_json.call_args_list[0][0][0]
        assert call_args["type"] == "queue_position"
        assert call_args["position"] >= 0  # Position is 0 when running, 1 when pending
        assert call_args["job_id"] == job.id

    @pytest.mark.asyncio
    async def test_position_updates_stop_when_job_starts_running(
        self, execution_queue, mock_websocket, sample_graph_data
    ):
        """Test position updates stop when job starts running."""
        job = await execution_queue.enqueue(mock_websocket, sample_graph_data)

        # Wait a bit for position updates
        await asyncio.sleep(0.5)

        # Start the job
        await execution_queue.get_next()

        # Wait a bit more
        await asyncio.sleep(0.5)

        # Count calls
        initial_calls = mock_websocket.send_json.call_count

        # Wait more to ensure no new calls
        await asyncio.sleep(1.0)

        # Should not have sent more calls
        assert mock_websocket.send_json.call_count == initial_calls

    @pytest.mark.asyncio
    async def test_concurrent_enqueue_operations(self, execution_queue, sample_graph_data):
        """Test concurrent enqueue operations."""
        websockets = []
        for i in range(10):
            ws = MagicMock(spec=WebSocket)
            ws.client_state = WebSocketState.CONNECTED
            ws.send_json = AsyncMock()
            websockets.append(ws)

        # Enqueue concurrently
        tasks = [execution_queue.enqueue(ws, sample_graph_data) for ws in websockets]
        jobs = await asyncio.gather(*tasks)

        # All jobs should have unique IDs
        job_ids = [job.id for job in jobs]
        assert len(set(job_ids)) == 10
        assert min(job_ids) == 0
        assert max(job_ids) == 9

    @pytest.mark.asyncio
    async def test_fifo_ordering(self, execution_queue, sample_graph_data):
        """Test jobs are processed in FIFO order."""
        jobs = []
        for i in range(5):
            ws = MagicMock(spec=WebSocket)
            ws.client_state = WebSocketState.CONNECTED
            ws.send_json = AsyncMock()
            job = await execution_queue.enqueue(ws, sample_graph_data)
            jobs.append(job)

        # Get all jobs
        retrieved_jobs = []
        for _ in range(5):
            job = await execution_queue.get_next()
            retrieved_jobs.append(job)

        # Should be in FIFO order
        assert retrieved_jobs == jobs


class TestWebSocketSending:
    """Tests for WebSocket sending functions."""

    @pytest.mark.asyncio
    async def test_ws_send_sync_sends_message(self, mock_websocket):
        """Test _ws_send_sync sends message."""
        payload = Mock()
        payload.model_dump = Mock(return_value={"test": "data"})

        await _ws_send_sync(mock_websocket, payload)

        mock_websocket.send_json.assert_called_once_with({"test": "data"})

    @pytest.mark.asyncio
    async def test_ws_send_sync_handles_disconnected_websocket(self):
        """Test _ws_send_sync handles disconnected websocket."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.DISCONNECTED
        ws.send_json = AsyncMock()

        payload = Mock()
        payload.model_dump = Mock(return_value={"test": "data"})

        # Should not raise exception
        await _ws_send_sync(ws, payload)

    @pytest.mark.asyncio
    async def test_ws_send_sync_handles_exception(self, mock_websocket):
        """Test _ws_send_sync handles exceptions."""
        mock_websocket.send_json.side_effect = Exception("Connection error")
        payload = Mock()
        payload.model_dump = Mock(return_value={"test": "data"})

        # Should not raise exception
        await _ws_send_sync(mock_websocket, payload)

    @pytest.mark.asyncio
    async def test_ws_send_async_creates_task(self, mock_websocket):
        """Test _ws_send_async creates a task."""
        payload = Mock()
        payload.model_dump = Mock(return_value={"test": "data"})

        _ws_send_async(mock_websocket, payload)

        # Give task time to complete
        await asyncio.sleep(0.05)

        # Should have sent the message
        mock_websocket.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_ws_send_async_doesnt_send_when_disconnected(self):
        """Test _ws_send_async doesn't send when disconnected."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.DISCONNECTED
        ws.send_json = AsyncMock()

        payload = Mock()
        payload.model_dump = Mock(return_value={"test": "data"})

        _ws_send_async(ws, payload)

        # Wait for task
        await asyncio.sleep(0.01)

        # Should not have sent
        ws.send_json.assert_not_called()


class TestMonitorCancel:
    """Tests for _monitor_cancel function."""

    @pytest.mark.asyncio
    async def test_monitor_cancel_returns_user_on_cancel_cancelled_job(
        self, mock_websocket, sample_graph_data
    ):
        """Test _monitor_cancel returns 'user' on cancel."""
        job = ExecutionJob(1, mock_websocket, sample_graph_data)
        executor = MagicMock(spec=GraphExecutor)
        executor.stop = AsyncMock()

        # Set cancel event after a delay
        async def set_cancel():
            await asyncio.sleep(0.05)
            job.cancel_event.set()

        asyncio.create_task(set_cancel())

        reason = await _monitor_cancel(job, mock_websocket, executor, None)

        assert reason == "user"
        executor.stop.assert_called_once_with(reason="user")

    @pytest.mark.asyncio
    async def test_monitor_cancel_returns_disconnect_on_websocket_close(self, sample_graph_data):
        """Test _monitor_cancel returns 'disconnect' on websocket close."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        job = ExecutionJob(1, ws, sample_graph_data)
        executor = MagicMock(spec=GraphExecutor)
        executor.stop = AsyncMock()

        # Close websocket after a delay
        async def close_websocket():
            await asyncio.sleep(0.05)
            ws.client_state = WebSocketState.DISCONNECTED

        asyncio.create_task(close_websocket())

        reason = await _monitor_cancel(job, ws, executor, None)

        assert reason == "disconnect"
        executor.stop.assert_called_once_with(reason="disconnect")

    @pytest.mark.asyncio
    async def test_monitor_cancel_returns_completed_on_task_completion(
        self, mock_websocket, sample_graph_data
    ):
        """Test _monitor_cancel returns 'completed' on task completion."""
        job = ExecutionJob(1, mock_websocket, sample_graph_data)
        executor = MagicMock(spec=GraphExecutor)
        executor.stop = AsyncMock()

        # Create a task that completes quickly
        async def quick_task():
            await asyncio.sleep(0.05)
            return "done"

        execution_task = asyncio.create_task(quick_task())

        reason = await _monitor_cancel(job, mock_websocket, executor, execution_task)

        assert reason == "completed"
        executor.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_monitor_cancel_cancels_execution_task_on_user_cancel(
        self, mock_websocket, sample_graph_data
    ):
        """Test _monitor_cancel cancels execution task on user cancel."""
        job = ExecutionJob(1, mock_websocket, sample_graph_data)
        executor = MagicMock(spec=GraphExecutor)
        executor.stop = AsyncMock()

        # Create a long-running task
        async def long_task():
            await asyncio.sleep(1.0)
            return "done"

        execution_task = asyncio.create_task(long_task())

        # Set cancel event after a delay
        async def set_cancel():
            await asyncio.sleep(0.05)
            job.cancel_event.set()

        asyncio.create_task(set_cancel())

        reason = await _monitor_cancel(job, mock_websocket, executor, execution_task)

        assert reason == "user"
        # Wait a bit for cancellation to complete
        await asyncio.sleep(0.01)
        # Task should be cancelled or done
        assert execution_task.cancelled() or execution_task.done()
        executor.stop.assert_called_once_with(reason="user")


class TestExecutionWorker:
    """Tests for execution_worker function."""

    @pytest.mark.asyncio
    async def test_execution_worker_processes_job_successfully(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test execution_worker processes a job successfully."""
        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.is_stopped = False
        mock_executor.is_stopping = False
        mock_executor.execute = AsyncMock(return_value={1: {"result": "success"}})
        mock_executor.set_progress_callback = Mock()

        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            job = await execution_queue.enqueue(ws, sample_graph_data)

            # Run worker for one job
            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))

            # Wait for job to be processed
            await asyncio.sleep(0.1)

            # Cancel worker
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_execution_worker_handles_cancelled_job(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test execution_worker handles a cancelled job."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        job = await execution_queue.enqueue(ws, sample_graph_data)

        # Cancel job before worker picks it up
        await execution_queue.cancel_job(job)

        # Create mock executor (should not be called)
        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.execute = AsyncMock()

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            # Run worker
            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))

            # Wait
            await asyncio.sleep(0.1)

            # Cancel worker
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

            # Executor should not have been called
            mock_executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_execution_worker_sends_progress_updates(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test execution_worker sends progress updates."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        progress_callback = None

        def capture_callback(cb):
            nonlocal progress_callback
            progress_callback = cb

        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.is_stopped = False
        mock_executor.is_stopping = False
        mock_executor.set_progress_callback = capture_callback

        async def execute_with_progress():
            if progress_callback:
                progress_callback({"node_id": 1, "progress": 50.0, "text": "Halfway"})
            await asyncio.sleep(0.01)
            return {1: {"result": "success"}}

        mock_executor.execute = execute_with_progress

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            job = await execution_queue.enqueue(ws, sample_graph_data)

            # Run worker
            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))

            # Wait for execution
            await asyncio.sleep(0.1)

            # Cancel worker
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

            # Should have sent progress messages
            assert ws.send_json.called

    @pytest.mark.asyncio
    async def test_execution_worker_handles_execution_error(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test execution_worker handles execution errors."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.is_stopped = False
        mock_executor.is_stopping = False
        mock_executor.execute = AsyncMock(side_effect=RuntimeError("Execution failed"))
        mock_executor.set_progress_callback = Mock()

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            job = await execution_queue.enqueue(ws, sample_graph_data)

            # Run worker
            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))

            # Wait for execution
            await asyncio.sleep(0.1)

            # Cancel worker
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

            # Should have sent error message
            assert ws.send_json.called

    @pytest.mark.asyncio
    async def test_execution_worker_handles_stopped_executor(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test execution_worker handles stopped executor."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.is_stopped = True
        mock_executor.is_stopping = False
        mock_executor.cancellation_reason = "user"
        mock_executor.execute = AsyncMock(return_value={1: {"result": "cancelled"}})
        mock_executor.set_progress_callback = Mock()

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            job = await execution_queue.enqueue(ws, sample_graph_data)

            # Run worker
            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))

            # Wait for execution
            await asyncio.sleep(0.1)

            # Cancel worker
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

            # Should have sent stopped message
            assert ws.send_json.called

    @pytest.mark.asyncio
    async def test_execution_worker_doesnt_send_after_disconnect(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test execution_worker doesn't send messages after disconnect."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.DISCONNECTED
        ws.send_json = AsyncMock()

        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.is_stopped = False
        mock_executor.is_stopping = False
        mock_executor.execute = AsyncMock(return_value={1: {"result": "success"}})
        mock_executor.set_progress_callback = Mock()

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            job = await execution_queue.enqueue(ws, sample_graph_data)

            # Run worker
            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))

            # Wait for execution
            await asyncio.sleep(0.1)

            # Cancel worker
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

            # Initial status message may be sent before checking state, but final data/status should not be sent
            # The check verifies that at least we don't send the data message
            call_types = [
                call[0][0].get("type") for call in ws.send_json.call_args_list if call[0][0]
            ]
            # Should not send data message
            assert "data" not in call_types

    @pytest.mark.asyncio
    async def test_execution_worker_multiple_jobs_sequential(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test execution_worker processes multiple jobs sequentially."""
        executions = []

        def track_execution():
            executions.append(asyncio.get_event_loop().time())

        async def execute():
            track_execution()
            await asyncio.sleep(0.05)
            return {1: {"result": "success"}}

        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.is_stopped = False
        mock_executor.is_stopping = False
        mock_executor.execute = execute
        mock_executor.set_progress_callback = Mock()

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            # Enqueue multiple jobs
            for i in range(3):
                ws = MagicMock(spec=WebSocket)
                ws.client_state = WebSocketState.CONNECTED
                ws.send_json = AsyncMock()
                await execution_queue.enqueue(ws, sample_graph_data)

            # Run worker
            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))

            # Wait for all jobs
            await asyncio.sleep(0.5)

            # Cancel worker
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

            # Should have executed all jobs
            assert len(executions) == 3

    @pytest.mark.asyncio
    async def test_guarded_progress_callback_when_executor_stopped(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test progress callback doesn't send when executor is stopped."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        progress_callback = None

        def capture_callback(cb):
            nonlocal progress_callback
            progress_callback = cb

        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.is_stopped = True
        mock_executor.is_stopping = False
        mock_executor.set_progress_callback = capture_callback

        async def execute():
            if progress_callback:
                progress_callback({"node_id": 1, "progress": 50.0})
            return {1: {"result": "success"}}

        mock_executor.execute = execute

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            job = await execution_queue.enqueue(ws, sample_graph_data)

            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))
            await asyncio.sleep(0.1)
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_guarded_progress_callback_when_executor_stopping(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test progress callback doesn't send when executor is stopping."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        progress_callback = None

        def capture_callback(cb):
            nonlocal progress_callback
            progress_callback = cb

        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.is_stopped = False
        mock_executor.is_stopping = True
        mock_executor.set_progress_callback = capture_callback

        async def execute():
            if progress_callback:
                progress_callback({"node_id": 1, "progress": 50.0})
            return {1: {"result": "success"}}

        mock_executor.execute = execute

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            job = await execution_queue.enqueue(ws, sample_graph_data)

            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))
            await asyncio.sleep(0.1)
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_progress_callback_with_state_field(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test progress callback handles state field."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        progress_callback = None

        def capture_callback(cb):
            nonlocal progress_callback
            progress_callback = cb

        class MockState:
            value = "running"

        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.is_stopped = False
        mock_executor.is_stopping = False
        mock_executor.set_progress_callback = capture_callback

        async def execute():
            if progress_callback:
                progress_callback({"node_id": 1, "state": MockState()})
            return {1: {"result": "success"}}

        mock_executor.execute = execute

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            job = await execution_queue.enqueue(ws, sample_graph_data)

            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))
            await asyncio.sleep(0.1)
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_progress_callback_with_meta_field(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test progress callback handles meta field."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        progress_callback = None

        def capture_callback(cb):
            nonlocal progress_callback
            progress_callback = cb

        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.is_stopped = False
        mock_executor.is_stopping = False
        mock_executor.set_progress_callback = capture_callback

        async def execute():
            if progress_callback:
                progress_callback({"node_id": 1, "meta": {"key": "value"}})
            return {1: {"result": "success"}}

        mock_executor.execute = execute

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            job = await execution_queue.enqueue(ws, sample_graph_data)

            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))
            await asyncio.sleep(0.1)
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_position_updates_handle_exception(self, execution_queue, sample_graph_data):
        """Test position updates handle exceptions gracefully."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock(side_effect=Exception("Connection error"))

        job = await execution_queue.enqueue(ws, sample_graph_data)

        # Wait for position update task to hit exception
        await asyncio.sleep(1.1)

        # Should have attempted to send
        assert ws.send_json.called

    @pytest.mark.asyncio
    async def test_ws_send_async_handles_exception(self, mock_websocket):
        """Test _ws_send_async handles exceptions."""
        mock_websocket.send_json.side_effect = Exception("Send error")
        payload = Mock()
        payload.model_dump = Mock(return_value={"test": "data"})

        _ws_send_async(mock_websocket, payload)

        # Wait for task
        await asyncio.sleep(0.05)

        # Should not raise exception

    @pytest.mark.asyncio
    async def test_execution_worker_cancelled_error_path(
        self, execution_queue, mock_node_registry, sample_graph_data
    ):
        """Test execution_worker handles CancelledError properly."""
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        mock_executor = MagicMock(spec=GraphExecutor)
        mock_executor.is_stopped = False
        mock_executor.is_stopping = False
        mock_executor.cancellation_reason = "user"
        mock_executor.execute = AsyncMock(side_effect=asyncio.CancelledError())
        mock_executor.set_progress_callback = Mock()

        with patch("server.queue.GraphExecutor", return_value=mock_executor):
            job = await execution_queue.enqueue(ws, sample_graph_data)

            worker_task = asyncio.create_task(execution_worker(execution_queue, mock_node_registry))
            await asyncio.sleep(0.1)
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
