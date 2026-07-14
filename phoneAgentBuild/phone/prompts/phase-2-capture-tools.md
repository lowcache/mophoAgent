# Phase 2: Capture Tools

**Target Agent:** Claude Code (phone, Termux)
**Commit message:** `feat(phone-mcp): capture tools — audio, image, screenshot, share`

---

## What You Are Building

Four MCP tools that capture raw input from the phone's hardware: microphone audio, camera image, screen screenshot (via Shizuku), and Android share sheet content. These are the input side of the ingest pipeline — capture now, process later.

---

## Prerequisites

Phase 0 + Phase 1 built, tested, committed. Inference layer functional.

---

## File Structure

```
~/phone-agent/
├── tools/
│   ├── capture_audio.py             # NEW: phone.capture.audio
│   ├── capture_image.py             # NEW: phone.capture.image
│   ├── capture_screenshot.py        # NEW: phone.capture.screenshot
│   ├── capture_share.py             # NEW: phone.capture.share
├── vad/
│   ├── __init__.py
│   ├── gate.py                      # NEW: Silero VAD trim/gate
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
│   └── spool/           (termux-url-opener writes here)
├── processed/           (future, Phase 3)
│   ├── transcripts/
│   ├── ocr/
│   └── summaries/
├── staged/              (future, Phase 3)
└── queue/               (future, Phase 6)
    ├── pending/
    ├── delivering/
    ├── delivered/
    └── failed/
```

---

## Implementation Spec

### ingest/layout.py — Directory Creation

```python
INGEST_BASE = Path.home() / "ingest"
SUBDIRS = ["audio", "images", "screenshots", "shares", "shares/spool",
           "processed/transcripts", "processed/ocr", "processed/summaries",
           "processed/scheduled", "staged",
           "queue/pending", "queue/delivering", "queue/delivered",
           "queue/failed", "errors"]

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

Record from the phone's microphone, then VAD-trim the result.

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

**Implementation (baseline: record-then-trim):**
1. Record with `termux-microphone-record -f {tmp_path} -l {max_duration_sec} -r {sample_rate} -c 1` (`termux-microphone-record -q` stops early if needed). This is file-based — Termux does not reliably expose a live mic stream to Python.
2. Load the finished WAV, run Silero VAD over it to find speech spans.
3. Trim leading/trailing silence around the detected speech span (with `speech_pad_ms` padding); write the trimmed WAV via `soundfile` (16-bit PCM, mono) into `~/ingest/audio/`.
4. If no speech was detected at all → delete the recording, return `VAD_TIMEOUT`.
5. Compute peak level and duration from the trimmed audio.

**Optional upgrade (NOT baseline):** live VAD gating that stops recording at end-of-utterance requires a streaming mic source (pulseaudio in Termux). Attempt only after the record-then-trim path is committed; keep the trim path as fallback.

**VAD (vad/gate.py):**

Silero VAD, pre-trained ONNX model, runs on CPU (<10ms per 30ms frame).

```python
class VADGate:
    def __init__(self, model_path: str, threshold: float = 0.5, mode: int = 3):
        # mode 3 = most aggressive filtering (best for clean speech)

    def speech_spans(self, audio: np.ndarray, sample_rate: int) -> list[tuple[float, float]]:
        # Returns [(start_sec, end_sec), ...] speech segments over the whole clip
```

**Error states:**
- `MICROPHONE_BUSY` — termux-microphone-record returns "Device or resource busy"
- `VAD_TIMEOUT` — recording contained no detected speech → delete raw audio, return empty
- `PERMISSION_DENIED` — microphone permission not granted to the **Termux:API app** (Android Settings → Apps → Termux:API → Permissions → Microphone). This is an Android app permission — `termux-setup-storage` is unrelated.

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
- Parse EXIF data from the resulting JPEG using `PIL.Image.getexif()` (public API — not `_getexif()`)
- Copy the file into the ingest directory with the correct filename

**Error states:**
- `CAMERA_BUSY` — camera in use by another app
- `PERMISSION_DENIED` — camera permission not granted (Termux:API app permission)

### tools/capture_screenshot.py — `phone.capture.screenshot`

Capture the phone screen. **Requires Shizuku rish** — `screencap` needs the shell uid; there is no direct path from the Termux uid.

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
1. Run `screencap` through rish to a shared-storage temp path:
   ```bash
   rish -c 'screencap -p /sdcard/Download/.phone-agent-shot.png'
   ```
2. Move the file into `~/ingest/screenshots/` with the correct filename (requires `termux-setup-storage` for /sdcard access).
3. Delete the temp file.
4. Read file dimensions from the image header.

**Error states:**
- `SHIZUKU_NOT_RUNNING` — Shizuku service not available
- `DISPLAY_OFF` — screen is off, screencap returns black image → return error
- `STORAGE_WRITE_FAILED` — can't write to temp location

### tools/capture_share.py — `phone.capture.share`

Receive content shared from other apps via the Android share sheet.

**Note: `termux-share-receive` does not exist.** The real mechanism is Termux's hook scripts: when content is shared to Termux, the app invokes `~/bin/termux-url-opener` (URLs/text) or `~/bin/termux-file-editor` (files) with the shared content as argument.

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
  "source_app": null
}
```
(`source_app` is not observable from the hook scripts; report `null`.)

**Implementation:**

1. One-time setup — install the hook scripts (this phase creates them):

   `~/bin/termux-url-opener`:
   ```bash
   #!/data/data/com.termux/files/usr/bin/bash
   # Invoked by Termux when a URL/text is shared to it.
   spool="$HOME/ingest/shares/spool"
   mkdir -p "$spool"
   printf '{"ts":"%s","type":"text","content":%s}\n' \
       "$(date -Iseconds)" "$(printf '%s' "$1" | jq -Rs .)" \
       > "$spool/$(date +%Y%m%d_%H%M%S)_$$.json"
   ```

   `~/bin/termux-file-editor` — same shape with `"type":"file"` and the file path as content (copy the file into `~/ingest/shares/` first so it survives).

2. The tool handler polls `~/ingest/shares/spool/` (0.5s interval) until a new spool entry appears or `timeout_sec` elapses. On receipt: parse the JSON line, classify content as text/url/image/file, move the entry out of spool into `~/ingest/shares/`, return the result.

3. If content is a URL → store the URL raw in Phase 2. Phase 3 adds fetch + extraction.

**Error states:**
- `TIMEOUT` — no share received within `timeout_sec`
- `SHARE_NOT_SUPPORTED` — content type is not text, URL, image, or file

---

## Test Procedure

Requests go to the running server per Phase 0's curl pattern:

```bash
mcp_call() {  # helper: mcp_call TOOL ARGS_JSON
  curl -s -H "Authorization: Bearer $(cat ~/.config/phone-agent/token)" \
    -H 'Content-Type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}" \
    "http://$PHONE_TS_IP:8462/mcp"
}
```

1. Audio: `mcp_call phone.capture.audio '{"max_duration_sec":5}'` — speak for 3 seconds. Verify file appears in `~/ingest/audio/` trimmed to the speech span (~3s).
2. Image: `mcp_call phone.capture.image '{"resolution":"1920x1080"}'` — verify JPEG in `~/ingest/images/`.
3. Screenshot: `mcp_call phone.capture.screenshot '{}'` — verify PNG in `~/ingest/screenshots/`.
4. Share: open Chrome → Share a URL to Termux, then `mcp_call phone.capture.share '{"timeout_sec":30}'` — verify the URL appears in the output.

---

## Acceptance Criteria

- [ ] `phone.capture.audio` records clean WAV with correct sample rate
- [ ] Recorded file is VAD-trimmed to the speech span (leading/trailing silence removed)
- [ ] A recording with no speech returns `VAD_TIMEOUT` and the file is deleted
- [ ] `phone.capture.image` captures from camera and saves JPEG
- [ ] `phone.capture.screenshot` saves PNG with correct dimensions (via rish)
- [ ] `phone.capture.screenshot` returns `DISPLAY_OFF` error when screen is off
- [ ] `phone.capture.share` receives text shares from Chrome via termux-url-opener spool
- [ ] `phone.capture.share` receives URL shares and stores the raw URL
- [ ] Ingest directory structure exists with all subdirectories (including `queue/delivering/`)
- [ ] All filenames follow `YYYYMMDD_HHMMSS_type_hash5.ext` convention

---

## Guardrails

- **No NPU/LLM processing in this phase.** Capture stores raw files only. Phase 3 chains capture + compute.
- **VAD runs on CPU.** Silero VAD is <10ms per 30ms frame on a single CPU core.
- **Screenshot requires screen on.** Return clean error, not a corrupted black image.
- **Share sheet is best-effort.** Android share behavior varies across OEM skins; the termux-url-opener spool is the reliable path. Test on the actual device early.
- **Don't delete source files after ingest.** The raw file in `audio/` is the source of truth. The `processed/` directory contains derived artifacts. Each tool writes to its own subdirectory.

---

## Dependencies to Add

```toml
dependencies = [
    "httpx",
    "pydantic>=2.0",
    "Pillow>=10.0",
    "numpy>=1.26",
    "soundfile>=0.13",
]
```
(`onnxruntime` already required from Phase 1 for the Silero model. `sounddevice`/`pyaudio` are NOT baseline deps — only relevant to the optional streaming-VAD upgrade.)

System packages:
```bash
pkg install termux-api jq
# termux-camera-photo / termux-microphone-record come with termux-api
# (Termux:API companion app must also be installed, with mic + camera permissions granted)
```

Silero VAD model:
```bash
wget -O ~/phone-agent/vad/model.silero \
  https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.onnx
```

---

## Git Commit

```bash
git add -A
git commit -m "feat(phone-mcp): capture tools — audio, image, screenshot, share"
git tag phone-mcp-phase-2
git push origin phone
```

Rollback: `git revert HEAD`. Capture tools gone. Inference and server still work. Ingest directory structure stays but holds leftover files (safe to delete manually).
