import asyncio
import os

from ingest.capture_trigger import get_trigger

VALID_PIPELINES = ("audio_transcript", "image_ocr", "share_extract")


def register(mcp):
    @mcp.tool(name="phone.pipeline.run")
    async def pipeline_run(pipeline: str, files: dict) -> dict:
        """Manually run a processing pipeline on existing files. Input:
        pipeline (audio_transcript | image_ocr | share_extract) and files
        — context keys for the pipeline (audio_path for audio_transcript,
        image_path for image_ocr; share_extract takes url or text).
        Fire-and-forget: output JSON lands under ~/ingest/processed/,
        failures under ~/ingest/errors/. Returns pipeline_id + status.
        Errors: PIPELINE_UNKNOWN, FILE_NOT_FOUND."""
        if pipeline not in VALID_PIPELINES:
            return {"error": "PIPELINE_UNKNOWN",
                    "message": f"expected one of {', '.join(VALID_PIPELINES)}"}

        context = {}
        for key, value in (files or {}).items():
            if isinstance(value, str) and key.endswith("_path"):
                value = os.path.expanduser(value)
                if not os.path.isfile(value):
                    return {"error": "FILE_NOT_FOUND", "message": value}
            context[key] = value

        # Convenience: build the share envelope from bare url/text keys.
        if pipeline == "share_extract" and "raw_share" not in context:
            if "url" in context:
                context["raw_share"] = {"type": "url",
                                        "content": context.pop("url")}
            elif "text" in context:
                context["raw_share"] = {"type": "text",
                                        "content": context.pop("text")}
        context.setdefault("source_path", context.get("audio_path")
                           or context.get("image_path"))

        pipeline_id = os.urandom(3).hex()
        trigger = get_trigger()
        task = asyncio.get_running_loop().create_task(
            trigger._run_and_store(pipeline, context))
        trigger.tasks.add(task)
        task.add_done_callback(trigger.tasks.discard)
        return {"pipeline_id": pipeline_id, "status": "running"}
