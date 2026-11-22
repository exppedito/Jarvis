import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name: str = "jarvis") -> logging.Logger:
    """Configura logger em arquivo rotativo (logs/jarvis.log) sem poluir o terminal ou o TTS."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    root_dir = Path(__file__).resolve().parents[2]
    logs_dir = root_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "jarvis.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1_048_576,  # 1 MB por arquivo
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
