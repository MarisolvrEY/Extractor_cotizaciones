"""
src/utils/logger.py
-------------------
Configura un logger centralizado con rich para salida formateada en consola
y un FileHandler para persistir logs en disco.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from rich.logging import RichHandler

_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_LOG_DIR.mkdir(exist_ok=True)


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Devuelve (o reutiliza) un logger con:
    - RichHandler para consola con colores
    - FileHandler para logs/pipeline.log
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # ya inicializado

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # ── Consola (rich) ────────────────────────────────────────────────────
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_path=False,
        markup=True,
    )
    console_handler.setLevel(numeric_level)

    # ── Archivo ───────────────────────────────────────────────────────────
    file_handler = logging.FileHandler(_LOG_DIR / "pipeline.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger
