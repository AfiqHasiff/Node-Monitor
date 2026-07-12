import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_logger: logging.Logger | None = None

_DEFAULT_LOG_DIR = Path(__file__).parent.parent / "logs"


def setup_logger(enabled: bool) -> logging.Logger:
    global _logger

    logger = logging.getLogger("monitor_agent")
    logger.setLevel(logging.INFO)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.WARNING)
    stdout_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(stdout_handler)

    if enabled:
        _DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)

        file_handler = TimedRotatingFileHandler(
            _DEFAULT_LOG_DIR / "monitor_agent.log",
            when="midnight",
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M"))
        logger.addHandler(file_handler)

    _logger = logger
    return logger


def make_packet_handler_logger(name: str) -> logging.Logger:
    """Create a dedicated logger for packet handler threads, writing to the unified log dir."""
    _DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    logger.addHandler(stdout_handler)

    file_handler = TimedRotatingFileHandler(
        _DEFAULT_LOG_DIR / f"{name}.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    if _logger is None:
        raise RuntimeError("Logger not initialised — call setup_logger() first")
    return _logger
