# Phase 2: Capture Tools

**Target Agent:** Claude Code (phone, Termux)
**Commit message:** `feat(phone-mcp): capture tools — audio, image, screenshot, share`

---

## What You Are Building

Four MCP tools that capture raw input from the phone's hardware: microphone audio, camera image, screen screenshot (via Shizuku), and Android share sheet content. These are the input side of the ingest pipeline — capture now, process later.

---

## Prerequisites

Phase 0 + Phase 1 built, tested, committed. NPU inference layer functional.

---

## File Structure

```
~/.config/phone-agent/
├── tools/
│   ├── capture_audio.py             # NEW: phone.capture.audio
│   ├── capture_image.py             # NEW: phone.capture.image
│   ├── capture_screenshot.py        # NEW: phone.capture.screenshot
│   ├── capture_share.py             # NEW: phone.capture.share
├── vad/
│   ├── __init__.py
│   ├── gate.py                      # NEW: Silero VAD gate
│   └── model.silero                 # Silero VAD model file
├── ingest/
│   ├── store.py                     # NEW: file naming + writer
│   └── layout.py                    # NEW: directory structure
├── tools/__init__.py                # ← from Phase 0 (modified)
├── main.py                          # ← from Phase 0 (register new tools)
├── tool_registry.py                 # ← from Phase 0 (register new tools)
```

**New directory structure created at server start:**

```
~/ingest/
├── audio/
├── images/
├── screenshots/
├── shares/
├── processed/           (future, Phase 3)
│   ├── transcripts/
│   ├── ocr/
│   └── summaries/
├── staged/              (future, Phase 3)
└── queue/               (future, Phase 6)
    ├── pending/
    ├── delivered/
    └── failed/
```

---

## Implementation Spec

### ingest/layout.py — Directory Creation

```python
INGEST_BASE = Path.home() / "ingest"
SUBDIRS = ["audio", "images", "screenshots", "shares",
           "processed/transcripts", "processed/ocr", "processed/summaries",
           "staged", "queue/pending", "queue/delivered", "queue/failed", "errors"]

def ensure_ingest_dirs():
    for subdir in SUBDIRS:
        (INGEST_BASE / subdir).mkdir(parents=True, exist_ok=True)
```

Called once at server startup.

### ingest/store.py — File Naming and Writing

```python
import hashlib, os, time

def generate_filename(source_type: str, extension: str) -> Path:
    """Generate a unique filename: YYYYMMDD_HHMMSS_{type}_{hash5}.{ext}"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    raw = f"{timestamp}_{os.urandom(4).hex()}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:5]
    filename = f"{timestamp}_{source_type}_{short_hash}.{extension}"
    return INGEST_BASE / source_type / filename

def write_capture(source_type: str, extension: str, data: bytes) -> Path:
    """Write raw bytes to the ingest directory and return the path."""
    path = generate_filename(source_type, extension)
    path.write_bytes(data)
    return path
```

### tools/capture_audio.py — `phone.capture.audio`

Record from the phone's microphone with VAD gating.

**Input:**
```json
{
  "max_duration_sec": 30,
  "sample_rate": 16000,
  "vad_threshold": 0.5,
  "vad_mode": 3
}
```

**Output:**
```json
{
  "audio_path": "~/ingest/audio/20260714_150322_raw_a3f2c.wav",
  "duration_sec": 14.2,
  "peak_level_db": -3.5,
  "vad_triggered": true
}
```

**Implementation:**
1. Use Python `sounddevice` or `pyaudio` to capture from microphone (requires `termux-microphone-record` via subprocess as fallback)
2. Feed raw audio into VAD gate (Silero VAD, runs on CPU — lightweight, <5% CPU)
3. VAD gate yields: `[speech (timestamp), silence, speech, silence, ...]`
4. Stop recording when:
   - Silence > 500ms after a speech segment (END OF UTTERANCE), OR
   - `max_duration_sec` reached (HARD CAP)
5. Write WAV file via `soundfile.write()` (16-bit PCM, mono)
6. Compute peak level and duration

**VAD Gate (vad/gate.py):**

Silero VAD. Uses the pre-trained ONNX model. Runs on CPU (negligible cost, <10ms per 30ms frame).

```python
class VADGate:
    def __init__(self, model_path: str, threshold: float = 0.5, mode: int = 3):
        # mode 3 = most aggressive filtering (best for clean speech)

    def is_speech(self, chunk: np.ndarray) -> bool:
        # Returns True if chunk contains speech
        # Processes 30ms frames, returns smoothed decision over last 5 frames
```

**Error states:**
- `MICROPHONE_BUSY` — termux-microphone-record returns "Device or resource busy"
- `VAD_TIMEOUT` — max_duration_sec reached with no speech detected → delete raw audio, return empty
- `PERMISSION_DENIED` — microphone permission not granted → guide user to grant via `termux-setup-storage`

### tools/capture_image.py — `phone.capture.image`

Capture a single frame from the camera.

**Input:**
```json
{
  "camera_id": 0,
  "resolution": "1920x1080",
  "format": "jpeg"
}
```

**Output:**
```json
{
  "image_path": "~/ingest/images/20260714_150322_frame_a3f2c.jpg",
  "width": 1920,
  "height": 1080,
  "exif": { "iso": 100, "focal_length": 4.6 }
}
```

**Implementation:**
- Use `termux-camera-photo` CLI tool:
  ```bash
  termux-camera-photo -c {camera_id} {output_path}
  ```
- Parse EXIF data from the resulting JPEG using `PIL.Image._getexif()`
- Copy the file into the ingest directory with the correct filename

**Error states:**
- `CAMERA_BUSY` — camera in use by another app
- `PERMISSION_DENIED` — camera permission not granted

### tools/capture_screenshot.py — `phone.capture.screenshot`

Capture the phone screen. Requires Shizuku rish.

**Input:**
```json
{
  "format": "png"
}
```

**Output:**
```json
{
  "image_path": "~/ingest/screenshots/20260714_150322_screen_a3f2c.png",
  "width": 1440,
  "height": 3120
}
```

**Implementation:**
1. Use Android's standard `screencap` command directly (available without root in local shell on S26):
   ```bash
   screencap -p /sdcard/temp_screenshot.png
   ```
2. Copy from `/sdcard/temp_screenshot.png` to `~/ingest/screenshots/` with correct filename
3. Delete the temp file
4. Read file dimensions from the image header

**Error states:**
- `DISPLAY_OFF` — screen is off, screencap returns black image → return error
- `STORAGE_WRITE_FAILED` — can't write to temp location

### tools/capture_share.py — `phone.capture.share`

Listen for incoming Android share sheet content. The phone has a Termux service that registers as a share target. When a user shares content (text, URL, image, file) to Termux from any app, this tool captures it.

**Input:**
```json
{
  "timeout_sec": 30
}
```

**Output:**
```json
{
  "type": "text",
  "content": "https://example.com/article",
  "source_app": "com.android.chrome"
}
```

**Implementation approach:**

The share sheet integration works through Termux's `termux-share-receive` tool:

1. Register Termux as a share target (one-time setup):
   - Android: Settings → Apps → Termux → Set as default → Text sharing
   - Or via `termux-open-send` intent

2. Receive shared content:
   ```bash
   # Blocking call — waits for incoming share
   termux-share-receive -t
   ```

3. The tool handler:
   - Runs `termux-share-receive -t` with a timeout wrapper
   - Parses the output: type (text/url/image/file), content, source app
   - If content is a URL → attempts to fetch and extract main content (readability)
     - Commented out in Phase 2 — just store the URL raw. Phase 3 adds full extraction.
   - Writes to `~/ingest/shares/` with metadata



**Error states:**
- `TIMEOUT` — no share received within `timeout_sec`
- `SHARE_NOT_SUPPORTED` — content type is not text, URL, image, or file

---

## Test Procedure

1. Test audio capture:
   ```bash
   echo '{"jsonrpc":"2.0","method":"tools/call","id":5,"params":{"name":"phone.capture.audio","arguments":{"max_duration_sec":5}}}' | ...
   ```
   Speak for 3 seconds. Verify file appears in `~/ingest/audio/` and duration is ~3s.

2. Test image capture:
   ```bash
   echo '{"jsonrpc":"2.0","method":"tools/call","id":6,"params":{"name":"phone.capture.image","arguments":{"resolution":"1920x1080"}}}' | ...
   ```
   Verify file appears in `~/ingest/images/`.

3. Test screenshot:
   ```bash
   echo '{"jsonrpc":"2.0","method":"tools/call","id":7,"params":{"name":"phone.capture.screenshot","arguments":{}}}' | ...
   ```
   Verify PNG file appears in `~/ingest/screenshots/`.

4. Test share sheet:
   - Open Chrome → Share a URL to Termux
   - Run: `echo '{"jsonrpc":"2.0","method":"tools/call","id":8,"params":{"name":"phone.capture.share","arguments":{"timeout_sec":30}}}' | ...`
   - Verify the URL appears in the output

---

## Acceptance Criteria

- [ ] `phone.capture.audio` records clean WAV file with correct sample rate
- [ ] VAD gate stops recording correctly after speech + 500ms silence
- [ ] VAD timeout returns empty result with `VAD_TIMEOUT` error
- [ ] `phone.capture.image` captures from camera and saves JPEG
- [ ] `phone.capture.screenshot` saves PNG with correct dimensions
- [ ] `phone.capture.screenshot` returns `DISPLAY_OFF` error when screen is off
- [ ] `phone.capture.share` receives text shares from Chrome
- [ ] `phone.capture.share` receives URL shares and stores raw URL
- [ ] Ingest directory structure exists with all subdirectories
- [ ] All filenames follow `YYYYMMDD_HHMMSS_type_hash5.ext` convention

---

## Guardrails

- **No NPU processing in this phase.** Capture stores raw files only. Phase 3 chains capture + NPU.
- **VAD runs on CPU, not NPU.** Silero VAD is <10ms per 30ms frame on a single CPU core — not worth NPU overhead to transfer.
- **Screenshot requires screen on.** Return clean error, not a corrupted black image.
- **Share sheet is best-effort.** Android's share system is unreliable across OEM skins. Build with `termux-share-receive` only.
- **Don't delete source files after ingest.** The raw file in `audio/` is the source of truth. The `processed/` directory contains derived artifacts. Each tool writes to its own subdirectory.

---

## Dependencies to Add

```toml
dependencies = [
    "orjson>=3.10",
    "pydantic>=2.0",
    "Pillow>=10.0",
    "numpy>=1.26",
    "sounddevice>=0.5",
    "soundfile>=0.13",
]
```

System packages:
```bash
pkg install python numpy openblas termux-api
# termux-camera-photo and termux-share-receive come with termux-api
```

Silero VAD model:
```bash
# Download silero vad onnx model
wget -O ~/.config/phone-agent/vad/model.silero \
  https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.onnx
```

---

## Git Commit

```bash
git add -A
git commit -m "feat(phone-mcp): capture tools — audio, image, screenshot, share"
git tag phone-mcp-phase-2
```

Rollback: `git revert HEAD`. Capture tools gone. NPU inference and server still work. Ingest directory structure stays but holds leftover files (safe to delete manually).
