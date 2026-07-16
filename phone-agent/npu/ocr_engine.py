"""CPU OCR: PP-OCR English recognition model + numpy line segmentation.

Baseline per D5: no detection model — lines are found with horizontal
projection (binarize → row ink density → bands), then each line crop runs
through the CTC recognition model (onnxruntime, CPU EP). Handles printed
text on reasonably clean backgrounds (screenshots, documents). The
det-model upgrade path (PP-OCRv5 det + polygon postprocess) is noted in
the phase relay message.
"""

import threading
import numpy as np
from pathlib import Path
from PIL import Image, ImageOps

_lock = threading.Lock()
_session = None
_charset: list[str] = []
_input_name = ""
_input_height = 48

MIN_LINE_HEIGHT = 8       # px; smaller bands are noise
LINE_GAP = 2              # blank rows tolerated inside one line
INK_ROW_FRAC = 0.005      # fraction of columns that must be ink to call a row "text"


def _load(model_dir: Path):
    global _session, _charset, _input_name, _input_height
    with _lock:
        if _session is not None:
            return
        import onnxruntime
        sess = onnxruntime.InferenceSession(
            str(model_dir / "rec-en.onnx"),
            providers=["CPUExecutionProvider"])
        inp = sess.get_inputs()[0]
        _input_name = inp.name
        if isinstance(inp.shape[2], int) and inp.shape[2] > 0:
            _input_height = inp.shape[2]
        # Class k maps to dict line k with a trailing space class; the
        # dict's first line "#" is the CTC blank placeholder (class 0),
        # verified empirically against rendered text.
        chars = (model_dir / "dict-en.txt").read_text(encoding="utf-8").splitlines()
        _charset = [*chars, " "]
        _session = sess


def _binarize(gray: np.ndarray) -> np.ndarray:
    """Otsu threshold; returns bool ink mask (True = text pixel), with the
    foreground chosen as the minority class (text is sparser than paper)."""
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    sum_all = np.dot(np.arange(256), hist)
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


def _line_bands(ink: np.ndarray) -> list[tuple[int, int]]:
    row_ink = ink.mean(axis=1)
    is_text = row_ink > INK_ROW_FRAC
    bands, start, gap = [], None, 0
    for y, flag in enumerate(is_text):
        if flag:
            start = y if start is None else start
            gap = 0
        elif start is not None:
            gap += 1
            if gap > LINE_GAP:
                if y - gap - start + 1 >= MIN_LINE_HEIGHT:
                    bands.append((start, y - gap + 1))
                start, gap = None, 0
    if start is not None and len(is_text) - start >= MIN_LINE_HEIGHT:
        bands.append((start, len(is_text)))
    return bands


def _recognize(rgb: np.ndarray) -> tuple[str, float]:
    """Run one line crop (RGB uint8 HxWx3) through the CTC rec model."""
    h, w = rgb.shape[:2]
    new_w = max(8, int(round(w * _input_height / h)))
    img = Image.fromarray(rgb).resize((new_w, _input_height), Image.BILINEAR)
    x = np.asarray(img, dtype=np.float32).transpose(2, 0, 1)[None]
    x = (x / 255.0 - 0.5) / 0.5
    logits = _session.run(None, {_input_name: x})[0][0]   # (T, C)
    if logits.min() >= 0.0 and abs(float(logits[0].sum()) - 1.0) < 1e-3:
        probs = logits   # model output is already softmaxed
    else:
        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)
    ids = probs.argmax(axis=1)
    conf = probs.max(axis=1)
    chars, confs, prev = [], [], -1
    for i, idx in enumerate(ids):
        # idx 0 is the CTC blank ("#" placeholder line in the dict).
        if idx != prev and 0 < idx < len(_charset):
            chars.append(_charset[idx])
            confs.append(conf[i])
        prev = idx
    text = "".join(chars).strip()
    return text, float(np.mean(confs)) if confs else 0.0


def run(model_dir: Path, image_path: Path, languages: list[str]) -> dict:
    """Full pipeline: image → text blocks in reading order. `languages` is
    accepted for schema compatibility; only the English model ships."""
    _load(Path(model_dir))
    img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
    rgb = np.asarray(img)
    gray = np.asarray(img.convert("L"))
    ink = _binarize(gray)

    blocks = []
    for y0, y1 in _line_bands(ink):
        cols = ink[y0:y1].mean(axis=0) > 0
        xs = np.flatnonzero(cols)
        if xs.size == 0:
            continue
        x0, x1 = int(xs[0]), int(xs[-1]) + 1
        pad = max(2, (y1 - y0) // 4)
        cy0, cy1 = max(0, y0 - pad), min(rgb.shape[0], y1 + pad)
        cx0, cx1 = max(0, x0 - pad), min(rgb.shape[1], x1 + pad)
        text, conf = _recognize(rgb[cy0:cy1, cx0:cx1])
        if text:
            blocks.append({"text": text,
                           "bbox": [x0, int(y0), x1, int(y1)],
                           "confidence": round(conf, 4)})
    return {
        "blocks": blocks,
        "full_text": "\n".join(b["text"] for b in blocks),
    }
