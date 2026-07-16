"""Serialized priority inference queue.

Only one inference runs at any time. Priorities: 0 interactive,
1 scheduled, 2 batch. A running batch job is cancelled and requeued from
scratch when interactive work arrives (D8: no suspend/resume).
"""

import asyncio
import itertools
import time
from dataclasses import dataclass, field
from typing import Any

PRIORITY_INTERACTIVE = 0
PRIORITY_SCHEDULED = 1
PRIORITY_BATCH = 2

_seq = itertools.count()  # FIFO tie-break within a priority


@dataclass(order=True)
class InferenceRequest:
    priority: int
    timestamp: float
    seq: int
    model: str = field(compare=False)
    input: Any = field(compare=False)
    future: asyncio.Future = field(compare=False)


class InferenceQueue:
    def __init__(self, bridge):
        self.bridge = bridge
        self.queue: asyncio.PriorityQueue[InferenceRequest] = asyncio.PriorityQueue()
        self._worker_task: asyncio.Task | None = None
        self._running: InferenceRequest | None = None
        self._running_task: asyncio.Task | None = None

    @property
    def depth(self) -> int:
        return self.queue.qsize() + (1 if self._running else 0)

    async def submit(self, model: str, input: Any, priority: int = PRIORITY_BATCH) -> Any:
        # Worker starts lazily: FastMCP owns the app lifespan, so there is
        # no startup hook with a running loop before the first request.
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.get_running_loop().create_task(self._worker_loop())
        future = asyncio.get_running_loop().create_future()
        request = InferenceRequest(priority, time.time(), next(_seq), model, input, future)
        await self.queue.put(request)
        # Preempt: interactive work cancels a running batch job (requeued
        # from scratch by the worker; its caller's future stays pending).
        if (priority == PRIORITY_INTERACTIVE
                and self._running is not None
                and self._running.priority == PRIORITY_BATCH
                and self._running_task is not None):
            self._running_task.cancel()
        return await future

    async def _worker_loop(self):
        while True:
            request = await self.queue.get()
            if request.future.cancelled():
                continue
            self._running = request
            self._running_task = asyncio.create_task(
                self.bridge.infer(request.model, request.input))
            try:
                result = await self._running_task
                if not request.future.done():
                    request.future.set_result(result)
            except asyncio.CancelledError:
                # Preempted: requeue the same request (same still-pending
                # future) behind the interactive work.
                await self.queue.put(InferenceRequest(
                    request.priority, request.timestamp, next(_seq),
                    request.model, request.input, request.future))
            except Exception as e:
                if not request.future.done():
                    request.future.set_exception(e)
            finally:
                self._running = None
                self._running_task = None
