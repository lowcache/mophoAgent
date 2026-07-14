# phoneAgentBuild ready to build (2026-07-14, commit 0db33c8)

Assessment + fix + split + branch setup complete. All on origin.

## Repo shape
- 3 branches aligned at 0db33c8: `main` (integration, laptop owns merges),
  `phone` (phases 0-7), `laptop` (phase 8 + design/DECISIONS).
- `relay/{to-laptop,to-phone,archive}/` — cross-agent dropbox, git-transported,
  branch-partitioned so commits don't collide. NOT .memory (phone must never
  write .memory; laptop forwards relay-worthy items to inbox).
- Phone product code lives in-repo at `~/mophoAgent/phone-agent/` on the
  `phone` branch; `~/phone-agent` is a symlink to it. Repo cloned to native
  Termux home; edited from proot via bind; run with native Termux python.

## phoneAgentBuild/ layout
- `DECISIONS.md` — authoritative D1-D10 (transport, agents, no-ssh, persistent
  servers, cpu-baseline, ingest tools, lock-only, no-preempt, offline ladder,
  termux/nix corrections).
- `design/` — 5 specs (tool schema, pipeline graph, trigger model, offline
  model, archived deepseek prompt).
- `phone/PHONE-ENV.md` + `phone/prompts/phase-0..7.md`.
- `laptop/phase-8-laptop-integration.md`.

## What was corrected (source docs had real defects)
- stdio-per-call transport → persistent FastMCP HTTP:8462 (models would reload
  every call otherwise).
- SSH everywhere in phase 8 (violated the design's own no-SSH constraint) →
  HTTP MCP + Ollama API; nix module bug (`imports` under `config=mkIf`);
  `iptables -F` "routing" placeholder removed.
- Missing ingest transfer entirely → added phone.ingest.list/fetch + laptop
  ingest-sync timer.
- QNN backend assumed available (it isn't in mainline llama.cpp / Termux) →
  CPU baseline, NPU stretch.
- termux-share-receive (nonexistent) → termux-url-opener spool; termux-location
  /-sensor flag fixes; termux-notification --id; blocklist regex; queue
  delivering/ dir + retry_count persistence bug; whisper-small 244M not 94M.

## Process notes
- Mechanical edits delegated to tether (Gemini 3.1 Pro). It over-applied on 4
  files (deleted whole tools/subsystems instead of editing) — those were
  rewritten by hand from context. Lesson: tether brief for destructive-looking
  edits needs "EDIT not REMOVE; preserve all sections" stated harder, or keep
  such files in-house.
