import asyncio
import logging
from enum import Enum
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from core.graph_executor import GraphExecutor
from core.node_registry import NodeRegistry
from core.serialization import serialize_results
from core.types_registry import (
    ExecutionResult,
    ExecutionResults,
    NodeCategory,
    NodeOutput,
    ProgressEvent,
    SerialisableGraph,
)

from .api.websocket_schemas import (
    ExecutionState,
    ServerToClientDataMessage,
    ServerToClientErrorMessage,
    ServerToClientMessage,
    ServerToClientProgressMessage,
    ServerToClientQueuePositionMessage,
    ServerToClientStatusMessage,
    ServerToClientStoppedMessage,
)

logger = logging.getLogger(__name__)


def _debug(message: str) -> None:
    """Debug logging helper - use logger.debug instead of print for better control."""
    logger.debug(message)


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
                logger.warning(f"Queue: Job {job.id} not found in pending or running lists")
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
                        type="queue_position", position=pos, job_id=job.id
                    )
                    await job.websocket.send_json(queue_msg.model_dump())
                except Exception:
                    break
            await asyncio.sleep(1.0)


def _ws_send_async(websocket: WebSocket, payload: ServerToClientMessage):
    """Send JSON async, swallowing exceptions but logging errors."""
    if websocket.client_state != WebSocketState.CONNECTED:
        logger.warning(f"_ws_send_async: Skipping send - websocket not connected (state: {websocket.client_state})")
        return

    async def _send():
        try:
            data = payload.model_dump(exclude_none=True)
            # Log payload size for debugging large messages
            payload_type = data.get("type", "unknown")
            if payload_type == "data" and "results" in data:
                results = data.get("results", {})
                for node_id, node_result in results.items():
                    if isinstance(node_result, dict) and "images" in node_result:
                        images = node_result.get("images", {})
                        for label, img_data in images.items():
                            if isinstance(img_data, str):
                                size_kb = len(img_data) / 1024
                                logger.warning(f"_ws_send_async: Sending image '{label}' ({size_kb:.1f} KB)")
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"_ws_send_async: Failed to send payload type={payload.type}: {e}", exc_info=True)

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
    """Monitor for cancellation or disconnect. Returns reason if stopped."""

    async def wait_for_cancel():
        await job.cancel_event.wait()
        return "user"

    async def wait_for_disconnect():
        while websocket.client_state not in (WebSocketState.DISCONNECTED,):
            await asyncio.sleep(0.05)
        return "disconnect"

    tasks: set[asyncio.Task[str]] = {
        asyncio.create_task(wait_for_cancel()),
        asyncio.create_task(wait_for_disconnect()),
    }

    if execution_task:

        async def wait_for_completion():
            await execution_task
            return "completed"

        tasks.add(asyncio.create_task(wait_for_completion()))

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    # Get result from first completed task
    reason = await done.pop()

    # Cancel execution if it wasn't already done
    if reason in ("user", "disconnect"):
        if execution_task and not execution_task.done():
            execution_task.cancel()
        await executor.stop(reason=reason)

    # Cancel remaining monitor tasks and await them to clean up properly
    for t in pending:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass  # Expected when cancelling a task

    return reason


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

        # Capture job.id for use in callback
        job_id = job.id

        def guarded_progress_callback(event: ProgressEvent) -> None:
            # Don't send progress if executor is stopped or stopping
            if executor and (executor.is_stopped or executor.is_stopping):
                return

            # Don't send if websocket disconnected
            if websocket.client_state == WebSocketState.DISCONNECTED:
                return

            # Construct Pydantic progress payload
            kwargs: dict[str, Any] = {}

            if "node_id" in event:
                kwargs["node_id"] = int(event["node_id"])

            if "progress" in event:
                kwargs["progress"] = float(event["progress"])

            if "text" in event:
                kwargs["text"] = str(event["text"])

            if "state" in event:
                kwargs["state"] = event[
                    "state"
                ]  # ProgressState enum - Pydantic will serialize to string

            if "meta" in event:
                kwargs["meta"] = event["meta"]

            # Send progress message to UI via websocket
            kwargs["job_id"] = job_id
            progress_msg = ServerToClientProgressMessage(**kwargs)
            _ws_send_async(websocket, progress_msg)

        def guarded_result_callback(node_id: int, outputs: NodeOutput) -> None:
            logger.debug(
                f"RESULT_TRACE: guarded_result_callback called for node {node_id}, outputs keys: {list(outputs.keys())}"
            )
            # Same guards as progress callback
            if executor and (executor.is_stopped or executor.is_stopping):
                logger.debug(f"RESULT_TRACE: Skipping node {node_id} - executor stopped/stopping")
                return
            if websocket.client_state == WebSocketState.DISCONNECTED:
                logger.debug(f"RESULT_TRACE: Skipping node {node_id} - websocket disconnected")
                return

            logger.debug(f"RESULT_TRACE: Sending immediate result for node {node_id} via websocket")
            data_msg = ServerToClientDataMessage(
                type="data",
                results=serialize_results({node_id: outputs}),
                job_id=job_id,
            )
            _ws_send_async(websocket, data_msg)
            logger.debug(f"RESULT_TRACE: Sent immediate result for node {node_id}")

        def _should_emit_immediately_for_node_id(
            node_id: int, executor: GraphExecutor | None
        ) -> bool:
            """Check if a node should emit results immediately (IO category nodes)."""
            if not executor:
                return False
            node = executor.nodes.get(node_id)
            if not node:
                return False
            return node.CATEGORY == NodeCategory.IO

        execution_task: asyncio.Task[Any] | None = None
        monitor_task: asyncio.Task[Any] | None = None
        result: ExecutionResult = ExecutionResult.error_result("Unexpected error")

        try:
            # Create executor inside try block to catch initialization errors
            executor = GraphExecutor(job.graph_data, node_registry)
            executor.set_progress_callback(guarded_progress_callback)
            executor.set_result_callback(guarded_result_callback)
            logger.debug(
                f"RESULT_TRACE: Executor created, result_callback set: {hasattr(executor, '_result_callback') and getattr(executor, '_result_callback') is not None}"
            )
            # Log node categories for debugging
            for node_id, node in executor.nodes.items():
                logger.debug(
                    f"RESULT_TRACE: Node {node_id} ({type(node).__name__}) has category: {node.CATEGORY}"
                )

            status_msg = ServerToClientStatusMessage(
                type="status",
                state=ExecutionState.RUNNING,
                message="Executing batch",
                job_id=job.id,
            )
            await _ws_send_sync(websocket, status_msg)

            execution_task = asyncio.create_task(executor.execute())
            monitor_task = asyncio.create_task(
                _monitor_cancel(job, websocket, executor, execution_task)
            )

            results = await execution_task

            # Check if we were cancelled during execution
            if executor.is_stopped:
                result = ExecutionResult.cancelled(by=executor.cancellation_reason or "unknown")
            else:
                result = ExecutionResult.success(results)

        except asyncio.CancelledError:
            # Task was cancelled - this is expected
            cancellation_reason = "unknown"
            if executor and executor.cancellation_reason:
                cancellation_reason = executor.cancellation_reason
            result = ExecutionResult.cancelled(by=cancellation_reason)
        except Exception as e:
            logger.error(f"Error executing job {job.id}: {e}", exc_info=True)
            result = ExecutionResult.error_result(str(e))

        finally:
            # Wait for monitor_task properly
            if monitor_task and not monitor_task.done():
                monitor_task.cancel()
            if monitor_task:
                await asyncio.gather(monitor_task, return_exceptions=True)

            # Send appropriate message based on result
            if websocket.client_state == WebSocketState.CONNECTED:
                if result.is_success and result.results is not None:
                    # Filter out IO category nodes that already emitted immediately
                    final_results = {
                        node_id: outputs
                        for node_id, outputs in result.results.items()
                        if not _should_emit_immediately_for_node_id(node_id, executor)
                    }

                    # Send final results (may be empty dict if all nodes were IO)
                    data_msg = ServerToClientDataMessage(
                        type="data",
                        results=serialize_results(final_results),
                        job_id=job.id,
                    )
                    await _ws_send_sync(websocket, data_msg)
                    status_msg = ServerToClientStatusMessage(
                        type="status",
                        state=ExecutionState.FINISHED,
                        message="Batch finished",
                        job_id=job.id,
                    )
                    await _ws_send_sync(websocket, status_msg)

                elif result.is_cancelled:
                    stopped_msg = ServerToClientStoppedMessage(
                        type="stopped",
                        message=f"Execution stopped: {result.cancelled_by}",
                        job_id=job.id,
                    )
                    await _ws_send_sync(websocket, stopped_msg)

                else:  # ERROR
                    error_msg = ServerToClientErrorMessage(
                        type="error",
                        message=result.error or "Unknown error",
                        code=None,
                        missing_keys=None,
                        job_id=job.id,
                    )
                    await _ws_send_sync(websocket, error_msg)

            job.done_event.set()
            await queue.mark_done(job)
