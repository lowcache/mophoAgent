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
