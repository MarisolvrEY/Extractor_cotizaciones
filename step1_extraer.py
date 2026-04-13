"""
step1_extraer.py
-----------------
PASO 1 — OCR de todos los archivos en data/procesables/ con Azure AI Content Understanding.

Lee cada archivo (PDF, imagen, Office, .txt) y guarda el texto extraído
como JSON en data/output/json/.

Requiere que el paso 0 ya haya corrido.

Output:
  data/output/json/<nombre>_ocr.json

Uso:
  python step1_extraer.py
  python step1_extraer.py --origen data/procesables
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from config import settings
from src.extraction.azure_ocr import extract_pdf
from src.utils.file_utils import collect_files, save_json
from src.utils.logger import get_logger

logger = get_logger("paso1", settings.LOG_LEVEL)

# Los .txt (cuerpos de email) se leen directamente, sin Azure
_TXT_EXTENSIONS = {".txt"}


def extraer(
    origen_dir: Path | None = None,
    json_dir:   Path | None = None,
) -> dict:
    settings.ensure_dirs()
    src      = origen_dir or settings.PROCESABLES_DIR
    dst_json = json_dir   or settings.OUTPUT_OCR_DIR

    logger.info("=" * 60)
    logger.info("  PASO 1 — Azure AI Content Understanding OCR")
    logger.info("=" * 60)
    logger.info(f"  Origen   : {src}")
    logger.info(f"  JSONs    : {dst_json}")
    logger.info(f"  Analyzer : {settings.AZURE_OCR_ANALYZER}")

    archivos = collect_files(src)
    if not archivos:
        logger.warning(f"No hay archivos en {src}. ¿Corriste el paso 0?")
        return {"total": 0, "exitosos": 0, "errores": 0}

    exitosos = 0
    errores  = 0

    logger.info(f"\nProcesando {len(archivos)} archivo(s)…\n")

    for archivo in tqdm(archivos, desc="OCR", unit="archivo"):
        ext = archivo.suffix.lower()

        if ext in _TXT_EXTENSIONS:
            # Cuerpo de email — leer texto directamente sin Azure
            result = {
                "file_name":         archivo.name,
                "full_text":         archivo.read_text(encoding="utf-8", errors="replace"),
                "pages":             [],
                "page_count":        1,
                "analyzer_id":       "local-txt",
                "extraction_status": "success",
                "error_message":     None,
            }
        else:
            # Azure OCR para el resto
            result = extract_pdf(archivo)

        save_json(result, dst_json, f"{archivo.stem}_ocr.json")

        if result["extraction_status"] == "success":
            exitosos += 1
        else:
            errores += 1

    logger.info("\n" + "=" * 60)
    logger.info(f"  Total    : {len(archivos)}")
    logger.info(f"  Exitosos : [green]{exitosos}[/green]")
    logger.info(f"  Errores  : {errores}")
    logger.info(f"  JSONs en : {dst_json}")
    logger.info("=" * 60)

    return {"total": len(archivos), "exitosos": exitosos, "errores": errores}


def _args():
    p = argparse.ArgumentParser(description="Paso 1: OCR con Azure AI Content Understanding.")
    p.add_argument("--origen",   type=Path, default=None)
    p.add_argument("--json-dir", type=Path, default=None)
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    try:
        settings.validate_paso1()
    except ValueError as exc:
        logger.error(f"[red]{exc}[/red]")
        sys.exit(1)
    r = extraer(origen_dir=args.origen, json_dir=args.json_dir)
    sys.exit(0 if r["exitosos"] > 0 else 1)
