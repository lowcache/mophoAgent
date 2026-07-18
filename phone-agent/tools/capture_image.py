import asyncio

from ingest.capture_trigger import get_trigger
from ingest.store import generate_filename
from tools.capture_common import CaptureError, run_cli, raise_for_termux_api

EXIF_ISO = 0x8827
EXIF_FOCAL_LENGTH = 0x920A


def register(mcp):
    @mcp.tool(name="phone.capture.image")
    async def capture_image(camera_id: int = 0, resolution: str = "1920x1080",
                            format: str = "jpeg") -> dict:
        """Capture a single camera frame (termux-camera-photo) into
        ~/ingest/images/. The CLI captures at the device's native
        resolution; `resolution` is advisory — actual width/height are
        returned. Errors: CAMERA_BUSY, PERMISSION_DENIED,
        CAPTURE_FAILED."""
        out_path = generate_filename("images", "frame", "jpg")
        try:
            proc = await run_cli(["termux-camera-photo", "-c", str(camera_id),
                                  str(out_path)], timeout=30)
            raise_for_termux_api(proc, "CAMERA")
            if not out_path.exists() or out_path.stat().st_size == 0:
                raise CaptureError("CAPTURE_FAILED", "camera produced no file")

            def _meta():
                from PIL import Image
                with Image.open(out_path) as img:
                    return img.size, img.getexif()
            (width, height), exif_raw = await asyncio.to_thread(_meta)
            exif = {}
            if exif_raw.get(EXIF_ISO) is not None:
                exif["iso"] = int(exif_raw[EXIF_ISO])
            if exif_raw.get(EXIF_FOCAL_LENGTH) is not None:
                exif["focal_length"] = round(float(exif_raw[EXIF_FOCAL_LENGTH]), 2)
            result = {"image_path": str(out_path), "width": width,
                      "height": height, "exif": exif}
            get_trigger().on_capture("image", result)
            return result
        except CaptureError as e:
            out_path.unlink(missing_ok=True)
            return {"error": e.code, "message": e.message}
