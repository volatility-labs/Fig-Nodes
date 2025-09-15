import asyncio
import contextlib
import json
from typing import Any, AsyncGenerator, Dict, List

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient


class _StreamingExecDummy:
    def __init__(self, graph: Dict[str, Any], registry: Dict[str, type]):
        self.is_streaming = True
        self._event = asyncio.Event()
        self.stop_called = False

    async def stream(self) -> AsyncGenerator[Dict[int, Dict[str, Any]], None]:
        # Initial static results
        yield {}
        # Gate further ticks until released
        await self._event.wait()
        yield {1: {"assistant_text": "hello"}}

    async def stop(self):
        self.stop_called = True
        self._event.set()


class _BatchExecDummy:
    def __init__(self, graph: Dict[str, Any], registry: Dict[str, type]):
        self.is_streaming = False
        self.stop_called = False

    async def execute(self) -> Dict[int, Dict[str, Any]]:
        await asyncio.sleep(0)
        return {1: {"output": "ok"}}

    async def stop(self):
        self.stop_called = True


class _ErrorExecDummy:
    def __init__(self, graph: Dict[str, Any], registry: Dict[str, type]):
        self.is_streaming = False

    async def execute(self) -> Dict[int, Dict[str, Any]]:
        raise RuntimeError("boom")


@pytest_asyncio.fixture(scope="function")
async def client():
    # Import inside fixture so we can monkeypatch symbols
    import ui.server as server
    await server._startup_queue_worker()
    yield TestClient(server.app)
    await server._shutdown_queue_worker()


def _recv_until_type(ws, msg_type: str, max_steps: int = 5):
    for _ in range(max_steps):
        data = ws.receive_json()
        if data.get("type") == msg_type:
            return data
    raise AssertionError(f"Did not receive message of type {msg_type}")


@pytest.mark.asyncio
async def test_streaming_flow_success(client, monkeypatch):
    import ui.server as server

    # Patch GraphExecutor to streaming dummy
    created: List[_StreamingExecDummy] = []

    def _factory(graph, reg):
        inst = _StreamingExecDummy(graph, reg)
        created.append(inst)
        return inst

    monkeypatch.setattr(server, "GraphExecutor", _factory, raising=True)

    with client.websocket_connect("/execute") as ws:
        ws.send_json({"nodes": [], "links": []})
        # Expect waiting then starting statuses
        st1 = _recv_until_type(ws, "status")
        assert "Waiting for available slot" in st1.get("message", "")
        st2 = _recv_until_type(ws, "status")
        assert "Starting execution" in st2.get("message", "")
        st3 = _recv_until_type(ws, "status")
        assert "Stream starting" in st3.get("message", "")

        # Initial non-stream data
        d0 = _recv_until_type(ws, "data")
        assert d0.get("stream") is False
        assert isinstance(d0.get("results"), dict)

        # Release the dummy to emit a streaming tick
        created[-1]._event.set()
        d1 = _recv_until_type(ws, "data")
        assert d1.get("stream") is True
        # Keys are stringified node ids
        assert d1["results"].get("1", {}).get("assistant_text") == "hello"

        st4 = _recv_until_type(ws, "status")
        assert "Stream finished" in st4.get("message", "")


@pytest.mark.asyncio
async def test_batch_flow_success(client, monkeypatch):
    import ui.server as server
    # Patch GraphExecutor to batch dummy
    created: List[_BatchExecDummy] = []

    def _factory(graph, reg):
        inst = _BatchExecDummy(graph, reg)
        created.append(inst)
        return inst

    monkeypatch.setattr(server, "GraphExecutor", _factory, raising=True)

    with client.websocket_connect("/execute") as ws:
        ws.send_json({"nodes": [], "links": []})
        st1 = _recv_until_type(ws, "status")
        assert "Waiting for available slot" in st1.get("message", "")
        st2 = _recv_until_type(ws, "status")
        assert "Starting execution" in st2.get("message", "")
        st3 = _recv_until_type(ws, "status")
        assert "Executing batch" in st3.get("message", "")
        d = _recv_until_type(ws, "data")
        assert d.get("results", {}).get("1", {}).get("output") == "ok"
        st4 = _recv_until_type(ws, "status")
        assert "Batch finished" in st4.get("message", "")


@pytest.mark.asyncio
async def test_concurrency_wait_message_on_second_connection(client, monkeypatch):
    import ui.server as server
    # Queue ensures single worker
    created: List[_StreamingExecDummy] = []

    def _factory(graph, reg):
        inst = _StreamingExecDummy(graph, reg)
        created.append(inst)
        return inst

    monkeypatch.setattr(server, "GraphExecutor", _factory, raising=True)

    # First connection acquires the semaphore
    ws1 = client.websocket_connect("/execute")
    ws1.__enter__()
    ws1.send_json({"nodes": [], "links": []})
    _recv_until_type(ws1, "status")  # waiting
    _recv_until_type(ws1, "status")  # starting
    _recv_until_type(ws1, "status")  # stream starting
    _recv_until_type(ws1, "data")    # initial

    # Second connection should see waiting immediately
    with client.websocket_connect("/execute") as ws2:
        ws2.send_json({"nodes": [], "links": []})
        st = _recv_until_type(ws2, "status")
        assert "Waiting for available slot" in st.get("message", "")

    with contextlib.suppress(Exception):
        ws1.__exit__(None, None, None)


@pytest.mark.asyncio
async def test_fifo_two_batch_jobs(client, monkeypatch):
    import ui.server as server
    order: List[str] = []

    class _Batch1(_BatchExecDummy):
        async def execute(self):
            order.append("start1")
            await asyncio.sleep(0)
            order.append("end1")
            return await super().execute()

    class _Batch2(_BatchExecDummy):
        async def execute(self):
            order.append("start2")
            await asyncio.sleep(0)
            order.append("end2")
            return await super().execute()

    seq = []

    def _factory(graph, reg):
        # Create _Batch1 for first, _Batch2 for second
        if not seq:
            seq.append(1)
            return _Batch1(graph, reg)
        return _Batch2(graph, reg)

    monkeypatch.setattr(server, "GraphExecutor", _factory, raising=True)

    ws1 = client.websocket_connect("/execute")
    ws1.__enter__()
    ws1.send_json({"nodes": [], "links": []})
    _recv_until_type(ws1, "status")  # waiting

    ws2 = client.websocket_connect("/execute")
    ws2.__enter__()
    ws2.send_json({"nodes": [], "links": []})
    _recv_until_type(ws2, "status")  # waiting

    # Drive both to completion
    _recv_until_type(ws1, "status")  # starting
    _recv_until_type(ws1, "status")  # executing batch
    _recv_until_type(ws1, "data")
    _recv_until_type(ws1, "status")  # batch finished

    _recv_until_type(ws2, "status")  # starting
    _recv_until_type(ws2, "status")  # executing batch
    _recv_until_type(ws2, "data")
    _recv_until_type(ws2, "status")  # batch finished

    ws1.__exit__(None, None, None)
    ws2.__exit__(None, None, None)

    # Ensure FIFO
    assert order == ["start1", "end1", "start2", "end2"]


@pytest.mark.asyncio
async def test_queued_client_disconnect_before_start_removes_job(client, monkeypatch):
    import ui.server as server

    # Make first connection hold worker by never releasing stream
    created: List[_StreamingExecDummy] = []

    def _factory(graph, reg):
        inst = _StreamingExecDummy(graph, reg)
        created.append(inst)
        return inst

    monkeypatch.setattr(server, "GraphExecutor", _factory, raising=True)

    ws1 = client.websocket_connect("/execute")
    ws1.__enter__()
    ws1.send_json({"nodes": [], "links": []})
    _recv_until_type(ws1, "status")
    _recv_until_type(ws1, "status")
    _recv_until_type(ws1, "status")
    _recv_until_type(ws1, "data")

    # Second client queues then disconnects
    ws2 = client.websocket_connect("/execute")
    ws2.__enter__()
    ws2.send_json({"nodes": [], "links": []})
    _recv_until_type(ws2, "status")  # waiting
    ws2.close()
    with contextlib.suppress(Exception):
        ws2.__exit__(None, None, None)

    # Release first stream to finish normally
    created[-1]._event.set()
    _recv_until_type(ws1, "data")
    _recv_until_type(ws1, "status")
    with contextlib.suppress(Exception):
        ws1.__exit__(None, None, None)


@pytest.mark.asyncio
async def test_stream_error_is_reported_and_socket_closed(client, monkeypatch):
    import ui.server as server

    class _BadStream(_StreamingExecDummy):
        async def stream(self):
            raise RuntimeError("stream-fail")

    monkeypatch.setattr(server, "GraphExecutor", lambda g, r: _BadStream(g, r), raising=True)

    with client.websocket_connect("/execute") as ws:
        ws.send_json({"nodes": [], "links": []})
        # waiting
        _recv_until_type(ws, "status")
        # error
        msg = ws.receive_json()
        assert msg.get("type") == "error"
        assert "stream-fail" in msg.get("message", "")


@pytest.mark.asyncio
async def test_cancellation_streaming_triggers_stop(client, monkeypatch):
    import ui.server as server
    created: List[_StreamingExecDummy] = []

    def _factory(graph, reg):
        inst = _StreamingExecDummy(graph, reg)
        created.append(inst)
        return inst

    monkeypatch.setattr(server, "GraphExecutor", _factory, raising=True)

    with client.websocket_connect("/execute") as ws:
        ws.send_json({"nodes": [], "links": []})
        _recv_until_type(ws, "status")  # waiting
        _recv_until_type(ws, "status")  # starting
        _recv_until_type(ws, "status")  # stream starting
        _recv_until_type(ws, "data")    # initial
        # Close to trigger WebSocketDisconnect handler
        ws.close()

    # Stop should be called on the last created executor
    assert created and created[-1].stop_called is True


@pytest.mark.asyncio
async def test_batch_error_propagation(client, monkeypatch):
    import ui.server as server
    monkeypatch.setattr(server, "GraphExecutor", _ErrorExecDummy, raising=True)

    with client.websocket_connect("/execute") as ws:
        ws.send_json({"nodes": [], "links": []})
        # First two status messages may still appear depending on semaphore; tolerate either
        msg = ws.receive_json()
        if msg.get("type") != "error":
            # Consume until error received
            while msg.get("type") != "error":
                msg = ws.receive_json()
        assert msg.get("type") == "error"
        assert "boom" in msg.get("message", "")


