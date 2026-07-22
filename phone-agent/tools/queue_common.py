"""Shared wiring for the Phase 6 queue/offline tools (not a tool module).
Queue files live under ~/ingest/queue/ so pending items survive a reboot.
"""

from config.settings import INGEST_DIR
from msgqueue.manager import QueueManager
from msgqueue.delivery import DeliveryProtocol
from offline.mode import LocalOnlyMode
from tools.voice_common import get_router, notify

_qm: QueueManager | None = None
_delivery: DeliveryProtocol | None = None
_offline: LocalOnlyMode | None = None


def get_queue_manager() -> QueueManager:
    global _qm
    if _qm is None:
        _qm = QueueManager(INGEST_DIR)
    return _qm


def get_delivery() -> DeliveryProtocol:
    global _delivery
    if _delivery is None:
        _delivery = DeliveryProtocol(get_queue_manager())
    return _delivery


def get_offline_mode() -> LocalOnlyMode:
    global _offline
    if _offline is None:
        _offline = LocalOnlyMode(get_queue_manager(), get_router(), notify=notify)
    return _offline
