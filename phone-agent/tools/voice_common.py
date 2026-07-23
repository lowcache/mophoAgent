"""Shared wiring for the Phase 6 voice tools (not a tool module — tool_registry
does not import it). Adapts the NPU backends to the injected-dependency shapes
that QueryRouter / VoiceSession expect, and builds the process-wide singletons.
"""

import json
import shlex

from config.settings import CONFIG_PATH
from npu import get_queue as _npu_queue
from npu.bridge import InferenceError
from npu.queue import PRIORITY_INTERACTIVE, PRIORITY_SCHEDULED
from tools.sys_common import run_shell, SystemToolError
from voice.tts import TTSEngine
from voice.router import QueryRouter
from voice.session import VoiceSession
from offline.detector import DisconnectionDetector

_LLM_MODEL = "qwen2.5-1.5b-q4"
_CLASSIFY_MODEL = "qwen2.5-1.5b-q4-classify"
_WHISPER_MODEL = "whisper-small.en-q8_0"


def _laptop_config() -> dict:
    """Laptop identity for routing/detection, overridable via config.json
    (keys: laptop_host, laptop_ts_ip, ollama_model). Defaults to the volnix
    tailnet IP so numeric curl+ping work before magic-DNS is configured; the
    operator SHOULD set laptop_host to the magic-DNS name
    (volnix.<tailnet>.ts.net) per the no-hardcoded-identity design note."""
    defaults = {"laptop_host": "100.101.229.9",
                "laptop_ts_ip": "100.101.229.9",
                "ollama_model": "llama3.1"}
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        cfg = {}
    for k in defaults:
        if isinstance(cfg.get(k), str):
            defaults[k] = cfg[k]
    return defaults


class _NpuLocalModel:
    async def infer(self, prompt: str) -> str:
        try:
            res = await _npu_queue().submit(
                _LLM_MODEL,
                {"prompt": prompt, "max_tokens": 256, "temperature": 0.7},
                priority=PRIORITY_INTERACTIVE)
        except InferenceError as e:
            return f"[local model unavailable: {e.code}]"
        return res.get("response", "") if isinstance(res, dict) else str(res)


class _NpuClassifier:
    async def classify(self, text: str, labels: list[str]) -> dict:
        # May raise InferenceError; QueryRouter._classify catches and falls
        # back to its keyword heuristic, so no local guard is needed here.
        return await _npu_queue().submit(
            _CLASSIFY_MODEL, {"text": text, "labels": labels},
            priority=PRIORITY_INTERACTIVE)


class _NpuWhisper:
    async def transcribe(self, audio_path: str) -> str:
        res = await _npu_queue().submit(
            _WHISPER_MODEL,
            {"audio_path": audio_path, "language": "en", "temperature": 0.0},
            priority=PRIORITY_SCHEDULED)
        if isinstance(res, dict):
            if res.get("error"):
                raise RuntimeError(res.get("message", "transcription failed"))
            return res.get("full_text", "")
        return str(res)


async def _capture(max_duration_sec: int = 15) -> dict:
    from tools.capture_audio import record_and_trim
    return await record_and_trim(max_duration_sec=max_duration_sec)


async def notify(title: str, body: str) -> None:
    """Best-effort status-bar notification for internal events (session reset,
    reconnect sync). Goes through the shared blocklist via run_shell; failures
    are swallowed so a notification problem never breaks the caller."""
    try:
        await run_shell(f"termux-notification --title {shlex.quote(title)} "
                        f"--content {shlex.quote(body)}")
    except SystemToolError:
        pass


_router: QueryRouter | None = None
_session: VoiceSession | None = None
_detector: DisconnectionDetector | None = None


def get_detector() -> DisconnectionDetector:
    """Process-wide D9 ladder. Shared so the voice router and the Phase-7
    scheduler agree on whether the laptop is reachable instead of probing it
    twice with independently drifting state."""
    global _detector
    if _detector is None:
        cfg = _laptop_config()
        _detector = DisconnectionDetector(cfg["laptop_host"], cfg["laptop_ts_ip"])
    return _detector


def get_router() -> QueryRouter:
    global _router
    if _router is None:
        cfg = _laptop_config()
        detector = get_detector()
        _router = QueryRouter(
            _NpuLocalModel(), detector, classifier=_NpuClassifier(),
            ollama_url=f"http://{cfg['laptop_host']}:11434/api/chat",
            ollama_model=cfg["ollama_model"])
    return _router


def get_session() -> VoiceSession:
    global _session
    if _session is None:
        # wake_word=None: the detector is a typed stub (voice/wake_word.py);
        # start() returns WAKE_WORD_UNAVAILABLE until a model is wired.
        _session = VoiceSession(get_router(), TTSEngine(), whisper=_NpuWhisper(),
                                capture=_capture, wake_word=None, notify=notify)
    return _session
