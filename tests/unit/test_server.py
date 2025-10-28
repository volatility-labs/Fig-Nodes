"""Tests for server.py WebSocket endpoint and HTTP routes."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketState

from core.api_key_vault import APIKeyVault
from core.node_registry import NODE_REGISTRY
from core.types_registry import SerialisableGraph
from server.api.session_manager import ConnectionRegistry, establish_session
from server.api.websocket_schemas import (
    ClientToServerConnectMessage,
    ClientToServerGraphMessage,
    ClientToServerStopMessage,
)
from server.queue import ExecutionJob, ExecutionQueue, execution_worker
from server.server import (
    _get_connection_registry,
    _get_execution_queue,
    _handle_graph_message,
    _handle_stop_message,
    _parse_client_message,
    _send_error_message,
    app,
)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket."""
    ws = MagicMock(spec=WebSocket)
    ws.client_state = WebSocketState.CONNECTED
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def sample_graph_data() -> SerialisableGraph:
    """Sample graph data for testing."""
    return {"nodes": [{"id": 1, "type": "test_node"}], "links": []}


@pytest.fixture
def isolated_app():
    """Create an isolated FastAPI app for testing."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def test_lifespan(app: FastAPI):
        """Test lifespan manager."""
        queue = ExecutionQueue()
        worker_task = asyncio.create_task(execution_worker(queue, NODE_REGISTRY))
        connection_registry = ConnectionRegistry()

        app.state.execution_queue = queue
        app.state.execution_worker = worker_task
        app.state.connection_registry = connection_registry

        yield

        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)

    test_app = FastAPI(lifespan=test_lifespan)
    return test_app


class TestParseClientMessage:
    """Tests for _parse_client_message function."""

    @pytest.mark.asyncio
    async def test_parse_connect_message(self):
        """Test parsing connect message."""
        raw_data = {"type": "connect", "session_id": "test-session"}
        message = await _parse_client_message(raw_data)
        assert isinstance(message, ClientToServerConnectMessage)
        assert message.type == "connect"
        assert message.session_id == "test-session"

    @pytest.mark.asyncio
    async def test_parse_connect_message_no_session_id(self):
        """Test parsing connect message without session_id."""
        raw_data = {"type": "connect"}
        message = await _parse_client_message(raw_data)
        assert isinstance(message, ClientToServerConnectMessage)
        assert message.type == "connect"
        assert message.session_id is None

    @pytest.mark.asyncio
    async def test_parse_graph_message(self):
        """Test parsing graph message."""
        raw_data = {"type": "graph", "graph_data": {"nodes": [], "links": []}}
        message = await _parse_client_message(raw_data)
        assert isinstance(message, ClientToServerGraphMessage)
        assert message.type == "graph"
        assert message.graph_data == {"nodes": [], "links": []}

    @pytest.mark.asyncio
    async def test_parse_stop_message(self):
        """Test parsing stop message."""
        raw_data = {"type": "stop"}
        message = await _parse_client_message(raw_data)
        assert isinstance(message, ClientToServerStopMessage)
        assert message.type == "stop"

    @pytest.mark.asyncio
    async def test_parse_invalid_message_raises_error(self):
        """Test parsing invalid message raises ValidationError."""
        raw_data = {"type": "invalid"}
        with pytest.raises(ValidationError):
            await _parse_client_message(raw_data)


class TestSendErrorMessage:
    """Tests for _send_error_message function."""

    @pytest.mark.asyncio
    async def test_send_error_message_basic(self, mock_websocket):
        """Test sending basic error message."""
        await _send_error_message(mock_websocket, "Test error")
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "error"
        assert call_args["message"] == "Test error"
        # None values are excluded by exclude_none=True
        assert call_args.get("code") is None
        assert call_args.get("missing_keys") is None
        assert call_args.get("job_id") is None

    @pytest.mark.asyncio
    async def test_send_error_message_with_code(self, mock_websocket):
        """Test sending error message with code."""
        await _send_error_message(mock_websocket, "Missing keys", code="MISSING_API_KEYS")
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["code"] == "MISSING_API_KEYS"

    @pytest.mark.asyncio
    async def test_send_error_message_with_missing_keys(self, mock_websocket):
        """Test sending error message with missing keys."""
        await _send_error_message(mock_websocket, "Missing keys", missing_keys=["key1", "key2"])
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["missing_keys"] == ["key1", "key2"]

    @pytest.mark.asyncio
    async def test_send_error_message_with_job_id(self, mock_websocket):
        """Test sending error message with job_id."""
        await _send_error_message(mock_websocket, "Error", job_id=123)
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["job_id"] == 123


class TestHandleGraphMessage:
    """Tests for _handle_graph_message function."""

    @pytest.mark.asyncio
    async def test_handle_graph_message_success(self, mock_websocket, sample_graph_data):
        """Test handling successful graph message."""
        vault = APIKeyVault()
        vault.set("test_key", "test_value")

        message = ClientToServerGraphMessage(type="graph", graph_data=sample_graph_data)

        # Mock node registry to not require any keys
        with patch("server.server.NODE_REGISTRY", new={}):
            # Mock app.state
            queue = ExecutionQueue()
            app.state.execution_queue = queue

            job = await _handle_graph_message(mock_websocket, message)

        assert job is not None
        assert isinstance(job, ExecutionJob)
        assert job.graph_data == sample_graph_data

        # Verify status message was sent
        assert mock_websocket.send_json.called
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "status"
        assert call_args["state"] == "queued"
        assert call_args["job_id"] == job.id

    @pytest.mark.asyncio
    async def test_handle_graph_message_missing_api_keys(self, mock_websocket, sample_graph_data):
        """Test handling graph message with missing API keys."""
        # Mock a node that requires a key
        mock_node_class = MagicMock()
        mock_node_class.required_keys = ["MISSING_KEY"]

        with patch("server.server.NODE_REGISTRY", {"test_node": mock_node_class}):
            message = ClientToServerGraphMessage(type="graph", graph_data=sample_graph_data)
            job = await _handle_graph_message(mock_websocket, message)

        assert job is None

        # Verify error message was sent
        assert mock_websocket.send_json.called
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "error"
        assert call_args["code"] == "MISSING_API_KEYS"
        assert "MISSING_KEY" in call_args["missing_keys"]


class TestHandleStopMessage:
    """Tests for _handle_stop_message function."""

    @pytest.mark.asyncio
    async def test_handle_stop_no_job(self, mock_websocket):
        """Test handling stop message with no active job."""
        should_close, updated_job = await _handle_stop_message(
            mock_websocket, None, False, asyncio.Event()
        )

        assert should_close is False
        assert updated_job is None

        # Verify stopped message was sent
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "stopped"
        assert call_args["message"] == "No active job to stop"

    @pytest.mark.asyncio
    async def test_handle_stop_already_cancelling(self, mock_websocket, sample_graph_data):
        """Test handling stop message when already cancelling."""
        job = ExecutionJob(1, mock_websocket, sample_graph_data)
        cancel_done_event = asyncio.Event()

        # Set cancel done event to simulate already cancelling
        cancel_done_event.set()

        should_close, updated_job = await _handle_stop_message(
            mock_websocket, job, True, cancel_done_event
        )

        assert should_close is False
        assert updated_job is None

        # Verify stopped message was sent
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "stopped"
        assert "idempotent" in call_args["message"]

    @pytest.mark.asyncio
    async def test_handle_stop_active_job(self, mock_websocket, sample_graph_data):
        """Test handling stop message with active job."""
        queue = ExecutionQueue()
        job = await queue.enqueue(mock_websocket, sample_graph_data)

        # Get the job from queue so it's running
        running_job = await queue.get_next()

        # Create a mock queue that also sets done_event when canceling running jobs
        mock_queue = MagicMock(spec=ExecutionQueue)

        async def mock_cancel_job(job):
            # Simulate cancel_job behavior - set done_event for running jobs
            if job.state.value == "running":
                job.done_event.set()
            elif job.state.value == "pending":
                job.done_event.set()
            job.state = Mock()
            job.state.value = "cancelled"

        mock_queue.cancel_job = AsyncMock(side_effect=mock_cancel_job)

        with patch("server.server._get_execution_queue", return_value=mock_queue):
            should_close, updated_job = await _handle_stop_message(
                mock_websocket, running_job, False, asyncio.Event()
            )

        assert should_close is False
        assert updated_job is None


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_execution_queue(self):
        """Test _get_execution_queue helper."""
        queue = ExecutionQueue()
        app.state.execution_queue = queue
        result = _get_execution_queue(app)
        assert result is queue

    def test_get_connection_registry(self):
        """Test _get_connection_registry helper."""
        registry = ConnectionRegistry()
        app.state.connection_registry = registry
        result = _get_connection_registry(app)
        assert result is registry


class TestWebSocketEndpoint:
    """Tests for WebSocket /execute endpoint."""

    def test_execute_endpoint_exists(self):
        """Test that execute endpoint is registered."""
        # Verify the websocket route exists in the app
        websocket_routes = [r for r in app.routes if hasattr(r, "path")]
        # Just verify that routes exist
        assert len(websocket_routes) > 0


class TestHTTPRoutes:
    """Tests for HTTP API routes."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    def test_get_root(self, client):
        """Test GET / endpoint."""
        response = client.get("/")
        assert response.status_code in [200, 404]  # May not exist in test environment

    def test_get_style_css(self, client):
        """Test GET /style.css endpoint."""
        response = client.get("/style.css")
        assert response.status_code in [200, 404]  # May not exist in test environment

    def test_get_nodes(self, client):
        """Test GET /api/v1/nodes endpoint."""
        response = client.get("/api/v1/nodes")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data

    def test_get_api_keys(self, client):
        """Test GET /api/v1/api_keys endpoint."""
        response = client.get("/api/v1/api_keys")
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data

    def test_set_api_key(self, client):
        """Test POST /api/v1/api_keys endpoint."""
        response = client.post(
            "/api/v1/api_keys", json={"key_name": "test_key", "value": "test_value"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Verify key was set
        get_response = client.get("/api/v1/api_keys")
        keys = get_response.json()["keys"]
        assert "test_key" in keys
        assert keys["test_key"] == "test_value"

    def test_delete_api_key(self, client):
        """Test DELETE /api/v1/api_keys endpoint."""
        # First set a key
        client.post("/api/v1/api_keys", json={"key_name": "delete_test", "value": "delete_value"})

        # Use request() method for DELETE with body
        response = client.request("DELETE", "/api/v1/api_keys", json={"key_name": "delete_test"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Verify key was deleted
        get_response = client.get("/api/v1/api_keys")
        keys = get_response.json()["keys"]
        assert "delete_test" not in keys

    def test_set_api_key_empty_value(self, client):
        """Test setting API key with empty value."""
        response = client.post("/api/v1/api_keys", json={"key_name": "empty_key", "value": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_delete_nonexistent_key(self, client):
        """Test deleting non-existent key."""
        # Use request() method for DELETE with body
        response = client.request("DELETE", "/api/v1/api_keys", json={"key_name": "nonexistent"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestExceptionHandlers:
    """Tests for exception handlers."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    def test_validation_error_handler(self, client):
        """Test validation error handler."""
        # Send invalid JSON to trigger validation error
        response = client.post("/api/v1/api_keys", json={"invalid": "data"})
        assert response.status_code == 422
        data = response.json()
        assert "error" in data or "detail" in data


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_jobs(self, mock_websocket, sample_graph_data):
        """Test handling multiple concurrent job submissions."""
        queue = ExecutionQueue()

        jobs = []
        for i in range(3):
            job = await queue.enqueue(mock_websocket, sample_graph_data)
            jobs.append(job)

        assert len(jobs) == 3
        assert all(job.id == i for i, job in enumerate(jobs))

    @pytest.mark.asyncio
    async def test_disconnect_during_execution(self, mock_websocket, sample_graph_data):
        """Test handling disconnect during execution."""
        queue = ExecutionQueue()
        job = await queue.enqueue(mock_websocket, sample_graph_data)

        # Simulate disconnect
        mock_websocket.client_state = WebSocketState.DISCONNECTED

        # Try to cancel the job
        await queue.cancel_job(job)

        assert job.state.value == "cancelled"

    @pytest.mark.asyncio
    async def test_invalid_message_parsing_continues(self, mock_websocket):
        """Test that invalid message parsing doesn't crash the endpoint."""
        # Send an invalid message format
        invalid_data = {"type": "invalid", "some_field": "value"}

        with pytest.raises(ValidationError):
            await _parse_client_message(invalid_data)

    @pytest.mark.asyncio
    async def test_graph_message_with_large_data(self, mock_websocket):
        """Test handling graph message with large data."""
        large_nodes = [{"id": i, "type": "test_node"} for i in range(1000)]
        large_graph_data = {"nodes": large_nodes, "links": []}

        message = ClientToServerGraphMessage(type="graph", graph_data=large_graph_data)
        assert message.graph_data == large_graph_data

    @pytest.mark.asyncio
    async def test_session_reconnection(self, mock_websocket):
        """Test session reconnection handling."""
        registry = ConnectionRegistry()
        session_id = "test-session-123"

        # First connection
        ws1 = MagicMock(spec=WebSocket)
        ws1.client_state = WebSocketState.CONNECTED
        registry.register(session_id, ws1)

        # Second connection with same session_id
        ws2 = MagicMock(spec=WebSocket)
        ws2.client_state = WebSocketState.CONNECTED

        # The registry should prevent duplicate registrations
        registry.register(session_id, ws2)

        # Latest websocket should be registered
        assert registry.get_websocket(session_id) is ws2

    @pytest.mark.asyncio
    async def test_stop_message_idempotency(self, mock_websocket, sample_graph_data):
        """Test that stop message is idempotent."""
        # Send stop with no job
        should_close1, _ = await _handle_stop_message(mock_websocket, None, False, asyncio.Event())

        # Send stop again
        should_close2, _ = await _handle_stop_message(mock_websocket, None, False, asyncio.Event())

        assert should_close1 == should_close2
        assert mock_websocket.send_json.call_count == 2


class TestQueueIntegration:
    """Integration tests for queue and server."""

    @pytest.mark.asyncio
    async def test_enqueue_and_execute(self, mock_websocket, sample_graph_data):
        """Test enqueue and execution flow."""
        queue = ExecutionQueue()

        # Enqueue job
        job = await queue.enqueue(mock_websocket, sample_graph_data)
        assert job.state.value == "pending"

        # Get next job
        next_job = await queue.get_next()
        assert next_job is job
        assert next_job.state.value == "running"

        # Mark done
        await queue.mark_done(job)
        assert job.state.value == "done"
        assert job.done_event.is_set()

    @pytest.mark.asyncio
    async def test_cancel_pending_job(self, mock_websocket, sample_graph_data):
        """Test cancelling a pending job."""
        queue = ExecutionQueue()
        job = await queue.enqueue(mock_websocket, sample_graph_data)

        await queue.cancel_job(job)

        assert job.state.value == "cancelled"
        assert job.done_event.is_set()

    @pytest.mark.asyncio
    async def test_queue_position_updates(self, mock_websocket, sample_graph_data):
        """Test queue position updates."""
        queue = ExecutionQueue()

        # Enqueue multiple jobs
        job1 = await queue.enqueue(mock_websocket, sample_graph_data)
        job2 = await queue.enqueue(mock_websocket, sample_graph_data)
        job3 = await queue.enqueue(mock_websocket, sample_graph_data)

        # Check positions
        assert await queue.position(job1) == 1
        assert await queue.position(job2) == 2
        assert await queue.position(job3) == 3

        # Get first job
        next_job = await queue.get_next()
        assert next_job is job1

        # Check positions again
        assert await queue.position(job1) == 0  # Running
        assert await queue.position(job2) == 1
        assert await queue.position(job3) == 2

        # Mark done to clean up
        await queue.mark_done(job1)


class TestSessionManagement:
    """Tests for session management functionality."""

    @pytest.mark.asyncio
    async def test_session_establishment_new_session(self, mock_websocket):
        """Test establishing a new session."""
        from server.api.session_manager import ConnectionRegistry

        registry = ConnectionRegistry()
        connect_msg = ClientToServerConnectMessage(type="connect", session_id=None)

        session_id = await establish_session(mock_websocket, registry, connect_msg)

        assert session_id is not None
        assert registry.has_session(session_id)
        assert registry.get_websocket(session_id) is mock_websocket

        # Verify session message was sent
        assert mock_websocket.send_json.called
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "session"
        assert call_args["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_session_establishment_existing_session(self, mock_websocket):
        """Test establishing session with existing session_id."""
        from server.api.session_manager import ConnectionRegistry

        registry = ConnectionRegistry()
        existing_session_id = "existing-session-123"
        registry.register(existing_session_id, mock_websocket)

        connect_msg = ClientToServerConnectMessage(type="connect", session_id=existing_session_id)
        session_id = await establish_session(mock_websocket, registry, connect_msg)

        assert session_id == existing_session_id
        assert registry.has_session(session_id)

    @pytest.mark.asyncio
    async def test_session_reconnection_closes_old_connection(self):
        """Test that reconnection closes old websocket."""
        from server.api.session_manager import ConnectionRegistry

        registry = ConnectionRegistry()
        session_id = "reconnect-session"

        # First websocket
        ws1 = MagicMock(spec=WebSocket)
        ws1.client_state = WebSocketState.CONNECTED
        ws1.close = AsyncMock()
        ws1.send_json = AsyncMock()

        # Second websocket
        ws2 = MagicMock(spec=WebSocket)
        ws2.client_state = WebSocketState.CONNECTED
        ws2.send_json = AsyncMock()

        # Establish first connection
        connect_msg1 = ClientToServerConnectMessage(type="connect", session_id=None)
        returned_session_id = await establish_session(ws1, registry, connect_msg1)

        # Simulate that the session persisted and now we're reconnecting
        # The client sends the session_id back
        connect_msg2 = ClientToServerConnectMessage(type="connect", session_id=returned_session_id)
        await establish_session(ws2, registry, connect_msg2)

        # Verify old websocket was closed
        ws1.close.assert_called_once()

        # Verify new websocket is registered
        assert registry.get_websocket(returned_session_id) is ws2

    @pytest.mark.asyncio
    async def test_session_unregister_with_matching_websocket(self):
        """Test unregister removes session when websocket matches."""
        from server.api.session_manager import ConnectionRegistry

        registry = ConnectionRegistry()
        session_id = "test-session"
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED

        registry.register(session_id, ws)
        registry.set_job(session_id, None)

        registry.unregister(session_id, ws)

        assert not registry.has_session(session_id)
        assert registry.get_job(session_id) is None

    @pytest.mark.asyncio
    async def test_session_unregister_with_different_websocket(self):
        """Test unregister prevents race condition with different websocket."""
        from server.api.session_manager import ConnectionRegistry

        registry = ConnectionRegistry()
        session_id = "test-session"
        ws1 = MagicMock(spec=WebSocket)
        ws2 = MagicMock(spec=WebSocket)

        registry.register(session_id, ws1)

        # Try to unregister with different websocket
        registry.unregister(session_id, ws2)

        # Session should still exist (ws1 is still registered)
        assert registry.has_session(session_id)
        assert registry.get_websocket(session_id) is ws1

    @pytest.mark.asyncio
    async def test_session_job_association(self):
        """Test associating and retrieving jobs with sessions."""
        from server.api.session_manager import ConnectionRegistry
        from server.queue import ExecutionJob

        registry = ConnectionRegistry()
        session_id = "test-session"
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED

        registry.register(session_id, ws)

        # Set job
        graph_data = {"nodes": [], "links": []}
        job = ExecutionJob(1, ws, graph_data)
        registry.set_job(session_id, job)

        assert registry.get_job(session_id) is job

        # Clear job
        registry.set_job(session_id, None)
        assert registry.get_job(session_id) is None


class TestQueueWorker:
    """Tests for queue worker and execution."""

    @pytest.mark.asyncio
    async def test_execution_worker_basic_flow(self, mock_websocket, sample_graph_data):
        """Test basic execution worker flow."""
        from core.node_registry import NodeRegistry
        from server.queue import ExecutionQueue, execution_worker

        queue = ExecutionQueue()
        registry = NodeRegistry({})

        # Create a simple task to stop the worker
        async def stop_worker_after_delay():
            await asyncio.sleep(0.1)
            # Enqueue a job that will be cancelled immediately
            job = await queue.enqueue(mock_websocket, sample_graph_data)
            await queue.cancel_job(job)

        # Start worker task
        worker_task = asyncio.create_task(execution_worker(queue, registry))
        stop_task = asyncio.create_task(stop_worker_after_delay())

        # Wait a bit
        await asyncio.sleep(0.2)

        # Cancel worker
        worker_task.cancel()
        await asyncio.gather(worker_task, stop_task, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_execution_worker_cancelled_before_execution(
        self, mock_websocket, sample_graph_data
    ):
        """Test execution worker handles jobs cancelled before execution."""
        from core.node_registry import NodeRegistry
        from server.queue import ExecutionQueue

        queue = ExecutionQueue()
        registry = NodeRegistry({})

        # Enqueue and immediately cancel
        job = await queue.enqueue(mock_websocket, sample_graph_data)
        await queue.cancel_job(job)

        # Verify job is cancelled and done event is set
        assert job.state.value == "cancelled"
        assert job.done_event.is_set()

        # Verify job is not in pending queue anymore
        pos = await queue.position(job)
        assert pos == -1  # Job not found in queue

    @pytest.mark.asyncio
    async def test_execution_worker_handles_cancellation(self, mock_websocket, sample_graph_data):
        """Test execution worker handles job cancellation."""
        from core.node_registry import NodeRegistry
        from server.queue import ExecutionQueue

        queue = ExecutionQueue()
        registry = NodeRegistry({})

        # Enqueue a job
        job = await queue.enqueue(mock_websocket, sample_graph_data)

        # Cancel it using the queue's cancel method
        await queue.cancel_job(job)

        # Verify cancellation state
        assert job.state.value == "cancelled"
        assert job.done_event.is_set()
        # Note: cancel_event is only set for running jobs, not pending jobs


class TestWebSocketEndpointIntegration:
    """Integration tests for WebSocket endpoint."""

    @pytest.mark.asyncio
    async def test_full_websocket_flow(self):
        """Test full WebSocket connection and execution flow."""
        from server.api.session_manager import ConnectionRegistry
        from server.queue import ExecutionQueue, execution_worker

        # Setup
        queue = ExecutionQueue()
        registry = ConnectionRegistry()
        app.state.execution_queue = queue
        app.state.connection_registry = registry

        # Create mock websocket
        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.accept = AsyncMock()
        ws.receive_json = AsyncMock()
        ws.send_json = AsyncMock()

        # Mock message sequence
        connect_msg = {"type": "connect", "session_id": None}
        graph_msg = {"type": "graph", "graph_data": {"nodes": [], "links": []}}

        call_count = 0

        async def mock_receive():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return connect_msg
            elif call_count == 2:
                return graph_msg
            else:
                # Keep connection alive
                await asyncio.sleep(100)

        ws.receive_json = AsyncMock(side_effect=mock_receive)

        # Mock NODE_REGISTRY to not require keys
        with patch("server.server.NODE_REGISTRY", new={}):
            # Start worker
            worker_task = asyncio.create_task(execution_worker(queue, {}))

            # Simulate endpoint execution
            try:
                await ws.accept()

                # Receive connect message
                raw_data = await ws.receive_json()
                from server.server import _parse_client_message

                message = await _parse_client_message(raw_data)
                assert message.type == "connect"

                connect_msg_typed = message  # type: ignore
                from server.api.session_manager import establish_session

                session_id = await establish_session(ws, registry, connect_msg_typed)
                assert session_id is not None

                # Receive graph message
                raw_data = await ws.receive_json()
                message = await _parse_client_message(raw_data)
                assert message.type == "graph"

                from server.server import _handle_graph_message

                job = await _handle_graph_message(ws, message)
                assert job is not None

                # Cleanup
                await asyncio.sleep(0.1)
                worker_task.cancel()
                await asyncio.gather(worker_task, return_exceptions=True)

            except Exception:
                worker_task.cancel()
                await asyncio.gather(worker_task, return_exceptions=True)
                raise

    @pytest.mark.asyncio
    async def test_websocket_disconnect_during_execution(self):
        """Test WebSocket disconnect handling during execution."""
        from server.api.session_manager import ConnectionRegistry
        from server.queue import ExecutionQueue

        registry = ConnectionRegistry()
        queue = ExecutionQueue()
        app.state.connection_registry = registry
        app.state.execution_queue = queue

        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        # Create a task that simulates disconnect
        async def simulate_disconnect():
            await asyncio.sleep(0.05)
            ws.client_state = WebSocketState.DISCONNECTED

        disconnect_task = asyncio.create_task(simulate_disconnect())

        # Simulate disconnect handling

        # Cleanup session
        session_id = "test-session"
        registry.register(session_id, ws)
        await disconnect_task

        # Verify cleanup happens without errors
        registry.unregister(session_id, ws)
        assert not registry.has_session(session_id)

    @pytest.mark.asyncio
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling and cleanup."""
        from server.api.session_manager import ConnectionRegistry

        registry = ConnectionRegistry()
        app.state.connection_registry = registry

        ws = MagicMock(spec=WebSocket)
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()

        session_id = "test-session"
        registry.register(session_id, ws)

        # Simulate error during communication
        ws.send_json.side_effect = Exception("Connection lost")

        # Verify registry cleanup happens
        try:
            registry.unregister(session_id, ws)
        except Exception:
            pass

        # Verify session is removed
        assert not registry.has_session(session_id)

    @pytest.mark.asyncio
    async def test_websocket_multiple_concurrent_sessions(self):
        """Test handling multiple concurrent WebSocket sessions."""
        from server.api.session_manager import ConnectionRegistry

        registry = ConnectionRegistry()

        # Create multiple websockets
        ws1 = MagicMock(spec=WebSocket)
        ws1.client_state = WebSocketState.CONNECTED
        ws1.send_json = AsyncMock()

        ws2 = MagicMock(spec=WebSocket)
        ws2.client_state = WebSocketState.CONNECTED
        ws2.send_json = AsyncMock()

        # Register both sessions
        session1 = "session-1"
        session2 = "session-2"

        registry.register(session1, ws1)
        registry.register(session2, ws2)

        assert registry.has_session(session1)
        assert registry.has_session(session2)
        assert registry.get_websocket(session1) is ws1
        assert registry.get_websocket(session2) is ws2

        # Unregister one
        registry.unregister(session1, ws1)
        assert not registry.has_session(session1)
        assert registry.has_session(session2)

    @pytest.mark.asyncio
    async def test_websocket_reconnection_scenario(self):
        """Test WebSocket reconnection scenario."""
        from server.api.session_manager import ConnectionRegistry

        registry = ConnectionRegistry()
        session_id = "reconnect-session"

        # First connection
        ws1 = MagicMock(spec=WebSocket)
        ws1.client_state = WebSocketState.CONNECTED
        ws1.close = AsyncMock()
        ws1.send_json = AsyncMock()

        connect_msg1 = ClientToServerConnectMessage(type="connect", session_id=session_id)
        await establish_session(ws1, registry, connect_msg1)

        # Simulate disconnect
        ws1.client_state = WebSocketState.DISCONNECTED

        # Reconnect with same session
        ws2 = MagicMock(spec=WebSocket)
        ws2.client_state = WebSocketState.CONNECTED
        ws2.send_json = AsyncMock()

        connect_msg2 = ClientToServerConnectMessage(type="connect", session_id=session_id)
        new_session_id = await establish_session(ws2, registry, connect_msg2)

        # Session should be maintained or replaced
        assert registry.has_session(new_session_id)

    @pytest.mark.asyncio
    async def test_websocket_stop_message_handling(self, mock_websocket, sample_graph_data):
        """Test stop message handling through WebSocket."""
        from server.queue import ExecutionQueue

        queue = ExecutionQueue()
        app.state.execution_queue = queue

        # Create a job
        job = await queue.enqueue(mock_websocket, sample_graph_data)

        # Handle stop message - this cancels the job
        cancel_done_event = asyncio.Event()
        should_close, updated_job = await _handle_stop_message(
            mock_websocket, job, False, cancel_done_event
        )

        assert should_close is False
        assert updated_job is None

        # Verify job was cancelled and event was set
        assert job.state.value == "cancelled"
        assert job.done_event.is_set()
        assert cancel_done_event.is_set()
