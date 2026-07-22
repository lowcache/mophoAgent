def register_all(mcp):
    import tools.health
    import tools.transcribe
    import tools.ocr
    import tools.embed
    import tools.classify
    import tools.infer
    import tools.capture_audio
    import tools.capture_image
    import tools.capture_screenshot
    import tools.capture_share
    import tools.pipeline_trigger
    import tools.sensor_imu
    import tools.sensor_modem
    import tools.sensor_gps
    import tools.sensor_light
    import tools.sensor_proximity
    import tools.sys_rish
    import tools.sys_exec
    import tools.sys_free_ram
    import tools.sys_notify
    import tools.voice_ask
    import tools.voice_start
    import tools.voice_stop
    import tools.queue_sync
    import tools.queue_deliver
    import tools.queue_clear_failed

    tools.health.register(mcp)
    tools.transcribe.register(mcp)
    tools.ocr.register(mcp)
    tools.embed.register(mcp)
    tools.classify.register(mcp)
    tools.infer.register(mcp)
    tools.capture_audio.register(mcp)
    tools.capture_image.register(mcp)
    tools.capture_screenshot.register(mcp)
    tools.capture_share.register(mcp)
    tools.pipeline_trigger.register(mcp)
    tools.sensor_imu.register(mcp)
    tools.sensor_modem.register(mcp)
    tools.sensor_gps.register(mcp)
    tools.sensor_light.register(mcp)
    tools.sensor_proximity.register(mcp)
    tools.sys_rish.register(mcp)
    tools.sys_exec.register(mcp)
    tools.sys_free_ram.register(mcp)
    tools.sys_notify.register(mcp)
    tools.voice_ask.register(mcp)
    tools.voice_start.register(mcp)
    tools.voice_stop.register(mcp)
    tools.queue_sync.register(mcp)
    tools.queue_deliver.register(mcp)
    tools.queue_clear_failed.register(mcp)
