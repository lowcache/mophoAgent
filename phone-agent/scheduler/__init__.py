"""Phase 7 subconscious scheduler: event-driven task loop.

Not a cron replacement — an asyncio loop that evaluates triggers on a tick,
gates each firing on live device conditions (battery, charging, WiFi), runs
the action, logs the result, and queues it for the laptop when offline.
"""
