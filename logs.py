"""Log capture: keeps the last N log entries in memory (for the dashboard)
and writes everything to logs/service.log (rotating). No secrets are captured.
"""
import logging
import os
import threading
from collections import deque
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

MAX_BUFFER = 1000

_buffer = deque(maxlen=MAX_BUFFER)
_lock = threading.Lock()

LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}


class RingBufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if record.exc_info:
                message += "\n" + self.format(record)
            entry = {
                "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": message,
            }
            with _lock:
                _buffer.append(entry)
        except Exception:
            pass


def install() -> None:
    """Attach the ring buffer and rotating file handler to the root logger."""
    root = logging.getLogger()
    if any(isinstance(handler, RingBufferHandler) for handler in root.handlers):
        return

    ring = RingBufferHandler()
    ring.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(ring)

    try:
        os.makedirs("logs", exist_ok=True)
        file_handler = RotatingFileHandler(
            "logs/service.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(file_handler)
    except Exception:
        pass


def recent(limit: int = 200, level: str = "") -> list[dict]:
    """Return newest-first log entries, optionally filtered by minimum level."""
    min_level = LEVELS.get(level.upper(), 0) if level else 0
    with _lock:
        entries = list(_buffer)
    if min_level:
        entries = [entry for entry in entries if LEVELS.get(entry["level"], 0) >= min_level]
    return entries[-limit:][::-1]


def clear() -> None:
    with _lock:
        _buffer.clear()
