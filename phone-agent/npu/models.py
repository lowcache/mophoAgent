"""Model registry and backend process lifecycle (D4, D5).

Each model is served by a persistent child process (llama-server /
whisper-server) on loopback. "Loading" a model means its backend process
is running and answering health checks; "unloading" kills the process.
CPU baseline per D5 — no QNN backend exists in mainline llama.cpp.
"""

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from config.settings import (
    EMBED_PORT,
    LAZY_UNLOAD_IDLE_SEC,
    LLM_PORT,
    MODELS_DIR,
    RUNTIME_DIR,
    WHISPER_PORT,
)


@dataclass
class ModelSpec:
    name: str
    path: Path
    kind: Literal["whisper", "ocr", "embed", "classify", "llm"]
    quant: str
    max_context: int              # tokens, or seconds of audio for whisper
    load_on_start: bool
    memory_estimate_mb: int
    backend: Literal["llama.cpp", "whisper.cpp", "onnx"]
    port: int | None = None       # loopback port of the serving process
    server_args: tuple[str, ...] = ()


SPECS: dict[str, ModelSpec] = {
    "whisper-small.en-q8_0": ModelSpec(
        name="whisper-small.en-q8_0",
        path=MODELS_DIR / "whisper-small.en-q8_0.gguf",
        kind="whisper", quant="q8_0", max_context=30,
        load_on_start=True, memory_estimate_mb=600,
        backend="whisper.cpp", port=WHISPER_PORT,
        server_args=("-t", "4", "-bs", "1"),
    ),
    "ocr-model": ModelSpec(
        name="ocr-model",
        path=MODELS_DIR / "ocr",   # directory: det/rec onnx + charset
        kind="ocr", quant="int8", max_context=4096,
        load_on_start=False, memory_estimate_mb=256,
        backend="onnx", port=None,  # in-process onnxruntime, no server
    ),
    "all-minilm-l6-v2-q4": ModelSpec(
        name="all-minilm-l6-v2-q4",
        path=MODELS_DIR / "all-minilm-l6-v2-q4.gguf",
        kind="embed", quant="q4_0", max_context=256,
        load_on_start=True, memory_estimate_mb=128,
        backend="llama.cpp", port=EMBED_PORT,
        server_args=("--embedding", "--pooling", "mean", "-c", "512", "-t", "4", "-tb", "4"),
    ),
    # classify and llm share one llama-server instance (same weights, same
    # port); the registry keys differ so priorities and lifecycle stay per-use.
    "qwen2.5-1.5b-q4-classify": ModelSpec(
        name="qwen2.5-1.5b-q4-classify",
        path=MODELS_DIR / "qwen2.5-1.5b-q4.gguf",
        kind="classify", quant="q4_k_m", max_context=1024,
        load_on_start=False, memory_estimate_mb=2048,
        backend="llama.cpp", port=LLM_PORT,
        server_args=("-c", "1024", "-np", "1", "-t", "4", "-tb", "4"),
    ),
    "qwen2.5-1.5b-q4": ModelSpec(
        name="qwen2.5-1.5b-q4",
        path=MODELS_DIR / "qwen2.5-1.5b-q4.gguf",
        kind="llm", quant="q4_k_m", max_context=1024,
        load_on_start=False, memory_estimate_mb=2048,
        backend="llama.cpp", port=LLM_PORT,
        server_args=("-c", "1024", "-np", "1", "-t", "4", "-tb", "4"),
    ),
}


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _backend_ready(port: int) -> bool:
    """llama-server binds its socket immediately but answers 503 until the
    model finishes loading — a bare port probe is not readiness."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        return e.code == 404   # no /health route: port-open is the best signal
    except OSError:
        return False


class ModelRegistry:
    """Tracks specs and owns the backend server processes.

    Thread-safe: called from the asyncio worker (via to_thread) and from
    the idle-unload monitor thread.
    """

    def __init__(self, specs: dict[str, ModelSpec] | None = None):
        self.specs = specs if specs is not None else SPECS
        self._procs: dict[int, subprocess.Popen] = {}   # port → process
        self._last_used: dict[int, float] = {}          # port → monotonic
        self._lock = threading.Lock()
        self._monitor: threading.Thread | None = None

    def get(self, name: str) -> ModelSpec | None:
        return self.specs.get(name)

    # -- lifecycle -----------------------------------------------------

    def load(self, name: str, wait_sec: float = 90.0) -> None:
        """Start (or adopt) the backend process for `name` and block until
        its port answers. Serialized by the lock: only one model loads at
        a time."""
        spec = self._require(name)
        if spec.port is None:
            return  # in-process backend (onnx); nothing to spawn
        with self._lock:
            self._last_used[spec.port] = time.monotonic()
            proc = self._procs.get(spec.port)
            if proc and proc.poll() is None:
                return
            if _port_open(spec.port):
                return  # externally managed server already on the port
            self._spawn(spec)
        deadline = time.monotonic() + wait_sec
        while time.monotonic() < deadline:
            if _backend_ready(spec.port):
                self._last_used[spec.port] = time.monotonic()
                return
            proc = self._procs.get(spec.port)
            if proc and proc.poll() is not None:
                raise RuntimeError(
                    f"backend for {name} exited rc={proc.returncode}")
            time.sleep(0.5)
        raise TimeoutError(f"backend for {name} not ready after {wait_sec}s")

    def unload(self, name: str) -> None:
        spec = self._require(name)
        if spec.port is None:
            return
        with self._lock:
            proc = self._procs.pop(spec.port, None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    def is_loaded(self, name: str) -> bool:
        spec = self._require(name)
        if spec.port is None:
            return False
        proc = self._procs.get(spec.port)
        return (proc is not None and proc.poll() is None) or _port_open(spec.port)

    def loaded_models(self) -> list[str]:
        return [n for n in self.specs if self.is_loaded(n)]

    def touch(self, name: str) -> None:
        spec = self._require(name)
        if spec.port is not None:
            self._last_used[spec.port] = time.monotonic()

    # -- startup / monitor ----------------------------------------------

    def start_eager(self) -> None:
        """Load every load_on_start model; called once before uvicorn."""
        for name, spec in self.specs.items():
            if spec.load_on_start:
                try:
                    self.load(name)
                except (FileNotFoundError, RuntimeError, TimeoutError) as e:
                    # Degrade: the tool returns MODEL_NOT_LOADED until the
                    # backend is fixed; the MCP server itself stays up.
                    print(f"Warning: cannot load {name}: {e}", file=sys.stderr)
        if self._monitor is None:
            self._monitor = threading.Thread(
                target=self._idle_unload_loop, daemon=True)
            self._monitor.start()

    def _idle_unload_loop(self) -> None:
        lazy_ports = {s.port for s in self.specs.values()
                      if s.port is not None and not s.load_on_start}
        eager_ports = {s.port for s in self.specs.values()
                       if s.port is not None and s.load_on_start}
        lazy_ports -= eager_ports  # a shared port with an eager user stays up
        while True:
            time.sleep(5)
            now = time.monotonic()
            for port in lazy_ports:
                with self._lock:
                    proc = self._procs.get(port)
                    idle = now - self._last_used.get(port, now)
                    if proc and proc.poll() is None and idle > LAZY_UNLOAD_IDLE_SEC:
                        self._procs.pop(port, None)
                    else:
                        proc = None
                if proc:
                    proc.terminate()

    # -- internals -------------------------------------------------------

    def _require(self, name: str) -> ModelSpec:
        spec = self.specs.get(name)
        if spec is None:
            raise KeyError(f"Unknown model: {name}")
        return spec

    def _spawn(self, spec: ModelSpec) -> None:
        if not spec.path.exists():
            raise FileNotFoundError(f"model file missing: {spec.path}")
        binary = "whisper-server" if spec.backend == "whisper.cpp" else "llama-server"
        exe = (shutil.which(binary, path=str(RUNTIME_DIR / "bin"))
               or shutil.which(binary)
               or shutil.which(binary, path="/data/data/com.termux/files/usr/bin"))
        if exe is None:
            raise FileNotFoundError(f"{binary} not found on PATH")
        cmd = [exe, "-m", str(spec.path),
               "--host", "127.0.0.1", "--port", str(spec.port),
               *spec.server_args]
        env = dict(os.environ)
        env["LD_LIBRARY_PATH"] = str(RUNTIME_DIR / "lib") + (
            ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
        log = open(spec.path.parent / f"{binary}-{spec.port}.log", "ab")
        self._procs[spec.port] = subprocess.Popen(
            cmd, stdout=log, stderr=subprocess.STDOUT, env=env,
            stdin=subprocess.DEVNULL, start_new_session=True)
