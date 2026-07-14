# MCP Server — Tool Schema Specification

## Runtime
- **Host:** Termux (native, not proot) (built by Claude Code from proot; server runs native — see phone/PHONE-ENV.md)
- **Language:** Python 3.12+ (uv/pip)
- **Transport:** MCP Streamable HTTP (FastMCP/uvicorn), phone Tailscale IP:8462
- **Auth:** Bearer token per D1 (Tailscale CLI/LocalAPI unavailable on Android)
- **Startup:** Automate triggers on boot → rish starts termux-mcpd → systemd user service or tmux session

## Tool Definitions

### Category 1: Capture Tools

#### `phone.capture.audio`

Capture microphone audio with VAD gating. Returns when silence >500ms or max_duration reached.

Input:
```json
{
  "max_duration_sec": 30,
  "sample_rate": 16000,
  "vad_threshold": 0.5,
  "vad_mode": 3
}
```

Output:
```json
{
  "audio_path": "/data/data/com.termux/files/home/ingest/audio/20260714_150322_raw.wav",
  "duration_sec": 14.2,
  "peak_level_db": -3.5,
  "vad_triggered": true
}
```

Errors:
- `MICROPHONE_BUSY` — another process holds the audio device
- `VAD_TIMEOUT` — max_duration reached with no speech detected
- `PERMISSION_DENIED` — Termux:API microphone permission not granted

#### `phone.capture.image`

Capture a single frame from the camera.

Input:
```json
{
  "camera_id": 0,
  "resolution": "1920x1080",
  "format": "jpeg"
}
```

Output:
```json
{
  "image_path": "/data/data/com.termux/files/home/ingest/images/20260714_150322_frame.jpg",
  "width": 1920,
  "height": 1080,
  "exif": { "iso": 100, "focal_length": 4.6 }
}
```

Errors:
- `CAMERA_BUSY`
- `PERMISSION_DENIED`

#### `phone.capture.screenshot` (Shizuku-mediated)

Capture phone screen contents via `screenshot` shell command (requires Shizuku rish).

Input:
```json
{
  "format": "png"
}
```

Output:
```json
{
  "image_path": "/data/data/com.termux/files/home/ingest/screenshots/20260714_150322_screen.png",
  "width": 1440,
  "height": 3120
}
```

Errors:
- `SHIZUKU_NOT_RUNNING`
- `DISPLAY_OFF`

#### `phone.capture.share`

Receive content shared from other apps via Android share sheet → termux-url-opener spool mechanism (D10).

Input:
```json
{
  "timeout_sec": 30
}
```

Output:
```json
{
  "type": "text|url|image|file",
  "content": "shared text content or file path",
  "source_app": "com.android.chrome"
}
```

Errors:
- `TIMEOUT` — no share received within window

---

### Category 2: NPU Compute Tools

#### `phone.npu.transcribe`

Run on-device Whisper on an audio file via Qualcomm SNPE / QNN or llama.cpp with whisper backend on NPU.

Input:
```json
{
  "audio_path": "/path/to/raw.wav",
  "model": "whisper-small.en",
  "language": "en",
  "temperature": 0.0
}
```

Output:
```json
{
  "segments": [
    { "start_sec": 0.0, "end_sec": 2.3, "text": "Hello, this is a test recording." }
  ],
  "full_text": "Hello, this is a test recording.",
  "processing_time_ms": 3452,
  "model_used": "whisper-small.en-q4_0"
}
```

Errors:
- `MODEL_NOT_LOADED` — NPU model not initialized
- `NPU_BUSY` — another inference is running
- `AUDIO_TOO_LONG` — exceeds model max context (default: 30s)

#### `phone.npu.ocr`

Run on-device OCR on an image via NPU (ML Kit or custom ONNX model compiled for QNN).

Input:
```json
{
  "image_path": "/path/to/image.jpg",
  "languages": ["en"],
  "detect_orientation": true
}
```

Output:
```json
{
  "blocks": [
    { "text": "Hello World", "bounding_box": [10, 20, 200, 40], "confidence": 0.97 }
  ],
  "full_text": "Hello World",
  "processing_time_ms": 890
}
```

Errors:
- `IMAGE_TOO_LARGE` — exceeds 4096px on any axis (pre-scale client-side)
- `NO_TEXT_DETECTED`
- `NPU_BUSY`

#### `phone.npu.embed`

Compute text embeddings using a small NPU-accelerated embedding model (e.g., all-MiniLM-L6-v2 q4).

Input:
```json
{
  "text": "string to embed",
  "model": "all-minilm-l6-v2-q4",
  "normalize": true
}
```

Output (the `embedding` array is 384 floats — abbreviated here):
```json
{
  "embedding": [0.0123, -0.0456, 0.0789],
  "dimensions": 384,
  "processing_time_ms": 45
}
```

Errors:
- `MODEL_NOT_LOADED`
- `TEXT_TOO_LONG` — exceeds model token limit (256 tokens default)

#### `phone.npu.classify`

Run intent classification on short text (for routing queries: "is this a voice query for Ollama, a document to store, or a system command?").

Input:
```json
{
  "text": "short input text",
  "labels": ["store", "query", "command", "ignore"],
  "model": "qwen2.5-1.5b-q4"
}
```

Output:
```json
{
  "label": "query",
  "confidence": 0.93,
  "scores": { "store": 0.02, "query": 0.93, "command": 0.04, "ignore": 0.01 }
}
```

Errors:
- `MODEL_NOT_LOADED` — classifier model (qwen2.5-1.5b) not loaded

#### `phone.npu.llm_infer`

Run short inference on a local 1-3B model (qwen2.5-1.5b) for fast-path responses (CPU baseline; NPU sub-50ms TTFT is a D5 stretch; short context <1024 tokens). This tool answers locally only; deep/heavy queries are sent to the laptop's Ollama by the Phase 6 router (via the Ollama HTTP API over Tailscale per D3), not by this tool. The `routed_to_laptop` field is always `false` here.

Input:
```json
{
  "prompt": "What is 2+2?",
  "model": "qwen2.5-1.5b-q4",
  "max_tokens": 256,
  "temperature": 0.7
}
```

Output:
```json
{
  "response": "2+2 = 4",
  "tokens_generated": 8,
  "ttft_ms": 38,
  "tokens_per_sec": 42.3,
  "model_used": "qwen2.5-1.5b-q4",
  "routed_to_laptop": false
}
```

Errors:
- `CONTEXT_OVERFLOW` — prompt exceeds model max context
- `MODEL_NOT_LOADED`

---

### Category 3: Sensor Tools

#### `phone.sensor.read_imu`

Read accelerometer + gyroscope snapshot.

Input:
```json
{
  "sample_count": 50,
  "sample_interval_ms": 20
}
```

Output:
```json
{
  "samples": [
    { "accel": [0.1, 9.8, 0.2], "gyro": [0.01, 0.00, -0.01] }
  ],
  "inference": "on_desk",
  "inference_confidence": 0.95
}
```

Inference values: `on_desk`, `in_hand`, `in_pocket`, `walking`, `stationary`, `unknown`

#### `phone.sensor.read_modem`

Read cellular network state (requires Shizuku rish for some fields).

Input:
```json
{
  "fields": ["bssid", "signal_dbm", "network_type", "is_roaming"]
}
```

Output:
```json
{
  "bssid": "ab:cd:ef:12:34:56",
  "ssid": "HomeWiFi",
  "signal_dbm": -45,
  "network_type": "WiFi",
  "cellular_type": "5G_NR",
  "cellular_signal_rsrp": -95,
  "is_roaming": false,
  "first_hop_latency_ms": 3.2
}
```

#### `phone.sensor.read_gps`

Read current GPS coordinates (single shot, low power).

Input:
```json
{
  "timeout_sec": 5
}
```

Output:
```json
{
  "lat": 41.8827,
  "lon": -87.6233,
  "accuracy_m": 15,
  "geofence": "home"
}
```

Geofence values determined by configurable fence definitions (home, work, gym, etc.), defined in `~/.config/phone-agent/geofences.json`.

#### `phone.sensor.read_light`

Read ambient light sensor value.

Output:
```json
{
  "lux": 320,
  "label": "indoor_bright"
}
```

Labels: `pitch_black`, `dim`, `indoor_bright`, `outdoor_shade`, `direct_sunlight`

#### `phone.sensor.read_proximity`

Read proximity sensor.

Output:
```json
{
  "distance_cm": 0.5,
  "is_covered": true
}
```

---

### Category 4: System Tools

#### `phone.system.rish`

Execute a command through Shizuku's rish shell (ADL-level privileges).

Input:
```json
{
  "command": "am force-stop com.android.chrome",
  "timeout_sec": 10
}
```

Output:
```json
{
  "stdout": "",
  "stderr": "",
  "exit_code": 0,
  "execution_time_ms": 234
}
```

Errors:
- `SHIZUKU_NOT_RUNNING`
- `TIMEOUT` — command did not complete within timeout
- `FORBIDDEN_COMMAND` — command is on the blocklist (rm -rf /, factory reset, etc.)

#### `phone.system.termux_exec`

Execute a command inside Termux's native environment.

Input:
```json
{
  "command": "ls -la ~/ingest/",
  "timeout_sec": 30,
  "workdir": "~"
}
```

Output:
```json
{
  "stdout": "total 4\ndrwxr-xr-x ...",
  "stderr": "",
  "exit_code": 0,
  "execution_time_ms": 12
}
```

#### `phone.system.free_ram`

Suspend or kill heavy background apps to free RAM for inference. Uses rish `am kill` and `cmd activity`.

Input:
```json
{
  "target_free_mb": 2048,
  "aggressiveness": "normal"  // normal | aggressive
}
```

Output:
```json
{
  "freed_mb": 2150,
  "available_mb": 6144,
  "killed_packages": ["com.android.chrome", "com.instagram.android"]
}
```

#### `phone.system.state`

Report current phone state: battery, thermal, available RAM, running MCP tools.

Output:
```json
{
  "battery_pct": 78,
  "charging": true,
  "thermal_state": "cool",
  "available_ram_mb": 4096,
  "mcp_server_uptime_sec": 86400,
  "active_tools": ["npu.transcribe", "sensor.read_imu"],
  "pending_queue_depth": 3
}
```

#### `phone.system.notify`

Send a system notification to the phone's status bar.

Input:
```json
{
  "title": "Audit Complete",
  "body": "Vulnerability found. PR generated.",
  "priority": "high",
  "click_action": null
}
```

Output:
```json
{
  "notification_id": 42
}
```

---

## Tool Registration

The MCP server advertises its capabilities via two steps. First, `initialize`:

```json
{
  "protocolVersion": "2024-11-05",
  "capabilities": {
    "tools": {
      "listChanged": false
    }
  },
  "serverInfo": {
    "name": "phone-mcp",
    "version": "1.0.0"
  }
}
```

Second, `tools/list`:

```json
{
  "tools": [
    {
      "name": "phone.capture.audio",
      "description": "Record audio with VAD gating",
      "inputSchema": {
        "type": "object",
        "properties": {
          "max_duration_sec": { "type": "integer" }
        }
      }
    },
    {
      "name": "phone.capture.image",
      "description": "Capture camera frame"
    },
    {
      "name": "phone.capture.screenshot",
      "description": "Capture phone screen"
    }
  ]
}
```

(The remaining 18 tools follow the same shape with their respective descriptions.)

### Category 5: Ingest Transfer Tools

#### `phone.ingest.list`

List files in the staged directory per D6.

Input:
```json
{
  "since": "2026-07-14T00:00:00Z",
  "limit": 100
}
```

Output:
```json
{
  "files": [
    { "name": "20260714_150322_transcript_a3f2c.json", "size_bytes": 1024, "sha256": "...", "pipeline": "audio_transcript", "created_at": "2026-07-14T15:03:22Z" }
  ]
}
```

#### `phone.ingest.fetch`

Fetch a staged file per D6.

Input:
```json
{
  "name": "20260714_150322_transcript_a3f2c.json",
  "delete_after": true
}
```

Output:
```json
{
  "name": "20260714_150322_transcript_a3f2c.json",
  "sha256": "...",
  "content_b64": "..."
}
```

Errors:
- `FILE_NOT_FOUND` — the file doesn't exist
- `HASH_MISMATCH` — (Note for laptop side verification)

## Ingestion Staging Directory

All capture output lands in `~/ingest/` with subdirectories:

```
~/ingest/
├── audio/
├── images/
├── screenshots/
├── shares/
├── processed/     # after NPU transformation
│   ├── transcripts/
│   ├── ocr/
│   └── summaries/
└── staged/        # ready for consumption (laptop agent polls this)
```

## File Naming Convention

`YYYYMMDD_HHMMSS_{type}_{short_hash}.ext`

Example: `20260714_150322_audio_a3f2c.wav`
Hash is first 5 chars of SHA256 of the file content (or capture timestamp + random nonce).
