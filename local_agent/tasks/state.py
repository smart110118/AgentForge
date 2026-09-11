from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"
