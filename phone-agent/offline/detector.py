import asyncio
import subprocess
import httpx

POLL_INTERVAL_SEC = {
    "ONLINE": 60,
    "DEGRADED": 60,
    "LAPTOP_UNREACHABLE": 60,
    "NO_INTERNET": 120
}

class DisconnectionDetector:
    """
    Detects disconnection states between the phone, laptop, and the wider internet.
    States: ONLINE, DEGRADED, LAPTOP_UNREACHABLE, NO_INTERNET.
    """

    def __init__(self, laptop_host: str, laptop_ts_ip: str, ollama_port: int = 11434):
        self.laptop_host = laptop_host
        self.laptop_ts_ip = laptop_ts_ip
        self.ollama_port = ollama_port
        self.state = "ONLINE"

    async def _curl_ok(self, url: str, timeout: float = 2.0) -> bool:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)
                return resp.status_code < 400
        except httpx.RequestError:
            return False

    async def _ping_ok(self, host: str, count: int = 1, timeout: int = 2) -> bool:
        cmd = ["ping", "-c", str(count), "-W", str(timeout), host]
        try:
            proc = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, timeout=timeout + 2
            )
            return proc.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    async def check_connection(self) -> str:
        url = f"http://{self.laptop_host}:{self.ollama_port}/api/version"
        if await self._curl_ok(url):
            self.state = "ONLINE"
        elif await self._ping_ok(self.laptop_ts_ip):
            self.state = "DEGRADED"
        elif await self._ping_ok("1.1.1.1"):
            self.state = "LAPTOP_UNREACHABLE"
        else:
            self.state = "NO_INTERNET"
        return self.state

    async def is_online(self) -> bool:
        return (await self.check_connection()) == "ONLINE"

    def poll_interval(self) -> int:
        return POLL_INTERVAL_SEC[self.state]
