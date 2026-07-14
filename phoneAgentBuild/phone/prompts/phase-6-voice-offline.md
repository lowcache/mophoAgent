# Phase 6: Voice AI + Offline Autonomy

**Target Agent:** Claude Code (phone, Termux)
**Commit message:** `feat(phone-mcp): offline autonomy queue`

---

## What You Are Building

**Offline Autonomy Queue** — When the laptop is unreachable over Tailscale, the phone queues all outgoing items (ingest manifests, scheduled task results) in a priority queue with delivery protocol, retry, dedup, and conflict resolution.

---

## Prerequisites

Phase 0 (server), Phase 1 (NPU whisper + LLM), Phase 5 (notify). Tailscale must be configured between phone and laptop.

---

## File Structure

```
~/.config/phone-agent/
├── queue/
│   ├── __init__.py
│   ├── manager.py                 # NEW: queue state machine
│   ├── delivery.py                # NEW: delivery protocol with retry + ack
├── offline/
│   ├── __init__.py
│   ├── detector.py                # NEW: disconnection mode detection
│   ├── mode.py                    # NEW: local-only mode behavior
├── tools/
│   ├── queue_sync.py              # NEW: phone.queue.sync
│   ├── queue_deliver.py           # NEW: phone.queue.deliver
│   ├── queue_clear_failed.py      # NEW: phone.queue.clear_failed
```

---

## Offline Autonomy

### offline/detector.py — Disconnection Mode Detection

```python
class DisconnectionDetector:
    def __init__(self, laptop_hostname: str = "volnix"):
        self.laptop_hostname = laptop_hostname
        self.state = "ONLINE"  # ONLINE | NO_INTERNET | LAPTOP_ASLEEP | AIRPLANE_MODE

    async def check_connection(self) -> str:
        """Check Tailscale connection to laptop. Returns current mode."""
        # Ping laptop via Tailscale
        try:
            proc = await termux_exec(f"tailscale ping {self.laptop_hostname} --c 1 --timeout 2s")
            if proc["exit_code"] == 0 and "pong" in proc["stdout"]:
                self.state = "ONLINE"
                return "ONLINE"
        except:
            pass

        # Check if phone has internet (ping 1.1.1.1 or similar)
        try:
            proc = await termux_exec("ping -c 1 -W 2 1.1.1.1")
            if proc["exit_code"] == 0:
                # Phone has internet, but laptop is unreachable → laptop asleep or Tailscale down
                self.state = "LAPTOP_ASLEEP"
                return "LAPTOP_ASLEEP"
        except:
            pass

        # No internet at all
        self.state = "AIRPLANE_MODE"
        return "AIRPLANE_MODE"
```

**Reconnection polling:**
- ONLINE → check every 60s (normal)
- LAPTOP_ASLEEP → check every 60s (laptop wake cycles are slow)
- NO_INTERNET → check every 30s (network may come back faster)
- AIRPLANE_MODE → check every 120s (user must manually disable)

### queue/manager.py — Queue State Machine

```python
@dataclass
class QueueItem:
    id: str
    type: str  # "ingest", "schedule_result", "sensor_event"
    created_at: str  # ISO timestamp
    priority: int  # 0=high, 1=normal, 2=low
    payload: dict  # The actual data
    status: str  # "pending", "delivering", "delivered", "failed"
    retry_count: int = 0
    max_retries: int = 5
    deduplicated: bool = False  # Duplicate of already-processed item

class QueueManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pending_dir = base_dir / "queue" / "pending"
        self.delivering_dir = base_dir / "queue" / "delivering"
        self.delivered_dir = base_dir / "queue" / "delivered"
        self.failed_dir = base_dir / "queue" / "failed"

    async def enqueue(self, item: QueueItem):
        """Add an item to the pending queue."""
        path = self.pending_dir / f"{item.id}.json"
        path.write_text(json.dumps(asdict(item)))

    async def dequeue(self, item_id: str) -> QueueItem:
        """Move item from pending → delivering and return it."""
        src = self.pending_dir / f"{item_id}.json"
        dst = self.delivering_dir / f"{item_id}.json"
        src.rename(dst)
        return QueueItem(**json.loads(dst.read_text()))

    async def acknowledge(self, item_id: str):
        """Move item from delivering → delivered."""
        src = self.delivering_dir / f"{item_id}.json"
        dst = self.delivered_dir / f"{item_id}.json"
        src.rename(dst)

    async def fail(self, item_id: str):
        """Move item to failed queue (after max retries)."""
        src = self.delivering_dir / f"{item_id}.json"
        item = QueueItem(**json.loads(src.read_text()))
        item.retry_count += 1
        if item.retry_count >= item.max_retries:
            dst = self.failed_dir / f"{item_id}.json"
            src.rename(dst)
        else:
            dst = self.pending_dir / f"{item_id}.json"
            src.rename(dst)

    def list_pending(self, types: list[str] = None, limit: int = 50) -> list[QueueItem]:
        """List pending items, filtered by type, sorted by priority then age."""
        items = []
        for path in sorted(self.pending_dir.iterdir()):
            item = QueueItem(**json.loads(path.read_text()))
            if types and item.type not in types:
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return sorted(items, key=lambda i: (i.priority, i.created_at))
```

### offline/mode.py — Local-Only Mode

```python
class LocalOnlyMode:
    def __init__(self, queue_mgr: QueueManager):
        self.queue = queue_mgr
        self.active = False

    async def enter(self):
        """Switch to local-only mode."""
        self.active = True

    async def exit(self):
        """Return to normal mode. Sync queue."""
        self.active = False
        # Notify user
        await send_notification("Phone agent reconnected", "Syncing queued items")
        # The laptop agent will call phone.queue.sync when it sees the reconnection

    def on_capture(self, capture_result: dict):
        """Enqueue ingest item for later delivery."""
        item = QueueItem(
            id=generate_id(),
            type="ingest",
            created_at=timestamp(),
            priority=1,
            payload=capture_result,
            status="pending"
        )
        self.queue.enqueue(item)
```

---

## Tools

### phone.queue.sync — List Pending Queue Items

```json
// Input
{ "types": ["ingest", "sensor_event"], "limit": 50 }

// Output
{
  "pending_count": 5,
  "delivered_count": 10,
  "failed_count": 1,
  "items": [
    { "id": "ing_a3f2c", "type": "ingest", "priority": 0, "summary": "...", "created_at": "..." }
  ]
}
```

### phone.queue.deliver — Deliver and Acknowledge

```json
// Input
{ "item_id": "ing_a3f2c", "acknowledge": true }

// Output
{ "item": { ... full payload ... }, "status": "delivered", "queue_remaining": 4 }
```

### phone.queue.clear_failed — Clear Failed Items

```json
// Input
{ "item_id": "fi_xyz", "action": "retry" }

// Output
{ "status": "retrying", "queue_remaining_failed": 0 }
```

---

## Test Procedure

1. Test offline detection:
   - Disconnect laptop from network (or shutdown Tailscale)
   - Verify phone detects offline state
   - Make an ingest capture → verify it's queued

2. Test queue delivery:
   - Reconnect laptop
   - Call `phone.queue.sync` → verify pending items appear
   - Call `phone.queue.deliver` → verify item delivered
   - Call again → verify item no longer in pending

---

## Acceptance Criteria

- [ ] Offline detection correctly identifies laptop unreachable vs no internet
- [ ] Queue persists items across server restart (files on disk)
- [ ] Queue delivery with ack moves items from pending → delivered
- [ ] Failed items (max retries) moved to failed directory
- [ ] Reconnection triggers sync notification

---

## Guardrails

- **Queue does not auto-sync.** The laptop agent must explicitly call `phone.queue.sync`. The phone agent doesn't push.
- **Queue items are JSON on disk.** If the phone reboots, pending items survive in `~/ingest/queue/pending/`.

---

## Git Commit

```bash
git add -A
git commit -m "feat(phone-mcp): offline autonomy queue"
git tag phone-mcp-phase-6
```

Rollback: `git revert HEAD`. Queue reverts. Everything else continues working.
