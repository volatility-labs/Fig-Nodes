# queue.py - Extracted queue management for graph execution

import asyncio
from typing import Dict, Any, List
from enum import Enum
from fastapi import WebSocket
from starlette.websockets import WebSocketState
import typing
import pandas as pd
import os

class JobState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    CANCELLED = "cancelled"
    DONE = "done"

class ExecutionJob:
    def __init__(self, job_id: int, websocket: WebSocket, graph_data: Dict[str, Any]):
        self.id = job_id
        self.websocket = websocket
        self.graph_data = graph_data
        self.cancel_event = asyncio.Event()
        self.done_event = asyncio.Event()
        self.state = JobState.PENDING

class ExecutionQueue:
    def __init__(self):
        self._pending: List[ExecutionJob] = []
        self._running: typing.Optional[ExecutionJob] = None
        self._id_seq = 0
        self._lock = asyncio.Lock()
        self._wakeup_event = asyncio.Event()

    async def enqueue(self, websocket: WebSocket, graph_data: Dict[str, Any]) -> ExecutionJob:
        async with self._lock:
            job = ExecutionJob(self._id_seq, websocket, graph_data)
            self._id_seq += 1
            self._pending.append(job)
            self._wakeup_event.set()
            asyncio.create_task(self._send_position_updates(job))
            return job


    async def get_next(self) -> typing.Optional[ExecutionJob]:
        while True:
            async with self._lock:
                if self._pending:
                    job = self._pending.pop(0)
                    job.state = JobState.RUNNING
                    self._running = job
                    return job
            await self._wakeup_event.wait()
            self._wakeup_event.clear()

    async def mark_done(self, job: ExecutionJob):
        async with self._lock:
            if self._running is job:
                self._running = None
                job.state = JobState.DONE
                job.done_event.set()
            self._wakeup_event.set()

    async def cancel_job(self, job: ExecutionJob):
        async with self._lock:
            _debug(f"STOP_TRACE: cancel_job called in queue.py for job {job.id}, current state: {job.state}")
            _debug(f"Queue: Cancelling job {job.id}, current state: {job.state}")
            if job in self._pending:
                _debug(f"Queue: Job {job.id} was pending, removing from queue")
                self._pending.remove(job)
                job.state = JobState.CANCELLED
                job.done_event.set()
            elif self._running is job:
                _debug(f"STOP_TRACE: Job {job.id} is running, setting cancel_event in queue.py")
                job.state = JobState.CANCELLED
                job.cancel_event.set()
            else:
                _debug(f"Queue: Job {job.id} not found in pending or running lists")
            self._wakeup_event.set()
            _debug(f"STOP_TRACE: cancel_job completed in queue.py for job {job.id}")
            _debug(f"Queue: Job {job.id} cancellation initiated")

    async def position(self, job: ExecutionJob) -> int:
        async with self._lock:
            if self._running is job:
                return 0
            try:
                return self._pending.index(job) + 1
            except ValueError:
                return -1

    async def _send_position_updates(self, job: ExecutionJob):
        while job.state == JobState.PENDING:
            pos = await self.position(job)
            if job.websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await job.websocket.send_json({"type": "queue_position", "position": pos})
                except Exception:
                    break
            await asyncio.sleep(1.0)


def _debug(*parts):
    """Debug print helper, gated by DEBUG_QUEUE env var."""
    if os.getenv("DEBUG_QUEUE") == "1":
        print(*parts)


def _ws_send_async(websocket: WebSocket, payload: Dict[str, Any]):
    """Send JSON async, swallowing exceptions."""
    if websocket.client_state != WebSocketState.CONNECTED:
        return
    async def _send():
        try:
            await websocket.send_json(payload)
        except Exception:
            pass
    asyncio.create_task(_send())


async def _ws_send_sync(websocket: WebSocket, payload: Dict[str, Any], stop_on_fail=False, executor=None):
    """Send JSON sync, optionally stop executor on fail."""
    try:
        await websocket.send_json(payload)
    except Exception:
        if stop_on_fail and executor:
            await executor.stop()


async def _monitor_cancel(job: ExecutionJob, websocket: WebSocket, executor, execution_task=None):
    """Unified cancellation monitoring for both streaming and batch jobs."""
    _debug(f"STOP_TRACE: monitor_cancel started for job {job.id}")
    cancel_wait_task = asyncio.create_task(job.cancel_event.wait())
    async def _wait_disconnect():
        while websocket.client_state not in (WebSocketState.DISCONNECTED,):
            await asyncio.sleep(0.05)
        return True
    disconnect_wait_task = asyncio.create_task(_wait_disconnect())

    tasks = {cancel_wait_task, disconnect_wait_task}
    if execution_task:
        tasks.add(execution_task)

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    if cancel_wait_task in done:
        _debug(f"STOP_TRACE: cancel_event detected, cancelling execution_task")
        if execution_task:
            execution_task.cancel()
        _debug(f"STOP_TRACE: Calling executor.stop() after cancel")
        await executor.stop()
        _debug(f"STOP_TRACE: executor.stop() completed")
    elif disconnect_wait_task in done:
        _debug(f"Worker: Job {job.id} WebSocket disconnected, stopping executor")
        if execution_task:
            execution_task.cancel()
        await executor.stop()
    elif execution_task and execution_task in done:
        _debug(f"STOP_TRACE: execution_task completed normally")

    for t in pending:
        t.cancel()


async def execution_worker(queue: ExecutionQueue, node_registry: Dict[str, type]):
    import core.graph_executor as graph_executor_module  # Import module so monkeypatching works

    while True:
        job = await queue.get_next()
        if job is None:
            continue
        websocket = job.websocket
        executor: typing.Optional[typing.Any] = None

        if job.cancel_event.is_set():
            _debug(f"Worker: Job {job.id} was cancelled before execution, skipping")
            await queue.mark_done(job)
            continue

        def progress_callback(node_id: int, progress: float, text: str = ""):
            _ws_send_async(websocket, {
                "type": "progress",
                "node_id": node_id,
                "progress": progress,
                "text": text
            })

        try:
            _debug("Worker: Creating GraphExecutor")
            # Resolve GraphExecutor at runtime from module to honor monkeypatch
            executor = graph_executor_module.GraphExecutor(job.graph_data, node_registry)
            executor.set_progress_callback(progress_callback)
            _debug(f"Worker: GraphExecutor created, is_streaming={executor.is_streaming}")

            if job.cancel_event.is_set():
                _debug(f"Worker: Job {job.id} was cancelled during setup, skipping execution")
                await queue.mark_done(job)
                return

            # Note: Initial "Starting execution" status is sent by the server endpoint
            # to avoid duplicate status messages here.

            if executor.is_streaming:
                _debug("Worker: Executing streaming path")
                await _ws_send_sync(websocket, {"type": "status", "message": "Stream starting..."})
                stream_generator = executor.stream()

                # Start cancellation watcher BEFORE first pull to allow immediate stop
                monitor_task = asyncio.create_task(_monitor_cancel(job, websocket, executor))

                # Race first pull against cancel for immediate response to stop
                try:
                    _debug("Worker: Getting initial results from stream generator")
                    initial_pull = asyncio.create_task(anext(stream_generator))
                    cancel_wait = asyncio.create_task(job.cancel_event.wait())
                    done, pending = await asyncio.wait({initial_pull, cancel_wait}, return_when=asyncio.FIRST_COMPLETED)
                    if cancel_wait in done and initial_pull not in done:
                        # Stop immediately before first results
                        await executor.stop()
                        initial_results = {}
                    else:
                        initial_results = await initial_pull
                        _debug(f"Worker: Got initial results: {list(initial_results.keys())}")
                except StopAsyncIteration:
                    _debug("Worker: Stream generator exhausted on first anext()")
                    initial_results = {}
                await _ws_send_sync(websocket, {"type": "data", "results": _serialize_results(initial_results), "stream": False})

                stream_failed = False
                try:
                    _debug("Worker: Starting stream loop")
                    while True:
                        try:
                            results = await anext(stream_generator)
                            _debug(f"Worker: Got stream result: {list(results.keys())}")
                        except StopAsyncIteration:
                            _debug("Worker: Stream generator exhausted (StopAsyncIteration)")
                            break
                        except Exception as e:
                            print(f"Worker: Unexpected exception in stream: {e}")
                            stream_failed = True
                            raise
                        await _ws_send_sync(websocket, {"type": "data", "results": _serialize_results(results), "stream": True}, stop_on_fail=True, executor=executor)
                finally:
                    monitor_task.cancel()
                if not stream_failed:
                    _debug("Worker: Stream finished, sending final status")
                    await _ws_send_sync(websocket, {"type": "status", "message": "Stream finished"})
            else:
                _debug("STOP_TRACE: Processing as batch in execution_worker")
                await _ws_send_sync(websocket, {"type": "status", "message": "Executing batch"})

                execution_task = asyncio.create_task(executor.execute())

                monitor_task = asyncio.create_task(_monitor_cancel(job, websocket, executor, execution_task))

                try:
                    results = await execution_task
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await _ws_send_sync(websocket, {"type": "data", "results": _serialize_results(results)})
                        await _ws_send_sync(websocket, {"type": "status", "message": "Batch finished"})
                except asyncio.CancelledError:
                    _debug("STOP_TRACE: Caught CancelledError in execution_task await")
                except Exception as e:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await _ws_send_sync(websocket, {"type": "error", "message": str(e)})
                finally:
                    monitor_task.cancel()
                    await asyncio.gather(monitor_task, return_exceptions=True)

        except Exception as e:
            await _ws_send_sync(websocket, {"type": "error", "message": str(e)})
        finally:
            try:
                if websocket.client_state not in (WebSocketState.DISCONNECTED,):
                    await websocket.close()
            except Exception:
                pass
            job.done_event.set()
            await queue.mark_done(job)

def _serialize_value(v: Any):
    if isinstance(v, list):
        return [_serialize_value(item) for item in v]
    if isinstance(v, dict):
        return {str(key): _serialize_value(val) for key, val in v.items()}
    if hasattr(v, 'to_dict'):
        return v.to_dict()
    if isinstance(v, pd.DataFrame):
        return v.to_dict(orient='records')
    return str(v)

def _serialize_results(results: Dict[int, Dict[str, Any]]):
    return {str(node_id): {out: _serialize_value(val) for out, val in node_res.items()} for node_id, node_res in results.items()}
