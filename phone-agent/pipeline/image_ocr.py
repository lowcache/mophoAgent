"""Image OCR pipeline: orientation/deskew, OCR, reading-order merge.

Source files are read-only: any correction is saved under staged/ via
ingest.store. Deskew is projection-profile variance over ±10° on a
downscaled binarized copy; corrections under 2° are ignored.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from ingest.store import generate_filename
from npu.queue import PRIORITY_BATCH
from pipeline.executor import Pipeline, Stage, StageFailed

DESKEW_MAX_WIDTH = 800
DESKEW_MIN_DEG = 2.0


def _otsu_ink(gray: np.ndarray) -> np.ndarray:
    """Otsu threshold; bool ink mask with the minority class as text
    (same approach as npu/ocr_engine.py, kept local)."""
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    sum_all = float(np.dot(np.arange(256), hist))
    sum_b = cum_b = 0.0
    best_t, best_var = 127, -1.0
    for t in range(256):
        cum_b += hist[t]
        if cum_b == 0 or cum_b == total:
            continue
        sum_b += t * hist[t]
        m_b = sum_b / cum_b
        m_f = (sum_all - sum_b) / (total - cum_b)
        var = cum_b * (total - cum_b) * (m_b - m_f) ** 2
        if var > best_var:
            best_var, best_t = var, t
    dark = gray <= best_t
    return dark if dark.mean() <= 0.5 else ~dark


def _estimate_skew(img: Image.Image) -> float:
    small = img.convert("L")
    if small.width > DESKEW_MAX_WIDTH:
        small = small.resize(
            (DESKEW_MAX_WIDTH,
             max(1, round(small.height * DESKEW_MAX_WIDTH / small.width))),
            Image.BILINEAR)
    ink = _otsu_ink(np.asarray(small, dtype=np.uint8))
    if not ink.any():
        return 0.0
    ink_img = Image.fromarray(ink.astype(np.uint8) * 255)

    def score(angle):
        arr = np.asarray(ink_img.rotate(angle, fillcolor=0))
        return float(arr.sum(axis=1, dtype=np.float64).var())

    base = score(0.0)
    best_angle, best_score = 0.0, base
    for angle in (i * 0.5 for i in range(-20, 21)):
        s = score(angle)
        if s > best_score:
            best_score, best_angle = s, angle
    # Require a clear win over the unrotated profile; near-uniform images
    # otherwise pick an arbitrary angle.
    return best_angle if best_score > base * 1.05 else 0.0


def _orient_correct(image_path: str) -> dict:
    img = Image.open(image_path)
    orientation = img.getexif().get(0x0112, 1)
    img = ImageOps.exif_transpose(img)
    changed = orientation not in (None, 1)

    angle = _estimate_skew(img)
    if abs(angle) > DESKEW_MIN_DEG:
        if img.mode == "P":
            img = img.convert("RGB")
        img = img.rotate(angle, expand=True, fillcolor="white")
        changed = True

    if changed:
        ext = (Path(image_path).suffix.lstrip(".") or "png").lower()
        if img.mode in ("RGBA", "P") and ext in ("jpg", "jpeg"):
            img = img.convert("RGB")
        out = generate_filename("staged", "corrected", ext)
        img.save(out)
        corrected_path = str(out)
    else:
        corrected_path = image_path
    return {"corrected_path": corrected_path,
            "resolution": [img.width, img.height]}


async def _ocr_run(corrected_path: str) -> dict:
    from npu import get_queue
    from npu.bridge import InferenceError
    try:
        result = await get_queue().submit(
            "ocr-model",
            {"image_path": corrected_path, "languages": ["en"]},
            priority=PRIORITY_BATCH)
    except InferenceError as e:
        raise StageFailed(e.code, e.message) from e
    if isinstance(result, dict) and "error" in result:
        raise StageFailed(str(result["error"]),
                          str(result.get("message", "inference failed")))
    return {"blocks": result["blocks"]}


def _order_blocks(blocks: list) -> dict:
    if not blocks:
        return {"ordered_blocks": []}
    heights = sorted(b["bbox"][3] - b["bbox"][1] for b in blocks)
    tol = max(heights[len(heights) // 2] / 2.0, 1.0)
    lines: list[list] = []  # [anchor_cy, [blocks]]
    for b in sorted(blocks, key=lambda b: (b["bbox"][1] + b["bbox"][3]) / 2.0):
        cy = (b["bbox"][1] + b["bbox"][3]) / 2.0
        if lines and abs(cy - lines[-1][0]) <= tol:
            lines[-1][1].append(b)
        else:
            lines.append([cy, [b]])
    ordered = []
    for _, line in lines:
        line.sort(key=lambda b: b["bbox"][0])
        ordered.append({
            "text": " ".join(b["text"] for b in line),
            "bbox": [min(b["bbox"][0] for b in line),
                     min(b["bbox"][1] for b in line),
                     max(b["bbox"][2] for b in line),
                     max(b["bbox"][3] for b in line)],
            "confidence": min(b["confidence"] for b in line),
        })
    return {"ordered_blocks": ordered}


PIPELINE = Pipeline(
    name="image_ocr",
    output_type="ocr",
    stages=[
        Stage(name="orient_correct", fn=_orient_correct,
              inputs=["image_path"], outputs=["corrected_path", "resolution"],
              timeout_sec=10),
        Stage(name="ocr_run", fn=_ocr_run,
              inputs=["corrected_path"], outputs=["blocks"],
              npu_required=True, timeout_sec=60),
        Stage(name="order_blocks", fn=_order_blocks,
              inputs=["blocks"], outputs=["ordered_blocks"], timeout_sec=5),
    ],
)
