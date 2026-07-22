# mophoAgent

**A phone that acts as a local-first sensory, compute, and control peripheral for a laptop-side AI agent.**

mophoAgent runs a persistent [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server *on an Android phone* (Galaxy S26 Ultra, under Termux). It exposes the phone's hardware and on-device intelligence — microphone, cameras, screen, radios, motion/environment sensors, system control, and **local AI inference** — as MCP tools that a laptop-side Claude agent can call over a private [Tailscale](https://tailscale.com) network. No cloud round-trips for inference; no SSH anywhere in the phone↔laptop path.

The endgame is a phone that behaves like an always-available extension of the laptop agent: it senses the environment, runs models on-device, and — in later phases — talks back by voice, keeps working while the laptop is asleep, and queues everything for delivery when the laptop is unreachable.

## What it does today

A single bearer-token-authenticated MCP endpoint (`Streamable HTTP`, port `8462`, bound to the Tailscale IP) serving **27 tools** across seven families:

| Family | Tools | What they do |
|---|---|---|
| **system** | `ping`, `state`, `rish`, `termux_exec`, `free_ram`, `notify` | Health/liveness, shell execution (Shizuku shell-uid via `rish` and unprivileged Termux uid), RAM reclamation, notifications. Every command is screened against a fail-closed regex blocklist. |
| **npu** | `transcribe`, `ocr`, `embed`, `classify`, `llm_infer` | Fully **on-device** inference — Whisper (speech→text), PP-OCR (image→text), MiniLM embeddings, grammar-constrained classification, and small-LLM generation. CPU baseline with an NPU stretch path. |
| **capture** | `audio`, `image`, `screenshot`, `share` | Mic capture with voice-activity trimming, camera JPEG, screen PNG, and an Android share-sheet intake hook. |
| **pipeline** | `run` | Composable processing pipelines (transcript, OCR, share-extract, summarize, embed) over captured/ingested content. |
| **sensor** | `read_imu`, `read_modem`, `read_gps`, `read_light`, `read_proximity` | Motion (with on-device activity inference — *stationary / walking / …*), cellular+Wi-Fi state, location + geofencing, ambient light, and proximity. |
| **voice** | `ask`, `start`, `stop` | One-shot voice cycle — (capture →) transcribe → route (local model vs laptop Ollama) → TTS. The wake-word listening session is experimental/opt-in. |
| **queue** | `sync`, `deliver`, `clear_failed` | Offline autonomy — a durable on-disk priority queue that buffers outbound items when the laptop drops off the tailnet, with retry, ack, and manual retry/discard. The laptop pulls; the phone never pushes. |

## Architecture

- **Transport (D1/D3):** MCP Streamable HTTP over Tailscale, bearer-token auth. No stdio, no SSH.
- **Persistent runtimes (D4):** inference backends (whisper-server, llama-server) stay resident behind a serialized async priority queue rather than spawning per call. Thread-pinned for the phone's big.LITTLE cores.
- **On-device, bionic-aware:** where Android's `bionic` libc blocks common wheels, logic is re-implemented in pure-Python stdlib (e.g. the IMU activity classifier, VAD, geofence math) so nothing depends on a fragile native `dlopen`.
- **Supervision:** runs as a `runit`/termux-services service, auto-started on boot, with an external watchdog that re-probes `/health` and recovers the service.
- **Two-agent build:** a phone-side agent (Claude Code in Termux) owns the product code; a laptop-side agent verifies and signs off each phase. They coordinate through file-based `relay/`.

## Build roadmap

Eight phases; each is self-contained, testable, and its own commit (see [`phoneAgentBuild/build-plan.md`](phoneAgentBuild/build-plan.md) and [`DECISIONS.md`](phoneAgentBuild/DECISIONS.md)).

| Phase | Scope | Status |
|---|---|---|
| 0 | MCP server skeleton | ✅ closed |
| 1 | On-device inference (CPU baseline, NPU stretch) | ✅ closed |
| 2 | Capture tools | ✅ closed |
| 3 | Processing pipelines | ✅ closed |
| 4 | Sensor tools | ✅ closed |
| 5 | System tools | ✅ closed (laptop signed off; deployed live) |
| 5.5 | Location-primitive prelude (fresh-fix GPS, accuracy gate, distance) | ✅ closed (additive diff reviewed sound) |
| 6 | Voice AI + offline autonomy queue | 🟡 built + offline-verified (27 tools); operator live-gate + laptop sign-off pending |
| 7 | Subconscious scheduler (runs tasks while the laptop sleeps) | ⬜ planned |

**Where it's heading:** Phase 6 adds an interactive voice session (wake word → local transcription → local-model-or-laptop routing → TTS) and an offline queue that buffers everything when the laptop drops off the tailnet. Phase 7 adds an event-driven scheduler — a "subconscious" that fires time- and event-based tasks on the phone and delivers results back when the laptop wakes. Location awareness is evolving toward a **dynamic geofence** where "home" is derived from wherever the laptop is currently operational (built for a user with no fixed location), rather than a hardcoded coordinate.

## Repository layout

```
phone-agent/         The MCP server (product code): main.py, tool_registry.py,
                     tools/, npu/, sensors/, pipeline/, vad/, scripts/, config/
phoneAgentBuild/     Build plan, per-phase prompts, design docs, decisions
relay/               File-based coordination between the phone- and laptop-side agents
```

> **Note:** the server must run **natively** in Termux (not the proot dev shell), where the hardware CLIs, on-device model runtimes, and Tailscale binding are available. Runtime and boundary details are in [`phone-agent/README.md`](phone-agent/README.md) and `phoneAgentBuild/phone/PHONE-ENV.md`.
