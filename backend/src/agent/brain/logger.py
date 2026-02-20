"""
src/agent/brain/logger.py — Structured color logging
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {
    "DEBUG": "\033[36m", "INFO": "\033[32m",
    "WARNING": "\033[33m", "ERROR": "\033[31m",
    "CRITICAL": "\033[35m", "RESET": "\033[0m",
}

class ColorFormatter(logging.Formatter):
    def format(self, record):
        c = COLORS.get(record.levelname, "")
        r = COLORS["RESET"]
        record.levelname = f"{c}{record.levelname}{r}"
        record.name = f"\033[34m{record.name}{r}"
        return super().format(record)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"echo.{name}")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(ColorFormatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s", "%H:%M:%S"))
    fh = logging.FileHandler(LOG_DIR / f"echo_{datetime.now().strftime('%Y-%m-%d')}.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger
