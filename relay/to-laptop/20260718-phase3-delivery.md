---
type: delivery
from: claude-phone
date: 2026-07-18
subject: Phase 3 delivered — processing pipelines live, all acceptance green
status: open
---

# Phase 3 delivery: processing pipelines (tag `phone-mcp-phase-3`, 3fac7e2)

Deployed to the native runtime and verified live on
`http://100.101.229.9:8462` (runit respawn confirmed, pid 32345, service
log clean). Battery: **5/5 ALL PASS @ exactly 12 tools** (new tool:
`phone.pipeline.run`).

## What shipped

- `pipeline/executor.py` — linear-DAG stage runner: async fns awaited
  (NPU submits go through the serialized queue at PRIORITY_BATCH), sync
  fns via `asyncio.to_thread`, per-stage `asyncio.wait_for` timeouts,
  `PipelineError` carries partial run context; formatter dispatch by
  `output_type` at the end (pipelines have no format stage).
- `pipeline/audio_transcript.py` — VAD segment (stdlib wave; 8/16 kHz,
  16-bit, downmix) → whisper → transcript.
- `pipeline/image_ocr.py` — EXIF orient + projection-profile deskew
  (±10°, 5%-improvement guard so blank/uniform images never rotate;
  corrections saved under staged/, source read-only) → OCR →
  reading-order line merge.
- `pipeline/share_extract.py` — classify(store/query/command/ignore) →
  extract (url via httpx / text / text-file) → summarize-if->500-words →
  embed. URL extraction is a stdlib `html.parser` scorer
  (`pipeline/extract_html.py`) — tether-verified that every readability
  lib (readability-lxml, trafilatura, justext, goose3, newspaper4k,
  resiliparse) needs lxml/C extensions that cannot load in the bionic
  venv.
- `ingest/capture_trigger.py` — captures auto-trigger their pipeline,
  fire-and-forget with strong-ref task set; error dicts ignored;
  image/file shares with image extensions reroute to image_ocr. Failures
  land as JSON records (with partial context) in `~/ingest/errors/`.
- `tools/pipeline_trigger.py` — `phone.pipeline.run(pipeline, files)`;
  `files` is a dict of context keys (`audio_path` / `image_path` /
  `url` / `text`); returns `{pipeline_id, status:"running"}`.
- Watchdog layer (phase-2 follow-up you flagged): bootstrap now applies
  the rish `max_phantom_processes` mitigation (guarded `|| true`), and
  `scripts/watchdog.sh` is an external /health probe that re-runs
  bootstrap, installed by `scripts/watchdog-install.sh` via
  termux-job-scheduler (job 462, 15 min, persisted). No process killing
  anywhere in the repo.

## Live acceptance evidence (2026-07-18, on-device)

- **audio_transcript**: `phone.pipeline.run` on the phase-2 wav →
  `processed/transcripts/…json` with the spoken sentence verbatim,
  schema-correct (speaker null, start/end sec), 11.6 s.
- **image_ocr real text**: synthetic 800×300 text PNG → both lines
  extracted verbatim, reading order correct, conf 0.97–0.99, 315 ms.
- **image_ocr photo**: phase-2 4080×3060 camera JPEG → clean empty-block
  output, no spurious deskew rotation, 1.6 s.
- **share_extract URL**: live fetch of https://example.com → title
  "Example Domain" + body extracted, intent classified on-device,
  summary correctly null (<500 words), 384-dim embedding, 4.4 s.
- **auto-trigger**: `phone.capture.image` alone produced a new
  `processed/ocr` record (EXIF transpose applied: 3060×4080 from a
  4080×3060 capture) — capture → trigger → pipeline → store, no manual
  call.
- **error path** (offline battery, HOME-isolated): missing audio file →
  JSON error record in `ingest/errors/` with pipeline/stage/partial
  context; error-dict captures ignored; image-share reroute verified.

## Deviations from the phase-3 prompt (flagging, not hiding)

- Stage timeouts raised: classify 30 s (spec 10), summarize 120 s (spec
  60), whisper 120 s. Queue wait counts toward the stage timeout under
  the serialized NPU queue, so spec values starve batch-priority stages.
- Summarize input head-truncated to 2500 chars and embed input to 800
  chars — qwen serves a 1024-token context, embed caps at 256 tokens.
- `tags` is always `[]` (no tagging model in scope this phase).
- Missing input file surfaces as generic `STAGE_ERROR` (wave.open
  FileNotFoundError mapping), not a dedicated code.
- `duration_sec` is null when audio runs via manual `pipeline.run`
  (only the capture flow knows it).
- Share auto-trigger fires on `capture.share` spool drain; image/file
  shares reroute to image_ocr rather than failing in share_extract.

## Operator gate items (phone-side, need a human)

1. Run `bash ~/mophoAgent/phone-agent/scripts/watchdog-install.sh` in a
   NATIVE session — 4 termux-job-scheduler flag uncertainties need
   on-device validation (cancel-flag form, 900000 ms floor,
   `--persisted true` arg form, PATH environment for rish inside the
   job). `termux-job-scheduler --pending` should show job 462 after.
2. Settings → Battery → Unrestricted for both Termux and Termux:API
   (the job scheduler and the phantom mitigation don't survive
   otherwise).
3. Optional confidence check: reboot, wait for Termux:Boot, confirm
   /health 200 and that a shared URL from Brave lands in
   `processed/summaries/` untouched.

Laptop side: please run `scripts/verify.sh http://100.101.229.9:8462`
over the tailnet (expect 5/5 @ 12 tools) and sign off, per the
phase-merge ritual.
