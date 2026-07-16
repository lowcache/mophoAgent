---
type: state-update
project: mophoAgent
from: claude-laptop
created: 2026-07-16T12:36:00Z
---

# Phase-1 sign-off CLOSED — tailnet /health verified laptop→phone

The final Phase-1 acceptance item (cross-tailnet reachability from the laptop)
now passes. Verified 2026-07-16 from volnix over the mesh:
- `GET http://100.101.229.9:8462/health` → 200 `{"status":"ok"}` (cellular RTT ~357ms)
- `GET /mcp` bad bearer → 401 (auth boundary holds over the tailnet)

Sign-off note relay/to-phone/20260716-0751-phase1-signoff.md flipped to
`status: closed`. Phase 2 unblocked.

## How volnix joined the tailnet (non-obvious; needed for phase 6/8)
Tailscale on volnix lives in its OWN `tailscale` microvm (separate from the Tor
`net-gate` VM), `autostart = false`, and had never been brought up. Changes
made in ~/.nix-config/nixos/vms.nix (applied via `make switch`):
- Guest: `services.tailscale.authKeyFile = "/var/lib/tailscale/authkey"` (key
  placed at host /persist/var/lib/tailscale-vm/authkey, virtiofs-shared) +
  `extraUpFlags = [ "--advertise-exit-node" ]`. Declarative auto-join, no guest
  console/login (the guest has no getty autologin — console path was a dead end).
- Guest: `networking.nat` SNAT `192.168.101.0/24 → tailscale0` so host-originated
  traffic gets the guest's tailnet source.
- Host: host route `100.64.0.0/10 via 192.168.101.2`, and — the actual blocker —
  `IPMasquerade = "both"` on the `11-tailscale-tap` host network so the guest
  had real internet to authenticate (the tap only had IPv4Forwarding, no SNAT;
  same idiom the android VM tap already used). Without it tailscaled could not
  reach the coordination server → no tailnet route → ICMP redirects.
- Debugging red herring: the mesh path was fine once the guest authed; the
  final timeout was just the phone MCP server being down (died since the gate;
  relaunched). EADDRINUSE on relaunch = a server already bound, not a failure.

Those vms.nix edits are currently UNCOMMITTED in ~/.nix-config (separate repo).

## Still-open follow-up (already tracked)
Phone MCP server is a hand-run foreground process, not a managed service — it
self-terminated between gate and this check. Reinforces the existing
"codify bootstrap.sh/launcher + persistent process" todo.
