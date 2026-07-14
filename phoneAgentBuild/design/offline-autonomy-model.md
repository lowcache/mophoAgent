# Offline Autonomy — Phone Agent When Laptop Is Unreachable

## Problem

The MCP mesh between phone and laptop depends on Tailscale. Tailscale can be down (network failure), the laptop can be asleep (Tailscale times out), or the phone can have no internet (airplane mode, tunnel, remote area). The phone agent must function autonomously in all three cases.

## Local-Only Mode

**Detection:** Ladder per D9: curl Ollama /api/version fails → ICMP laptop fails → ICMP 1.1.1.1 fails.

**Exit:** Ladder detection moves up to ONLINE → re-establish MCP mesh, sync queue, exit local-only.

### Constraints in Local-Only Mode

| Resource | Available? | Notes |
|---|---|---|
| NPU inference | Yes | All local models loaded |
| Capture (mic/camera/sensor) | Yes | No network dependency |
| Share sheet receive | Yes | Local IPC |
| Local LLM (1-3B) | Yes | Runs on NPU |
| Ollama (full models) | No | Laptop unreachable |
| Web fetch for URL extraction | Maybe | If phone has separate internet (cellular data, even if Tailscale VPN is down) |
| Git push | No | phone holds no auth keys (guardrail) |

### Behavior Changes

1. **Voice AI** → All queries answered by local NPU 1-3B model. Responses are faster (no network latency) but less capable. The phone agent inserts `[offline response]` prefix to indicate the response came from the small model. Full Ollama responses are queued for delivery when mesh reconnects.

2. **NPU Ingest** → All capture + processing runs normally. Staged files accumulate in `~/ingest/staged/`. No change needed — ingest doesn't depend on the laptop.

3. **Subconscious Scheduler** → Workflows that require the laptop (flake update triggers, Ollama model preloading, make trash) are skipped. Workflows that the phone can execute independently (local file housekeeping, sensor monitoring, NPU model health check) still run.

---

## Queue Model

When the laptop is unreachable, the phone agent queues all results intended for laptop consumption (Voice AI queries that were routed to Ollama, cumulative ingest batch manifests, schedule results, sensor event summaries).

### Queue Structure

```
~/ingest/queue/
├── pending/           # items waiting for delivery
│   ├── 20260714_150322_voice_query_a3f2c.json
│   └── 20260714_151200_ingest_batch_manifest_b4d9e.json
├── delivering/        # items currently being delivered (move to failed on error)
│   └── ...
├── delivered/         # items successfully delivered to laptop
│   └── ...
└── failed/            # items that failed delivery after max retries
    └── ...
```

### Queue Item

```json
{
  "id": "voice_query_a3f2c",
  "type": "voice_query",
  "created_at": "2026-07-14T15:03:22.000-05:00",
  "source": {
    "pipeline": "voice_ai",
    "input": "~/ingest/audio/20260714_150322_raw.wav",
    "transcript": "what's the status of the net-gate build"
  },
  "laptop_response": null,
  "phone_response": "The phone is offline. I can't check the build status until the laptop reconnects.",
  "status": "pending",
  "retry_count": 0,
  "max_retries": 5,
  "priority": "normal"
}
```

### Delivery Protocol

1. Laptop reconnects to MCP mesh.
2. Phone agent calls `phone.queue.sync()` — new MCP tool.
3. Laptop agent (Claude Code) calls `phone.queue.deliver()` — another MCP tool.
4. Items are delivered in priority order: `high` → `normal` → `low`.
5. Within same priority: oldest first.
6. Each item is sent as a JSON payload over the MCP `tools/call` response.
7. Laptop agent acknowledges receipt. Phone moves item from `pending` → `delivered`.
8. If ack not received within 10s, item stays in `pending` with incremented `retry_count` and the item is moved back from delivering/ to pending/ with retry_count persisted to the JSON file.

### Conflict Resolution

**What happens if an ingest pipeline result was already manually processed on the laptop while the phone was offline?**

The laptop agent deduplicates by `source_file_hash` (SHA256 of the raw capture file). If an item in `~/ingest/staged/` matches a file already processed, the phone agent appends `"deduplicated": true` to the item metadata and moves it to `delivered` silently — no conflict.

**What happens if a Voice AI query was answered locally on the phone, but the laptop agent later processes the same transcript?**

The phone agent marks the voice query item with `"resolved_locally": true`. The laptop agent can optionally re-run the query on Ollama for a better answer and push the result as an async notification to the phone.

---

## Disconnection Modes

### Mode A: LAPTOP_UNREACHABLE

**Detection:** ICMP to laptop TS IP fails, but ICMP to 1.1.1.1 succeeds (tailnet down OR laptop off — indistinguishable).

**Behavior:**
- All laptop-dependent MCP tools return `TARGET_UNREACHABLE`
- Local-only mode engaged
- Phone agent runs autonomously
- Queue accumulates pending items
- Reconnection is polled every 60s per D9

**User-visible:** Phone shows a persistent notification: "Phone agent offline — laptop unreachable. Queuing <N> items."

### Mode B: Laptop reachable but MCP/Ollama down (degraded)

**Detection:** ICMP to laptop TS IP succeeds, but curl to Ollama /api/version fails.

**Behavior:**
- Same as Mode A, but reconnection is polled every 60s
- Subconscious Scheduler enters *light polling*: check laptop MCP status every 60s
- Ingest continues normally
- Voice AI uses local NPU with offline disclaimer

**User-visible:** No persistent notification (laptop sleep is expected). Brief toast on reconnect: "Laptop reconnected. Syncing <N> queued items."

### Mode C: NO_INTERNET

**Detection:** ICMP to 1.1.1.1 fails.

**Behavior:**
- Same as Mode A
- NPU Ingest runs on-device only (no web fetch for URL extraction)
- Voice AI uses local NPU only
- Queue is purely local
- Reconnection is manual (user turns off airplane mode)

**User-visible:** No notification (user chose to go offline). On reconnect: "Syncing <N> queued items."

---

## MCP Tool: `phone.queue.sync`

Used by laptop agent (Claude Code) to discover pending items.

```json
// Input
{
  "types": ["ingest", "voice_query", "schedule_result", "sensor_event"],
  "limit": 50,
  "since": "2026-07-14T00:00:00Z"
}

// Output
{
  "pending_count": 12,
  "delivered_count": 45,
  "failed_count": 1,
  "items": [
    {
      "id": "voice_query_a3f2c",
      "type": "voice_query",
      "created_at": "2026-07-14T15:03:22.000-05:00",
      "priority": "normal",
      "summary": "Voice query: 'what's the status of the net-gate build' — answered locally (offline)"
    }
  ]
}
```

## MCP Tool: `phone.queue.deliver`

Laptop agent calls this to pull and acknowledge a specific item.

```json
// Input
{
  "item_id": "voice_query_a3f2c",
  "acknowledge": true
}

// Output
{
  "item": { /* full item payload */ },
  "status": "delivered",
  "queue_remaining": 11
}
```

## MCP Tool: `phone.queue.clear_failed`

Laptop or phone agent can clear failed items after manual review.

```json
// Input
{
  "item_id": "failed_item_xyz",
  "action": "remove|retry|archive"
}
```
