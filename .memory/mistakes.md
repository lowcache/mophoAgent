---
type: mistakes
project: mophoAgent
last_updated: 2026-07-17
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

### 2026-07-17 — Process scan self-matching strike three
Symptom: Native process scan via `/proc/*/cmdline` case-glob for `*phone-agent*main.py*` matched the scan command's own shell and `head -1` handed it to `kill -TERM`, killing the scanning shell and misreading survivors as respawned pids. Third recurrence of this class bug (same as banned `pkill -f`). Root cause: Substring pattern in scan filter matched the scanning command's own cmdline, making the scan self-referential. Prevention: Any self-written process scan must exclude `$$` and ancestor pids OR match on `/proc/*/comm` + exact cwd/exe, never a substring that appears in the scan command itself. Prefer `/proc/*/comm` exact match + working directory verification.

### 2026-07-17 — Phase 2 runbook prescribed pip native-lib dependency for bionic venv
Symptom: Original phase-2 runbook instructed `pkg install libsndfile` + `uv pip install soundfile`. Operator encountered hardlink errors; inspection revealed soundfile ships a manylinux wheel with bundled glibc libsndfile — would fail bionic dlopen even if installation succeeded (same class as [[project-uv-dlopen-poisoned-inodes]]). Root cause: Runbook author did not account for pip wheel glibc-native-lib incompatibility with Android bionic. Prevention: Runbooks for native Termux venv must vet all pip dependencies for binary wheels; avoid any that bundle non-EABI native libs. For audio I/O, stdlib `wave` module suffices when ffmpeg guarantees output encoding (16-bit mono PCM).
