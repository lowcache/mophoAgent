# phoneAgentBuild assessment + restructure (2026-07-14)

## State
- `phoneAgentBuild/` restructured: `design/` (specs: tool schema, pipeline
  graph, trigger model, offline model, archived deepseek prompt), `phone/`
  (PHONE-ENV.md + prompts phase 0–7, built by Claude Code in Termux/proot),
  `laptop/` (phase 8, built by laptop Claude Code), `DECISIONS.md`
  (authoritative D1–D10), `build-plan.md`.
- Mechanical edits to all prompts delegated via tether (task
  `phoneagent-prompt-edits`), per-file spec in the brief; laptop agent
  verifies afterwards.

## Decisions (full text in phoneAgentBuild/DECISIONS.md)
- D1 Transport = MCP Streamable HTTP (FastMCP+uvicorn, phone TS-IP:8462,
  bearer token). stdio rejected: server must be persistent.
- D2 Phone built by Claude Code (Termux proot); server runs native Termux;
  code `~/phone-agent`, config `~/.config/phone-agent`.
- D3 No SSH phone↔laptop; phone→laptop only via Ollama HTTP API.
- D4 Persistent llama-server/whisper-server, no per-call CLI spawns.
- D5 CPU baseline, NPU stretch (no QNN in mainline llama.cpp; QNN SDK not
  in Termux).
- D6 New tools phone.ingest.list/fetch + laptop ingest-sync timer (the
  staged-file transfer was missing entirely from the original plan).
- D7 Proximity = lock-only (programmatic unlock rejected).
- D8 No NPU suspend/resume preemption (fiction); cancel+requeue instead.
- D9 Offline detection ladder: curl Ollama → ICMP laptop → ICMP 1.1.1.1
  (no tailscale CLI on Android).
- D10 Bag of factual fixes: termux-share-receive doesn't exist
  (termux-url-opener spool instead), termux-location/-sensor flag fixes,
  termux-notification needs --id, blocklist→regex, queue delivering/ dir +
  retry_count persistence bug, whisper-small is 244M not 94M, etc.

## Mistakes found in source docs (for mistakes.md)
- Phase 8 used SSH everywhere despite the design constraint "MCP is the
  only interface, no SSH" — and spawned a fresh stdio server per poll (5s
  interval), which would reload models every call.
- Nix module bug: `imports` inside `config = mkIf ...` (invalid);
  home-manager systemd syntax mixed into a NixOS module.
- `iptables -F && iptables -P ACCEPT` as "direct routing" — destructive
  placeholder, removed.
