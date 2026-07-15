import socket
import sys
import uvicorn
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from mcp.server.fastmcp import FastMCP
from config.settings import TAILSCALE_IP, PORT, token_file_exists, get_token_from_file

# Create FastMCP instance
mcp = FastMCP("phone-mcp", stateless_http=True, json_response=True)

# Register tools from registry
from tool_registry import register_all
register_all(mcp)

@mcp.custom_route('/health', methods=['GET'])
async def health_check(request: Request):
    return JSONResponse({"status": "ok"})

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        
        auth = request.headers.get("Authorization")
        if not auth:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
            
        expected = get_token_from_file() # read from ~/.config/phone-agent/token
        if auth != f"Bearer {expected}":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
            
        return await call_next(request)

app = mcp.streamable_http_app()   # mounts the MCP endpoint at /mcp
app.add_middleware(BearerAuthMiddleware)

def resolve_bind_host(preferred: str) -> str:
    """Android assigns the Tailscale VPN address in a way userland cannot
    bind (EADDRNOTAVAIL), so fall back to 0.0.0.0 — the tailnet still
    reaches us and BearerAuthMiddleware gates everything but /health."""
    try:
        probe = socket.socket()
        probe.bind((preferred, PORT))
        probe.close()
        return preferred
    except OSError as e:
        print(f"Warning: cannot bind {preferred} ({e}); falling back to 0.0.0.0", file=sys.stderr)
        return "0.0.0.0"


if __name__ == "__main__":
    if not token_file_exists():
        print("Error: ~/.config/phone-agent/token missing. Generate with: openssl rand -hex 32 > ~/.config/phone-agent/token", file=sys.stderr)
        sys.exit(1)
    uvicorn.run(app, host=resolve_bind_host(TAILSCALE_IP), port=PORT)
