import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.router import QueryRouter

class StubModel:
    async def infer(self, prompt: str) -> str:
        return f"local:{prompt}"

class StubDetector:
    def __init__(self, online: bool):
        self.online = online

    async def is_online(self) -> bool:
        return self.online

class StubClassifier:
    def __init__(self, label: str):
        self.label = label

    async def classify(self, text: str, labels: list[str]) -> dict:
        return {"label": self.label, "confidence": 1.0}

class StubRouter(QueryRouter):
    async def _query_ollama(self, transcript: str) -> str:
        return f"laptop:{transcript}"

def test_simple_online():
    async def run():
        router = StubRouter(StubModel(), StubDetector(True), StubClassifier("simple"))
        resp, src = await router.route("test")
        assert src == "local"
        assert resp.startswith("local:")
    asyncio.run(run())

def test_complex_online():
    async def run():
        router = StubRouter(StubModel(), StubDetector(True), StubClassifier("complex"))
        resp, src = await router.route("test")
        assert src == "laptop"
    asyncio.run(run())

def test_complex_offline():
    async def run():
        router = StubRouter(StubModel(), StubDetector(False), StubClassifier("complex"))
        resp, src = await router.route("test")
        assert src == "local_offline"
        assert resp.startswith("[offline")
    asyncio.run(run())

def test_force_local():
    async def run():
        router = StubRouter(StubModel(), StubDetector(True), StubClassifier("complex"))
        router.force_local = True
        resp, src = await router.route("test")
        assert src == "local_offline"
    asyncio.run(run())

def test_heuristic():
    async def run():
        router = StubRouter(StubModel(), StubDetector(False), None)

        resp, src = await router.route("please debug this code")
        assert src == "local_offline"

        resp, src = await router.route("hi")
        assert src == "local"
    asyncio.run(run())

def test_system_handler():
    async def run():
        async def sys_handler(t):
            return "SYS"
        router = StubRouter(StubModel(), StubDetector(True), StubClassifier("system"), system_handler=sys_handler)
        resp, src = await router.route("test")
        assert src == "local"
        assert resp == "SYS"
    asyncio.run(run())

if __name__ == "__main__":
    tests = [
        test_simple_online,
        test_complex_online,
        test_complex_offline,
        test_force_local,
        test_heuristic,
        test_system_handler
    ]

    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")

    print(f"{passed}/{len(tests)} PASS")
    if passed < len(tests):
        sys.exit(1)
