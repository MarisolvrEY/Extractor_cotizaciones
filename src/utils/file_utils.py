"""
src/utils/file_utils.py
-----------------------
Utilidades para manejo de archivos y escritura de resultados.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__, settings.LOG_LEVEL)

MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024

# Formatos que acepta Azure AI Content Understanding
SUPPORTED_EXTENSIONS: set[str] = {
    ".eml", ".msg",
    ".txt",
    ".pdf",
    ".jpg", ".jpeg",
    ".png",
    ".bmp",
    ".tiff", ".tif",
    ".docx",
    ".xlsx",
    ".pptx",
}


def collect_files(input_dir: Path | None = None) -> list[Path]:
    """
    Recorre input_dir de forma recursiva y retorna todos los archivos
    con extensión soportada por Azure AI Content Understanding.

    - Busca en subcarpetas (rglob)
    - Descarta archivos que superen MAX_FILE_SIZE_MB
    - Ordena por ruta completa para reproducibilidad
    """
    directory = input_dir or settings.INPUT_DIR
    all_files = sorted(
        f for f in directory.rglob("*")
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    valid: list[Path] = []
    skipped_size = 0

    for f in all_files:
        size = f.stat().st_size
        if size > MAX_BYTES:
            logger.warning(
                f"[yellow]Omitido[/yellow] {f.relative_to(directory)} "
                f"({size / 1024 / 1024:.1f} MB > {settings.MAX_FILE_SIZE_MB} MB)"
            )
            skipped_size += 1
        else:
            valid.append(f)

    logger.info(
        f"Archivos encontrados: {len(valid)} válidos "
        f"({skipped_size} omitidos por tamaño) "
        f"en {directory}"
    )
    return valid


def save_json(data: dict[str, Any], dest_dir: Path, filename: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not filename.endswith(".json"):
        filename += ".json"
    path = dest_dir / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug(f"JSON guardado → {path}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
