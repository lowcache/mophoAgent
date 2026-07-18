"""Async DAG stage runner (Phase 3).

Stages run strictly in order (linear DAG). A stage fn is either an async
callable (NPU stages — they submit to the serialized inference queue and
await it) or a plain sync callable (CPU-bound — run via asyncio.to_thread
so the event loop never blocks). Every stage is bounded by its timeout;
a to_thread worker cannot be killed mid-flight, but the pipeline stops
waiting for it and fails with partial results.
"""

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable


class MissingInput(Exception):
    """A stage's declared input key is absent from the run context."""


class StageFailed(Exception):
    """Raised by stage fns on semantic failure (e.g. NPU error dict)."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class PipelineError(Exception):
    """A stage failed or timed out; carries the partial run context."""

    def __init__(self, pipeline: str, stage: str, code: str, message: str,
                 partial: dict):
        super().__init__(f"{pipeline}/{stage} {code}: {message}")
        self.pipeline = pipeline
        self.stage = stage
        self.code = code
        self.message = message
        self.partial = partial


@dataclass
class Stage:
    name: str
    fn: Callable
    inputs: list[str]
    outputs: list[str]
    npu_required: bool = False
    timeout_sec: int = 60


@dataclass
class Pipeline:
    name: str
    stages: list[Stage]
    output_type: str  # key into pipeline.format.FORMATTERS


class PipelineExecutor:
    def __init__(self):
        self.pipelines: dict[str, Pipeline] = {}

    def register(self, pipeline: Pipeline):
        self.pipelines[pipeline.name] = pipeline

    async def run(self, pipeline_name: str, context: dict) -> dict:
        """Run a pipeline; context carries source paths and accumulates
        stage outputs. Returns the formatted output dict. Raises
        PipelineError (with .partial) on stage failure or timeout."""
        pipeline = self.pipelines[pipeline_name]
        run_context = dict(context)
        started = time.monotonic()

        for stage in pipeline.stages:
            stage_input = {}
            for key in stage.inputs:
                if key not in run_context:
                    raise PipelineError(
                        pipeline_name, stage.name, "MISSING_INPUT",
                        f"missing context key '{key}'", run_context)
                stage_input[key] = run_context[key]

            if inspect.iscoroutinefunction(stage.fn):
                coro = stage.fn(**stage_input)
            else:
                coro = asyncio.to_thread(stage.fn, **stage_input)
            try:
                result = await asyncio.wait_for(coro, timeout=stage.timeout_sec)
            except asyncio.TimeoutError:
                raise PipelineError(
                    pipeline_name, stage.name, "STAGE_TIMEOUT",
                    f"exceeded {stage.timeout_sec}s", run_context)
            except StageFailed as e:
                raise PipelineError(
                    pipeline_name, stage.name, e.code, e.message, run_context)
            except PipelineError:
                raise
            except Exception as e:
                raise PipelineError(
                    pipeline_name, stage.name, "STAGE_ERROR",
                    f"{type(e).__name__}: {e}", run_context)

            for key in stage.outputs:
                run_context[key] = (result or {}).get(key)

        run_context["processing_time_ms"] = int(
            (time.monotonic() - started) * 1000)
        from pipeline.format import FORMATTERS
        return FORMATTERS[pipeline.output_type](run_context)
