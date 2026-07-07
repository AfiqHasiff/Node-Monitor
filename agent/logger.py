import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_logger: logging.Logger | None = None


def setup_logger(enabled: bool) -> logging.Logger:
    global _logger

    logger = logging.getLogger("monitor_agent")
    logger.setLevel(logging.INFO)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.WARNING)
    stdout_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(stdout_handler)

    if enabled:
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)

        file_handler = TimedRotatingFileHandler(
            log_dir / "monitor_agent.log",
            when="midnight",
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M"))
        logger.addHandler(file_handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    if _logger is None:
        raise RuntimeError("Logger not initialised — call setup_logger() first")
    return _logger
