import httpx

class QueryRouter:
    """
    Routes voice queries to appropriate models based on network availability and complexity.
    If network or remote model errors occur (e.g. timeout), it automatically falls back to local.
    """

    def __init__(
        self,
        local_model,
        detector,
        classifier=None,
        ollama_url: str = "http://volnix.tailnet.ts.net:11434/api/chat",
        ollama_model: str = "llama3.1",
        system_handler=None,
    ):
        self.local_model = local_model
        self.detector = detector
        self.classifier = classifier
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.system_handler = system_handler
        self.force_local = False

    async def route(self, transcript: str) -> tuple[str, str]:
        label = await self._classify(transcript)

        if label == "system" and self.system_handler:
            return (await self.system_handler(transcript), "local")

        online = (not self.force_local) and await self.detector.is_online()

        if label == "complex" and online:
            try:
                return (await self._query_ollama(transcript), "laptop")
            except Exception:
                pass

        resp = await self.local_model.infer(transcript)
        if label == "complex":
            return (f"[offline, answered by phone model]\n{resp}", "local_offline")
        return (resp, "local")

    async def _classify(self, transcript: str) -> str:
        valid_labels = ["simple", "complex", "system"]
        if self.classifier is not None:
            try:
                result = await self.classifier.classify(transcript, valid_labels)
                if isinstance(result, dict) and "label" in result and result["label"] in valid_labels:
                    return result["label"]
            except Exception:
                pass
        return self._heuristic(transcript)

    def _heuristic(self, t: str) -> str:
        lc = t.lower()
        if any(kw in lc for kw in ("lock", "status", "battery", "notify")):
            return "system"
        if any(kw in lc for kw in ("code", "build", "why does", "debug", "review", "explain")):
            return "complex"
        if any(kw in lc for kw in ("what is", "who is", "hello", "hi")) or len(t) < 50:
            return "simple"
        return "simple"

    async def _query_ollama(self, transcript: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.ollama_url,
                json={
                    "model": self.ollama_model,
                    "messages": [{"role": "user", "content": transcript}],
                    "stream": False,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
