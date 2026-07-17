import asyncio
import shutil
from pathlib import Path

from ingest.store import generate_filename
from tools.capture_common import CaptureError, run_cli

# screencap needs the shell uid, so it runs via Shizuku rish and writes
# to shared storage (reachable by both uids; needs termux-setup-storage).
TMP_SHOT = Path("/sdcard/Download/.phone-agent-shot.png")


def register(mcp):
    @mcp.tool(name="phone.capture.screenshot")
    async def capture_screenshot(format: str = "png") -> dict:
        """Capture the phone screen via Shizuku rish + screencap into
        ~/ingest/screenshots/. Returns image_path, width, height.
        Errors: SHIZUKU_NOT_RUNNING, DISPLAY_OFF (all-black frame,
        deleted), STORAGE_WRITE_FAILED."""
        try:
            if shutil.which("rish") is None:
                raise CaptureError("SHIZUKU_NOT_RUNNING", "rish not on PATH")
            proc = await run_cli(["rish", "-c", f"screencap -p {TMP_SHOT}"],
                                 timeout=30)
            text = (proc.stdout + proc.stderr).lower()
            if proc.returncode != 0 or "binder" in text or "shizuku" in text:
                raise CaptureError("SHIZUKU_NOT_RUNNING",
                                   (proc.stderr or proc.stdout).strip()[:200]
                                   or "rish failed; is the Shizuku service running?")
            if not TMP_SHOT.exists() or TMP_SHOT.stat().st_size == 0:
                raise CaptureError("STORAGE_WRITE_FAILED",
                                   f"screencap wrote nothing to {TMP_SHOT}")

            out_path = generate_filename("screenshots", "screen", "png")
            await asyncio.to_thread(shutil.move, str(TMP_SHOT), str(out_path))

            def _inspect():
                from PIL import Image
                with Image.open(out_path) as img:
                    return img.size, img.convert("L").getextrema() == (0, 0)
            (width, height), all_black = await asyncio.to_thread(_inspect)
            if all_black:
                out_path.unlink(missing_ok=True)
                raise CaptureError("DISPLAY_OFF",
                                   "screen is off (all-black frame deleted)")
            return {"image_path": str(out_path), "width": width, "height": height}
        except CaptureError as e:
            return {"error": e.code, "message": e.message}
        finally:
            TMP_SHOT.unlink(missing_ok=True)
