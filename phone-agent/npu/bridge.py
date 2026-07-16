"""Routes inference requests to the persistent backend servers (D4).

llama-server (chat + classify) on 127.0.0.1:8463, llama-server --embedding
on :8464, whisper-server on :8465, OCR in-process via onnxruntime. All
public entry points are async; blocking work runs in a thread.
"""

import asyncio
import json
import math
import time
import wave
from pathlib import Path

import httpx

from config.settings import AUDIO_MAX_SEC
from npu.models import ModelRegistry, ModelSpec


class InferenceError(Exception):
    """Tool-visible failure with a stable error code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class NPUBridge:
    def __init__(self, models: ModelRegistry):
        self.models = models
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))

    async def infer(self, model_name: str, input: dict) -> dict:
        model = self.models.get(model_name)
        if not model:
            raise InferenceError("MODEL_NOT_LOADED", f"Unknown model: {model_name}")
        if model.port is not None and not self.models.is_loaded(model_name):
            try:
                await asyncio.to_thread(self.models.load, model_name)
            except (FileNotFoundError, RuntimeError, TimeoutError) as e:
                raise InferenceError("MODEL_NOT_LOADED", str(e)) from e
        self.models.touch(model_name)

        started = time.monotonic()
        if model.kind == "whisper":
            result = await self._whisper_infer(model, input)
        elif model.kind == "ocr":
            result = await self._ocr_infer(model, input)
        elif model.kind == "embed":
            result = await self._embed_infer(model, input)
        elif model.kind == "classify":
            result = await self._classify_infer(model, input)
        elif model.kind == "llm":
            result = await self._llm_infer(model, input)
        else:
            raise InferenceError("MODEL_NOT_LOADED", f"No backend for kind {model.kind}")
        result.setdefault("processing_time_ms",
                          int((time.monotonic() - started) * 1000))
        return result

    # -- whisper ---------------------------------------------------------

    async def _whisper_infer(self, model: ModelSpec, input: dict) -> dict:
        audio_path = Path(input["audio_path"]).expanduser()
        if not audio_path.is_file():
            raise InferenceError("MODEL_NOT_LOADED", f"audio file missing: {audio_path}")
        try:
            with wave.open(str(audio_path), "rb") as w:
                duration = w.getnframes() / w.getframerate()
            if duration > AUDIO_MAX_SEC:
                raise InferenceError(
                    "AUDIO_TOO_LONG",
                    f"{duration:.0f}s exceeds cap of {AUDIO_MAX_SEC}s")
        except wave.Error:
            duration = None  # non-wav container; let whisper-server decide

        resp = await self._post_backend(
            model, f"http://127.0.0.1:{model.port}/inference",
            files={"file": (audio_path.name, audio_path.read_bytes(), "audio/wav")},
            data={"response_format": "verbose_json",
                  "temperature": str(input.get("temperature", 0.0)),
                  "language": input.get("language", "en")})
        body = resp.json()
        segments = [{"start_sec": float(s.get("start", 0.0)),
                     "end_sec": float(s.get("end", 0.0)),
                     "text": s.get("text", "").strip()}
                    for s in body.get("segments", [])]
        return {
            "segments": segments,
            "full_text": body.get("text", "").strip(),
            "model_used": model.name,
        }

    # -- ocr ---------------------------------------------------------------

    async def _ocr_infer(self, model: ModelSpec, input: dict) -> dict:
        try:
            from npu import ocr_engine
        except ImportError as e:
            raise InferenceError(
                "MODEL_NOT_LOADED",
                f"OCR backend unavailable (onnxruntime not installed): {e}") from e
        image_path = Path(input["image_path"]).expanduser()
        if not image_path.is_file():
            raise InferenceError("MODEL_NOT_LOADED", f"image file missing: {image_path}")
        return await asyncio.to_thread(
            ocr_engine.run, model.path, image_path,
            input.get("languages", ["en"]))

    # -- embed ---------------------------------------------------------------

    async def _embed_infer(self, model: ModelSpec, input: dict) -> dict:
        resp = await self._post_backend(
            model, f"http://127.0.0.1:{model.port}/v1/embeddings",
            json={"input": input["text"], "model": model.name})
        vec = resp.json()["data"][0]["embedding"]
        if input.get("normalize", True):
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            vec = [x / norm for x in vec]
        return {"embedding": vec, "dimensions": len(vec)}

    # -- classify ---------------------------------------------------------

    async def _classify_infer(self, model: ModelSpec, input: dict) -> dict:
        labels = input["labels"]
        # GBNF grammar constrains output to exactly one label; logprobs on
        # the first token give per-label scores.
        grammar = "root ::= " + " | ".join(f'"{label}"' for label in labels)
        resp = await self._post_backend(
            model, f"http://127.0.0.1:{model.port}/v1/chat/completions",
            json={
                "model": model.name,
                "messages": [
                    {"role": "system",
                     "content": "Classify the user text into exactly one label: "
                                + ", ".join(labels) + ". Reply with the label only."},
                    {"role": "user", "content": input["text"]},
                ],
                "temperature": 0.0,
                "max_tokens": 8,
                "grammar": grammar,
                "logprobs": True,
                "top_logprobs": 20,
            })
        body = resp.json()
        choice = body["choices"][0]
        label = choice["message"]["content"].strip()
        scores = self._label_scores(choice, labels)
        confidence = scores.get(label, 0.0)
        return {"label": label, "confidence": confidence, "scores": scores}

    @staticmethod
    def _label_scores(choice: dict, labels: list[str]) -> dict[str, float]:
        """Per-label probability from the first generated token's top
        logprobs. Labels whose first token is absent from the list get 0."""
        try:
            top = choice["logprobs"]["content"][0]["top_logprobs"]
        except (KeyError, IndexError, TypeError):
            picked = choice["message"]["content"].strip()
            return {lbl: (1.0 if lbl == picked else 0.0) for lbl in labels}
        token_p = {t["token"]: math.exp(t["logprob"]) for t in top}
        raw = {}
        for label in labels:
            raw[label] = max((p for tok, p in token_p.items()
                              if label.startswith(tok) or tok.strip() == label),
                             default=0.0)
        total = sum(raw.values()) or 1.0
        return {lbl: p / total for lbl, p in raw.items()}

    # -- llm -------------------------------------------------------------

    async def _llm_infer(self, model: ModelSpec, input: dict) -> dict:
        payload = {
            "model": model.name,
            "messages": [{"role": "user", "content": input["prompt"]}],
            "max_tokens": input.get("max_tokens", 256),
            "temperature": input.get("temperature", 0.7),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        started = time.monotonic()
        ttft_ms = None
        chunks: list[str] = []
        tokens_generated = 0
        url = f"http://127.0.0.1:{model.port}/v1/chat/completions"
        try:
            async with self.client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    event = json.loads(line[6:])
                    usage = event.get("usage")
                    if usage:
                        tokens_generated = usage.get("completion_tokens", 0)
                    for c in event.get("choices", []):
                        delta = c.get("delta", {}).get("content")
                        if delta:
                            if ttft_ms is None:
                                ttft_ms = int((time.monotonic() - started) * 1000)
                            chunks.append(delta)
        except httpx.HTTPError as e:
            raise InferenceError("NPU_BUSY", f"llama-server request failed: {e}") from e
        elapsed = time.monotonic() - started
        tokens_generated = tokens_generated or len(chunks)
        gen_sec = max(elapsed - (ttft_ms or 0) / 1000, 1e-3)
        return {
            "response": "".join(chunks),
            "tokens_generated": tokens_generated,
            "ttft_ms": ttft_ms if ttft_ms is not None else int(elapsed * 1000),
            "tokens_per_sec": round(tokens_generated / gen_sec, 1),
            "model_used": model.name,
            "routed_to_laptop": False,
        }

    # -- shared ------------------------------------------------------------

    async def _post_backend(self, model: ModelSpec, url: str, **kwargs) -> httpx.Response:
        try:
            resp = await self.client.post(url, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as e:
            raise InferenceError("NPU_BUSY", f"backend for {model.name} failed: {e}") from e
