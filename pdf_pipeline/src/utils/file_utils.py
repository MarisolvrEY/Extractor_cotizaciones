"""
src/utils/file_utils.py
-----------------------
Utilidades para manejo de archivos PDF y escritura de resultados.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__, settings.LOG_LEVEL)

MAX_BYTES = settings.MAX_PDF_SIZE_MB * 1024 * 1024


def collect_pdfs(input_dir: Path | None = None) -> list[Path]:
    """
    Devuelve todos los archivos .pdf encontrados en input_dir,
    filtrando los que excedan MAX_PDF_SIZE_MB.
    """
    directory = input_dir or settings.INPUT_DIR
    pdfs = sorted(directory.glob("*.pdf"))

    valid: list[Path] = []
    for pdf in pdfs:
        size = pdf.stat().st_size
        if size > MAX_BYTES:
            logger.warning(
                f"[yellow]Omitido[/yellow] {pdf.name} "
                f"({size / 1024 / 1024:.1f} MB > {settings.MAX_PDF_SIZE_MB} MB)"
            )
        else:
            valid.append(pdf)

    logger.info(f"PDFs encontrados: {len(valid)} válidos de {len(pdfs)} total.")
    return valid


def save_json(data: dict[str, Any], dest_dir: Path, filename: str) -> Path:
    """
    Guarda un dict como archivo .json con indentación legible.
    Devuelve el Path del archivo creado.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not filename.endswith(".json"):
        filename += ".json"
    path = dest_dir / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug(f"JSON guardado → {path}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    """Carga un archivo JSON y lo devuelve como dict."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_prompt(prompt_file: str) -> str:
    """
    Carga el contenido de un archivo de prompt desde PROMPTS_DIR.
    Lanza FileNotFoundError si no existe.
    """
    path = settings.PROMPTS_DIR / prompt_file
    if not path.exists():
        raise FileNotFoundError(f"Prompt no encontrado: {path}")
    return path.read_text(encoding="utf-8").strip()
