import asyncio
from enum import Enum
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from core.graph_executor import GraphExecutor
from core.node_registry import NodeRegistry
from core.serialization import serialize_results
from core.types_registry import ProgressEvent, SerialisableGraph

from .api.websocket_schemas import (
    ServerToClientDataMessage,
    ServerToClientErrorMessage,
    ServerToClientMessage,
    ServerToClientProgressMessage,
    ServerToClientQueuePositionMessage,
    ServerToClientStatusMessage,
)


def _debug(message: str) -> None:
    print(message)


class JobState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    CANCELLED = "cancelled"
    DONE = "done"


class ExecutionJob:
    def __init__(self, job_id: int, websocket: WebSocket, graph_data: SerialisableGraph):
        self.id = job_id
        self.websocket = websocket
        self.graph_data = graph_data
        self.cancel_event = asyncio.Event()
        self.done_event = asyncio.Event()
        self.state = JobState.PENDING


class ExecutionQueue:
    def __init__(self):
        self._pending: list[ExecutionJob] = []
        self._running: ExecutionJob | None = None
        self._id_seq = 0
        self._lock = asyncio.Lock()
        self._wakeup_event = asyncio.Event()

    async def enqueue(self, websocket: WebSocket, graph_data: SerialisableGraph) -> ExecutionJob:
        async with self._lock:
            job = ExecutionJob(self._id_seq, websocket, graph_data)
            self._id_seq += 1
            self._pending.append(job)
            self._wakeup_event.set()
            asyncio.create_task(self._send_position_updates(job))
            return job

    async def get_next(self) -> ExecutionJob | None:
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
            if job in self._pending:
                self._pending.remove(job)
                job.state = JobState.CANCELLED
                job.done_event.set()
            elif self._running is job:
                job.state = JobState.CANCELLED
                job.cancel_event.set()
            else:
                print(f"Queue: Job {job.id} not found in pending or running lists")
            self._wakeup_event.set()

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
                    queue_msg = ServerToClientQueuePositionMessage(
                        type="queue_position", position=pos
                    )
                    await job.websocket.send_json(queue_msg.model_dump())
                except Exception:
                    break
            await asyncio.sleep(1.0)


def _ws_send_async(websocket: WebSocket, payload: ServerToClientMessage):
    """Send JSON async, swallowing exceptions."""
    if websocket.client_state != WebSocketState.CONNECTED:
        return

    async def _send():
        try:
            await websocket.send_json(payload.model_dump(exclude_none=True))
        except Exception:
            pass

    asyncio.create_task(_send())


async def _ws_send_sync(websocket: WebSocket, payload: ServerToClientMessage):
    """Send JSON sync, swallowing exceptions."""
    try:
        await websocket.send_json(payload.model_dump(exclude_none=True))
    except Exception:
        pass


async def _monitor_cancel(
    job: ExecutionJob,
    websocket: WebSocket,
    executor: GraphExecutor,
    execution_task: asyncio.Task[Any] | None = None,
):
    cancel_wait_task = asyncio.create_task(job.cancel_event.wait())

    async def _wait_disconnect():
        while websocket.client_state not in (WebSocketState.DISCONNECTED,):
            await asyncio.sleep(0.05)
        return True

    disconnect_wait_task = asyncio.create_task(_wait_disconnect())

    tasks: set[asyncio.Task[Any]] = set()
    tasks.add(cancel_wait_task)
    tasks.add(disconnect_wait_task)

    if execution_task is not None:
        tasks.add(execution_task)

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    if cancel_wait_task in done:
        if execution_task:
            execution_task.cancel()
        await executor.stop()
    elif disconnect_wait_task in done:
        if execution_task:
            execution_task.cancel()
        await executor.stop()
    elif execution_task and execution_task in done:
        print("STOP_TRACE: execution_task completed normally")

    for t in pending:
        t.cancel()


async def execution_worker(queue: ExecutionQueue, node_registry: NodeRegistry):
    """Worker for executing graph jobs."""
    while True:
        job = await queue.get_next()
        if job is None:
            continue
        websocket = job.websocket
        executor: GraphExecutor | None = None

        if job.cancel_event.is_set():
            _debug(f"Worker: Job {job.id} was cancelled before execution, skipping")
            await queue.mark_done(job)
            continue

        def progress_callback(event: ProgressEvent) -> None:
            # Construct Pydantic progress payload
            kwargs: dict[str, Any] = {}

            if "node_id" in event:
                kwargs["node_id"] = int(event["node_id"])

            if "progress" in event:
                kwargs["progress"] = float(event["progress"])

            if "text" in event:
                kwargs["text"] = str(event["text"])

            if "state" in event:
                kwargs["state"] = event["state"].value

            if "meta" in event:
                kwargs["meta"] = event["meta"]

            progress_msg = ServerToClientProgressMessage(**kwargs)
            _ws_send_async(websocket, progress_msg)

        executor = GraphExecutor(job.graph_data, node_registry)
        executor.set_progress_callback(progress_callback)

        status_msg = ServerToClientStatusMessage(type="status", message="Executing batch")
        await _ws_send_sync(websocket, status_msg)

        execution_task = asyncio.create_task(executor.execute())
        monitor_task = asyncio.create_task(
            _monitor_cancel(job, websocket, executor, execution_task)
        )

        try:
            results = await execution_task
            if websocket.client_state == WebSocketState.CONNECTED:
                data_msg = ServerToClientDataMessage(
                    type="data", results=serialize_results(results)
                )
                await _ws_send_sync(websocket, data_msg)
                status_msg = ServerToClientStatusMessage(type="status", message="Batch finished")
                await _ws_send_sync(websocket, status_msg)
        except Exception as e:
            if websocket.client_state == WebSocketState.CONNECTED:
                error_msg = ServerToClientErrorMessage(
                    type="error", message=str(e), code=None, missing_keys=None
                )
                await _ws_send_sync(websocket, error_msg)
        finally:
            monitor_task.cancel()
            await asyncio.gather(monitor_task, return_exceptions=True)

            job.done_event.set()
            await queue.mark_done(job)
