"""Integration tests for WebSocket /execute endpoint."""

import asyncio
import json
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.server import app


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_graph_data():
    """Sample graph data for testing."""
    return {"nodes": [{"id": 1, "type": "test_node"}], "links": []}


class TestWebSocketConnect:
    """Tests for WebSocket connection establishment."""

    def test_connect_with_new_session(self, test_client, sample_graph_data):
        """Test connecting with a new session."""
        # Note: Context manager will close connection automatically
        with test_client.websocket_connect("/execute") as websocket:
            # Send connect message
            websocket.send_json({"type": "connect"})
            
            # Receive session message
            message = websocket.receive_json()
            assert message["type"] == "session"
            assert "session_id" in message
            
            # Don't need to close - context manager handles it

    def test_connect_with_existing_session(self, test_client, sample_graph_data):
        """Test connecting with an existing session."""
        session_id = None
        
        # First connection
        with test_client.websocket_connect("/execute") as websocket1:
            websocket1.send_json({"type": "connect"})
            response1 = websocket1.receive_json()
            session_id = response1["session_id"]
            websocket1.close()
        
        # Second connection with same session_id
        with test_client.websocket_connect("/execute") as websocket2:
            websocket2.send_json({"type": "connect", "session_id": session_id})
            response2 = websocket2.receive_json()
            assert response2["type"] == "session"
            assert response2["session_id"] == session_id
            websocket2.close()

    def test_first_message_must_be_connect(self, test_client, sample_graph_data):
        """Test that first message must be 'connect'."""
        with test_client.websocket_connect("/execute") as websocket:
            # Try to send graph message first
            websocket.send_json({"type": "graph", "graph_data": sample_graph_data})
            
            # Should receive error
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert "connect" in message["message"].lower()
            # Context manager closes automatically

    def test_invalid_connect_message(self, test_client):
        """Test invalid connect message handling."""
        with test_client.websocket_connect("/execute") as websocket:
            # Send invalid connect message (validation should pass but field is ignored)
            websocket.send_json({"type": "connect", "invalid_field": "value"})
            
            # Should receive session message (field is ignored)
            message = websocket.receive_json()
            assert message["type"] == "session"
            # Context manager closes automatically


class TestWebSocketGraphExecution:
    """Tests for graph execution via WebSocket."""

    def test_execute_graph_message(self, test_client, sample_graph_data):
        """Test executing a graph via WebSocket."""
        with test_client.websocket_connect("/execute") as websocket:
            # Connect
            websocket.send_json({"type": "connect"})
            websocket.receive_json()  # Session message
            
            # Mock NODE_REGISTRY to not require keys
            with pytest.mock.patch("server.server.NODE_REGISTRY", new={}):
                # Send graph message
                websocket.send_json({"type": "graph", "graph_data": sample_graph_data})
                
                # Should receive status message
                message = websocket.receive_json()
                assert message["type"] == "status"
                assert message["state"] == "queued"
                assert "job_id" in message
            
            # Context manager closes automatically

    def test_execute_graph_missing_api_keys(self, test_client, sample_graph_data):
        """Test executing graph with missing API keys."""
        # Mock a node that requires keys
        mock_node_class = pytest.mock.MagicMock()
        mock_node_class.required_keys = ["MISSING_KEY"]
        
        with test_client.websocket_connect("/execute") as websocket:
            # Connect
            websocket.send_json({"type": "connect"})
            websocket.receive_json()  # Session message
            
            with pytest.mock.patch("server.server.NODE_REGISTRY", {"test_node": mock_node_class}):
                # Send graph message
                websocket.send_json({"type": "graph", "graph_data": sample_graph_data})
                
                # Should receive error about missing keys
                message = websocket.receive_json()
                assert message["type"] == "error"
                assert message["code"] == "MISSING_API_KEYS"
                assert "MISSING_KEY" in message["missing_keys"]
            
            # Context manager closes automatically

    def test_multiple_graph_messages(self, test_client, sample_graph_data):
        """Test sending multiple graph messages."""
        with test_client.websocket_connect("/execute") as websocket:
            # Connect
            websocket.send_json({"type": "connect"})
            websocket.receive_json()  # Session message
            
            with pytest.mock.patch("server.server.NODE_REGISTRY", new={}):
                # Send first graph
                websocket.send_json({"type": "graph", "graph_data": sample_graph_data})
                response1 = websocket.receive_json()
                assert response1["type"] == "status"
                
                # Send second graph
                websocket.send_json({"type": "graph", "graph_data": sample_graph_data})
                response2 = websocket.receive_json()
                assert response2["type"] == "status"
                assert response2["job_id"] != response1["job_id"]
            
            # Context manager closes automatically


class TestWebSocketStopExecution:
    """Tests for stopping execution via WebSocket."""

    def test_stop_no_active_job(self, test_client):
        """Test stopping when no active job."""
        with test_client.websocket_connect("/execute") as websocket:
            # Connect
            websocket.send_json({"type": "connect"})
            websocket.receive_json()  # Session message
            
            # Send stop message
            websocket.send_json({"type": "stop"})
            
            # Should receive stopped message
            message = websocket.receive_json()
            assert message["type"] == "stopped"
            assert "No active job" in message["message"]
            
            # Context manager closes automatically

    def test_stop_active_job(self, test_client, sample_graph_data):
        """Test stopping an active job."""
        with test_client.websocket_connect("/execute") as websocket:
            # Connect
            websocket.send_json({"type": "connect"})
            websocket.receive_json()  # Session message
            
            with pytest.mock.patch("server.server.NODE_REGISTRY", new={}):
                # Start a job
                websocket.send_json({"type": "graph", "graph_data": sample_graph_data})
                response = websocket.receive_json()
                assert response["type"] == "status"
                
                # Stop the job
                websocket.send_json({"type": "stop"})
                
                # Should receive stopped message (might take a moment)
                # Note: In real execution, this would wait for job completion
                # For this test, we're just verifying the stop message is accepted
            
            # Context manager closes automatically


class TestWebSocketErrorHandling:
    """Tests for WebSocket error handling."""

    def test_invalid_message_format(self, test_client):
        """Test handling invalid message format."""
        with test_client.websocket_connect("/execute") as websocket:
            # Connect
            websocket.send_json({"type": "connect"})
            websocket.receive_json()  # Session message
            
            # Send invalid message
            websocket.send_json({"type": "invalid_type"})
            
            # Should receive error
            message = websocket.receive_json()
            assert message["type"] == "error"
            
            # Context manager closes automatically

    def test_malformed_json(self, test_client):
        """Test handling malformed JSON."""
        with test_client.websocket_connect("/execute") as websocket:
            # Connect
            websocket.send_json({"type": "connect"})
            websocket.receive_json()  # Session message
            
            # Send malformed data
            websocket.send_bytes(b"invalid json")
            
            # Should close connection or handle gracefully
            try:
                message = websocket.receive_json()
                assert message["type"] == "error"
            except WebSocketDisconnect:
                # Expected behavior - connection closed
                pass
            
            # If not disconnected, close manually
            try:
                # Context manager closes automatically
            except:
                pass

    def test_disconnect_during_execution(self, test_client, sample_graph_data):
        """Test disconnect during execution."""
        with test_client.websocket_connect("/execute") as websocket:
            # Connect
            websocket.send_json({"type": "connect"})
            websocket.receive_json()  # Session message
            
            with pytest.mock.patch("server.server.NODE_REGISTRY", new={}):
                # Start a job
                websocket.send_json({"type": "graph", "graph_data": sample_graph_data})
                websocket.receive_json()  # Status message
                
                # Disconnect abruptly
                # Context manager closes automatically
        
        # Connection should close cleanly


class TestWebSocketSessionManagement:
    """Tests for WebSocket session management."""

    def test_session_persistence(self, test_client):
        """Test that session persists across reconnections."""
        session_id = None
        
        # First connection
        with test_client.websocket_connect("/execute") as websocket1:
            websocket1.send_json({"type": "connect"})
            response1 = websocket1.receive_json()
            session_id = response1["session_id"]
            websocket1.close()
        
        # Reconnect with same session
        with test_client.websocket_connect("/execute") as websocket2:
            websocket2.send_json({"type": "connect", "session_id": session_id})
            response2 = websocket2.receive_json()
            assert response2["session_id"] == session_id
            websocket2.close()

    def test_multiple_concurrent_sessions(self, test_client):
        """Test multiple concurrent WebSocket sessions."""
        sessions = []
        
        # Open multiple connections
        for _ in range(3):
            with test_client.websocket_connect("/execute") as websocket:
                websocket.send_json({"type": "connect"})
                response = websocket.receive_json()
                sessions.append(response["session_id"])
                # Context manager closes automatically
        
        # Verify all sessions are unique
        assert len(set(sessions)) == 3


class TestWebSocketMessageFlow:
    """Tests for complete WebSocket message flow."""

    def test_complete_execution_flow(self, test_client, sample_graph_data):
        """Test complete execution flow."""
        with test_client.websocket_connect("/execute") as websocket:
            # Step 1: Connect
            websocket.send_json({"type": "connect"})
            session_msg = websocket.receive_json()
            assert session_msg["type"] == "session"
            session_id = session_msg["session_id"]
            
            # Step 2: Send graph
            with pytest.mock.patch("server.server.NODE_REGISTRY", new={}):
                websocket.send_json({"type": "graph", "graph_data": sample_graph_data})
                status_msg = websocket.receive_json()
                assert status_msg["type"] == "status"
                assert status_msg["state"] == "queued"
                
                # Step 3: Stop (if needed)
                websocket.send_json({"type": "stop"})
                stopped_msg = websocket.receive_json()
                assert stopped_msg["type"] == "stopped"
            
            # Context manager closes automatically

    def test_reconnect_and_execute(self, test_client, sample_graph_data):
        """Test reconnecting and executing."""
        session_id = None
        
        # First connection
        with test_client.websocket_connect("/execute") as websocket1:
            websocket1.send_json({"type": "connect"})
            response1 = websocket1.receive_json()
            session_id = response1["session_id"]
            websocket1.close()
        
        # Reconnect and execute
        with test_client.websocket_connect("/execute") as websocket2:
            websocket2.send_json({"type": "connect", "session_id": session_id})
            websocket2.receive_json()  # Session message
            
            with pytest.mock.patch("server.server.NODE_REGISTRY", new={}):
                websocket2.send_json({"type": "graph", "graph_data": sample_graph_data})
                response = websocket2.receive_json()
                assert response["type"] == "status"
            
            websocket2.close()


class TestWebSocketEdgeCases:
    """Tests for edge cases in WebSocket handling."""

    def test_empty_graph_data(self, test_client):
        """Test executing with empty graph data."""
        with test_client.websocket_connect("/execute") as websocket:
            websocket.send_json({"type": "connect"})
            websocket.receive_json()  # Session message
            
            # Send empty graph
            websocket.send_json({"type": "graph", "graph_data": {"nodes": [], "links": []}})
            
            # Should receive status or error
            message = websocket.receive_json()
            assert message["type"] in ["status", "error"]
            
            # Context manager closes automatically

    def test_large_graph_data(self, test_client):
        """Test executing with large graph data."""
        # Create a large graph
        large_nodes = [{"id": i, "type": "test_node"} for i in range(100)]
        large_graph = {"nodes": large_nodes, "links": []}
        
        with test_client.websocket_connect("/execute") as websocket:
            websocket.send_json({"type": "connect"})
            websocket.receive_json()  # Session message
            
            with pytest.mock.patch("server.server.NODE_REGISTRY", new={}):
                websocket.send_json({"type": "graph", "graph_data": large_graph})
                message = websocket.receive_json()
                assert message["type"] == "status"
            
            # Context manager closes automatically

    def test_rapid_message_sequence(self, test_client, sample_graph_data):
        """Test rapid sequence of messages."""
        with test_client.websocket_connect("/execute") as websocket:
            websocket.send_json({"type": "connect"})
            websocket.receive_json()  # Session message
            
            with pytest.mock.patch("server.server.NODE_REGISTRY", new={}):
                # Send multiple messages rapidly
                for _ in range(5):
                    websocket.send_json({"type": "graph", "graph_data": sample_graph_data})
                
                # Receive responses
                for _ in range(5):
                    message = websocket.receive_json()
                    assert message["type"] == "status"
            
            # Context manager closes automatically

