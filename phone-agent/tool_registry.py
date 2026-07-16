def register_all(mcp):
    import tools.health
    import tools.transcribe
    import tools.ocr
    import tools.embed
    import tools.classify
    import tools.infer

    tools.health.register(mcp)
    tools.transcribe.register(mcp)
    tools.ocr.register(mcp)
    tools.embed.register(mcp)
    tools.classify.register(mcp)
    tools.infer.register(mcp)
