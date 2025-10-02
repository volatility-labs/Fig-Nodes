# queue.py - Extracted queue management for graph execution

import asyncio
from typing import Dict, Any, List
from enum import Enum
from fastapi import WebSocket
from starlette.websockets import WebSocketState
import typing

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
            print(f"STOP_TRACE: cancel_job called in queue.py for job {job.id}, current state: {job.state}")
            print(f"Queue: Cancelling job {job.id}, current state: {job.state}")
            if job in self._pending:
                print(f"Queue: Job {job.id} was pending, removing from queue")
                self._pending.remove(job)
                job.state = JobState.CANCELLED
                job.done_event.set()
            elif self._running is job:
                print(f"STOP_TRACE: Job {job.id} is running, setting cancel_event in queue.py")
                job.state = JobState.CANCELLED
                job.cancel_event.set()
            else:
                print(f"Queue: Job {job.id} not found in pending or running lists")
            self._wakeup_event.set()
            print(f"STOP_TRACE: cancel_job completed in queue.py for job {job.id}")
            print(f"Queue: Job {job.id} cancellation initiated")

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

async def execution_worker(queue: ExecutionQueue, node_registry: Dict[str, type]):
    from core.graph_executor import GraphExecutor  # Import here to avoid circular deps

    while True:
        job = await queue.get_next()
        if job is None:
            continue
        websocket = job.websocket
        executor: typing.Optional[GraphExecutor] = None

        if job.cancel_event.is_set():
            import os
            if os.getenv("DEBUG_QUEUE") == "1":
                print(f"Worker: Job {job.id} was cancelled before execution, skipping")
            job.done_event.set()
            await queue.mark_done(job)
            continue

        def progress_callback(node_id: int, progress: float, text: str = ""):
            if websocket.client_state != WebSocketState.CONNECTED:
                return
            async def safe_send():
                try:
                    await websocket.send_json({
                        "type": "progress",
                        "node_id": node_id,
                        "progress": progress,
                        "text": text
                    })
                except Exception:
                    pass
            asyncio.create_task(safe_send())

        try:
            import os
            if os.getenv("DEBUG_QUEUE") == "1":
                print("Worker: Creating GraphExecutor")
            executor = GraphExecutor(job.graph_data, node_registry)
            executor.set_progress_callback(progress_callback)
            if os.getenv("DEBUG_QUEUE") == "1":
                print(f"Worker: GraphExecutor created, is_streaming={executor.is_streaming}")

            if job.cancel_event.is_set():
                if os.getenv("DEBUG_QUEUE") == "1":
                    print(f"Worker: Job {job.id} was cancelled during setup, skipping execution")
                job.done_event.set()
                await queue.mark_done(job)
                return

            try:
                await websocket.send_json({"type": "status", "message": "Starting execution"})
            except Exception:
                pass

            if executor.is_streaming:
                print("STOP_TRACE: Processing as stream in execution_worker")
                import os
                if os.getenv("DEBUG_QUEUE") == "1":
                    print("Worker: Executing streaming path")
                try:
                    await websocket.send_json({"type": "status", "message": "Stream starting..."})
                except Exception:
                    pass
                stream_generator = executor.stream()
                try:
                    if os.getenv("DEBUG_QUEUE") == "1":
                        print("Worker: Getting initial results from stream generator")
                    initial_results = await anext(stream_generator)
                    if os.getenv("DEBUG_QUEUE") == "1":
                        print(f"Worker: Got initial results: {list(initial_results.keys())}")
                except StopAsyncIteration:
                    if os.getenv("DEBUG_QUEUE") == "1":
                        print("Worker: Stream generator exhausted on first anext()")
                    initial_results = {}
                try:
                    await websocket.send_json({"type": "data", "results": _serialize_results(initial_results), "stream": False})
                except Exception:
                    pass

                async def monitor_cancel():
                    print(f"STOP_TRACE: monitor_cancel started for job {job.id} in queue.py")
                    checks = 0
                    while True:
                        await asyncio.sleep(0.05)
                        checks += 1
                        if job.cancel_event.is_set():
                            print(f"STOP_TRACE: Detected cancel_event in monitor_cancel for job {job.id} after {checks} checks")
                            print(f"STOP_TRACE: Calling executor.stop() in queue.py")
                            await executor.stop()
                            print(f"STOP_TRACE: executor.stop() completed in queue.py")
                            break
                        if websocket.client_state in (WebSocketState.CLOSED, WebSocketState.DISCONNECTED):
                            print(f"Worker: Job {job.id} WebSocket disconnected, stopping executor")
                            if os.getenv("DEBUG_QUEUE") == "1":
                                print("Worker: WebSocket disconnected, stopping executor")
                            await executor.stop()
                            break

                monitor_task = asyncio.create_task(monitor_cancel())

                try:
                    if os.getenv("DEBUG_QUEUE") == "1":
                        print("Worker: Starting stream loop")
                    while True:
                        try:
                            results = await anext(stream_generator)
                            if os.getenv("DEBUG_QUEUE") == "1":
                                print(f"Worker: Got stream result: {list(results.keys())}")
                        except StopAsyncIteration:
                            if os.getenv("DEBUG_QUEUE") == "1":
                                print("Worker: Stream generator exhausted (StopAsyncIteration)")
                            break
                        except Exception as e:
                            print(f"Worker: Unexpected exception in stream: {e}")
                            raise
                        try:
                            await websocket.send_json({"type": "data", "results": _serialize_results(results), "stream": True})
                        except Exception:
                            print("Worker: Exception sending stream data, stopping executor")
                            await executor.stop()
                            break
                finally:
                    monitor_task.cancel()
                    try:
                        import os
                        if os.getenv("DEBUG_QUEUE") == "1":
                            print("Worker: Stream finished, sending final status")
                        await websocket.send_json({"type": "status", "message": "Stream finished"})
                    except Exception:
                        pass
            else:
                print("STOP_TRACE: Processing as batch in execution_worker")
                try:
                    await websocket.send_json({"type": "status", "message": "Executing batch"})
                except Exception:
                    pass

                execution_task = asyncio.create_task(executor.execute())

                async def monitor_cancel():
                    print(f"STOP_TRACE: monitor_cancel started for batch job {job.id}")
                    cancel_wait_task = asyncio.create_task(job.cancel_event.wait())
                    done, pending = await asyncio.wait(
                        [cancel_wait_task, execution_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    if cancel_wait_task in done:
                        print(f"STOP_TRACE: cancel_event detected, cancelling execution_task")
                        execution_task.cancel()
                        print(f"STOP_TRACE: Calling executor.stop() after cancel")
                        await executor.stop()
                        print(f"STOP_TRACE: executor.stop() completed")
                    elif execution_task in done:
                        print(f"STOP_TRACE: execution_task completed normally")
                    # Check for disconnect (though may be after completion)
                    if websocket.client_state in (WebSocketState.CLOSED, WebSocketState.DISCONNECTED):
                        print(f"STOP_TRACE: WebSocket disconnected detected in monitor_cancel")
                        execution_task.cancel()
                        await executor.stop()

                monitor_task = asyncio.create_task(monitor_cancel())

                try:
                    results = await execution_task
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json({"type": "data", "results": _serialize_results(results)})
                        await websocket.send_json({"type": "status", "message": "Batch finished"})
                except asyncio.CancelledError:
                    print("STOP_TRACE: Caught CancelledError in execution_task await")
                except Exception as e:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json({"type": "error", "message": str(e)})
                finally:
                    monitor_task.cancel()
                    await asyncio.gather(monitor_task, return_exceptions=True)

        except Exception as e:
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            try:
                if websocket.client_state not in (WebSocketState.DISCONNECTED, WebSocketState.CLOSED):
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
