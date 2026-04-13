"""
step1_extraer.py
-----------------
PASO 1 — Extrae el contenido de todos los PDFs con Azure AI Content Understanding.

Por cada PDF:
  - Llama a la API REST de Content Understanding (OCR)
  - Guarda el resultado como JSON en data/output/json/

Output:
  data/output/json/<nombre>_ocr.json   (uno por cada PDF)

Uso:
  python step1_extraer.py
  python step1_extraer.py --input data/input
  python step1_extraer.py --input /mis_pdfs --json-dir /mis_outputs
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from config import settings
from src.extraction.azure_ocr import extract_pdf
from src.utils.file_utils import collect_pdfs, save_json
from src.utils.logger import get_logger

logger = get_logger("paso1", settings.LOG_LEVEL)


def extraer(
    input_dir: Path | None = None,
    json_dir: Path | None = None,
) -> dict:
    settings.ensure_dirs()
    src      = input_dir or settings.INPUT_DIR
    dst_json = json_dir  or settings.OUTPUT_OCR_DIR

    logger.info("=" * 60)
    logger.info("  PASO 1 — Azure AI Content Understanding OCR")
    logger.info("=" * 60)
    logger.info(f"  Entrada   : {src}")
    logger.info(f"  JSONs     : {dst_json}")
    logger.info(f"  Analyzer  : {settings.AZURE_OCR_ANALYZER}")

    pdfs = collect_pdfs(src)
    if not pdfs:
        logger.warning("No se encontraron PDFs.")
        return {"total": 0, "exitosos": 0, "errores": 0}

    exitosos = 0
    errores  = 0

    logger.info(f"\nExtrayendo {len(pdfs)} PDF(s)…\n")

    for pdf in tqdm(pdfs, desc="OCR", unit="pdf"):
        result = extract_pdf(pdf)
        save_json(result, dst_json, f"{pdf.stem}_ocr.json")

        if result["extraction_status"] == "success":
            exitosos += 1
        else:
            errores += 1

    logger.info("\n" + "=" * 60)
    logger.info(f"  Total     : {len(pdfs)}")
    logger.info(f"  Exitosos  : [green]{exitosos}[/green]")
    logger.info(f"  Errores   : {errores}")
    logger.info(f"  JSONs en  : {dst_json}")
    logger.info("=" * 60)

    return {"total": len(pdfs), "exitosos": exitosos, "errores": errores}


def _args():
    p = argparse.ArgumentParser(description="Paso 1: OCR de todos los PDFs con Azure AI Content Understanding.")
    p.add_argument("--input",    type=Path, default=None, help="Carpeta de PDFs de entrada")
    p.add_argument("--json-dir", type=Path, default=None, help="Carpeta para los JSONs de salida")
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    try:
        settings.validate_paso1()
    except ValueError as exc:
        logger.error(f"[red]{exc}[/red]")
        sys.exit(1)
    r = extraer(input_dir=args.input, json_dir=args.json_dir)
    sys.exit(0 if r["exitosos"] > 0 else 1)
