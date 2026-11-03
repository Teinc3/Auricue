import logging
import sys
from datetime import datetime
from pathlib import Path


LOG_DIR = Path("logs")
logger = logging.getLogger("auricue")
logger.setLevel(logging.DEBUG)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

_file_handler: logging.Handler | None = None


def open_session_log(session_id: int | None) -> None:
    """Attach session file handler at DEBUG level."""

    global _file_handler
    close_session_log()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(
        LOG_DIR / f"session-{session_id}-{ts}.log", encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(fh)
    _file_handler = fh


def close_session_log() -> None:
    """Detach and close active session file handler."""

    global _file_handler
    if not _file_handler:
        return
    logger.removeHandler(_file_handler)
    _file_handler.close()
    _file_handler = None


__all__ = ["close_session_log", "logger", "open_session_log"]
