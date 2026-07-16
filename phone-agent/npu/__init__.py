"""NPU runtime singletons shared by all tool handlers."""

_registry = None
_bridge = None
_queue = None


def get_registry():
    global _registry
    if _registry is None:
        from npu.models import ModelRegistry
        _registry = ModelRegistry()
    return _registry


def get_bridge():
    global _bridge
    if _bridge is None:
        from npu.bridge import NPUBridge
        _bridge = NPUBridge(get_registry())
    return _bridge


def get_queue():
    global _queue
    if _queue is None:
        from npu.queue import InferenceQueue
        _queue = InferenceQueue(get_bridge())
    return _queue
