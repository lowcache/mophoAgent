---
type: mistakes
project: mophoAgent
last_updated: 2026-07-14
status: active
---

# Mistake Audit Log (append-only)

_No mistakes recorded yet._

### 2026-07-14 — Phase 8 SSH architecture violation
Symptom: Phase 8 prompt used SSH everywhere despite D3 constraint "MCP is the only interface, no SSH". Root cause: Original phase-8 brief did not enforce design constraints; SSH assumed as obvious transport. Prevention: D3 now authoritative in DECISIONS.md. Curator reviews DECISIONS.md against prompts before phone clone to flag violations early.

### 2026-07-14 — Phase 8 stdio server per-poll spawning
Symptom: Phase 8 template spawned fresh stdio MCP server on every 5-second poll loop, causing model reload overhead on every inference call. Root cause: Confusion between transport-layer persistence (D1, D4) and polling interval. Prevention: D1/D4 now explicit; Phase 0 skeleton enforces persistent HTTP server pattern from start.

### 2026-07-14 — Nix module syntax: imports inside mkIf config
Symptom: `imports = [...]` directive nested inside `config = mkIf condition`. Root cause: Home Manager module syntax (top-level `imports`) conflated with NixOS module syntax (conditional `config` block does not accept `imports`). Prevention: Phase 8 prompt now specifies "NixOS module, not home-manager" and provides correct skeleton.

### 2026-07-14 — home-manager systemd in NixOS module
Symptom: systemd service unit written using `config.systemd.user.*` (home-manager) inside NixOS module. Root cause: Copy-paste from home-manager docs without context. Prevention: Phase 8 prompt now provides exact systemd.services skeleton for NixOS (system-wide, not user).

### 2026-07-14 — Placeholder iptables rules
Symptom: `iptables -F && iptables -P ACCEPT` present as direct-routing fallback; destructive and ambiguous. Root cause: Placeholder during architecture drafting. Prevention: Removed; D3 and D9 now specify offline detection via curl/ICMP, not routing manipulation.
