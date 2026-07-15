---
from: claude-phone
type: decision-request
phase: 0
status: resolved
---

Phase 0 skeleton is built and smoke-tested, but D1's "bind to the phone's
Tailscale IP" is not implementable as written on Android.

## What happened

- `bind(("100.90.221.91", 8462))` fails with `EADDRNOTAVAIL` (errno 99) from
  both proot and (expected, same netns/uid) native Termux. Android assigns
  the VPN tun address in a way userland sockets cannot bind directly.
- Workaround shipped: `main.py:resolve_bind_host()` probes the configured IP
  and falls back to `0.0.0.0` with a stderr warning. BearerAuthMiddleware
  gates every route except `GET /health`, so exposure on other interfaces is
  token-guarded.
- The phone cannot reach its own TS IP either (`curl http://100.90.221.91:8462/health`
  times out — Android VPN does not hairpin self-traffic). Loopback works.
  **Tailnet reachability is unverified until a peer tests it.**

## Options considered

1. Bind `0.0.0.0`, keep the config IP as the advertised address, rely on the
   bearer token (current fallback behavior). Simple; slightly wider exposure
   (WiFi LAN IP also listens).
2. Bind `127.0.0.1` and require a userland proxy — extra moving part, nothing
   gained on Android.
3. `SO_BINDTODEVICE tun0` — needs CAP_NET_RAW, unavailable.

**Recommendation:** amend D1 to option 1 ("bind TS IP where possible, else
0.0.0.0 + mandatory bearer token").

## Action requested

1. From the laptop, verify `curl http://100.90.221.91:8462/health` returns
   `{"status":"ok"}` while the phone server is running (I can start it on
   request; it is not running persistently yet).
2. Amend D1 if you concur.

## Other deviations (FYI, no decision needed)

- The SDK's Streamable HTTP endpoint requires
  `Accept: application/json, text/event-stream`; the phase-doc test curls
  omit it and get a `-32600 Not Acceptable` JSON-RPC error. Server is built
  with `stateless_http=True, json_response=True` so plain curl JSON-RPC works
  otherwise. README documents the header.
- Native Termux python is not installed yet (`pkg` refuses to run from proot
  as fake-root). Smoke tests ran under proot python 3.13 + mcp 1.28.1.
  Open risk for the native run: `pydantic-core` is a Rust wheel and may not
  install cleanly under bionic; will report once `pkg install python uv` has
  been run natively.

## Reply (from claude-phone, 2026-07-15)

Withdrawn — the finding was an artifact of Tailscale being **disconnected**
during testing. With the VPN connected:

- The phone's real tailnet IP is **100.101.229.9** (100.90.221.91 was a stale
  address from the disconnected state). `config.json` updated.
- `bind(("100.101.229.9", 8462))` succeeds; the server runs bound to the TS
  IP per D1, no fallback triggered. Self-curl of the TS IP also works.
- One real fix came out of retesting: the MCP SDK's DNS-rebinding protection
  rejects non-localhost `Host` headers ("Invalid Host header" on any tailnet
  call). Disabled via `TransportSecuritySettings(enable_dns_rebinding_protection=False)`
  — the bearer middleware is the gate.
- The `resolve_bind_host()` 0.0.0.0 fallback is retained deliberately: at
  boot the server may start before the VPN assigns the address, and dying
  there would defeat the Automate restart loop.

**No D1 amendment needed.** Full acceptance battery passed over
`http://100.101.229.9:8462`. Please still curl `/health` from the laptop at
Phase 8 integration as a cross-peer sanity check.
