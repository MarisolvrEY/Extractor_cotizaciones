"""
step2_clasificar.py
--------------------
PASO 2 — Lee los JSONs del paso 1 y clasifica cuáles son cotizaciones.

Por cada JSON de extracción:
  - Lee el texto extraído
  - Busca keywords: "cotización", "proforma", "presupuesto", etc.
  - Si coincide → copia el PDF original a data/cotizaciones_encontradas/

Requiere que el paso 1 ya haya corrido (data/output/json/*.json existan).

Output:
  data/cotizaciones_encontradas/<nombre>.pdf   (copia del PDF original)

Uso:
  python step2_clasificar.py
  python step2_clasificar.py --json-dir data/output/json --input data/input
  python step2_clasificar.py --destino /mi_carpeta_cotizaciones
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from config import settings
from src.classification.document_classifier import classify_document
from src.utils.logger import get_logger

logger = get_logger("paso2", settings.LOG_LEVEL)


def clasificar(
    json_dir: Path | None = None,
    input_dir: Path | None = None,
    destino_dir: Path | None = None,
) -> dict:
    settings.ensure_dirs()
    src_json = json_dir    or settings.OUTPUT_OCR_DIR
    src_pdfs = input_dir   or settings.INPUT_DIR
    dst      = destino_dir or settings.COTIZACIONES_DIR
    dst.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("  PASO 2 — Clasificación por keywords")
    logger.info("=" * 60)
    logger.info(f"  JSONs de OCR   : {src_json}")
    logger.info(f"  PDFs originales: {src_pdfs}")
    logger.info(f"  Destino        : {dst}")

    json_files = sorted(src_json.glob("*_ocr.json"))
    if not json_files:
        logger.warning(f"No se encontraron JSONs en {src_json}. ¿Corriste el paso 1?")
        return {"total": 0, "cotizaciones": 0, "otros": 0, "sin_pdf": 0}

    total        = len(json_files)
    cotizaciones = 0
    otros        = 0
    sin_pdf      = 0

    logger.info(f"\nClasificando {total} documento(s)…\n")

    for jf in json_files:
        ocr_data = json.loads(jf.read_text(encoding="utf-8"))
        file_name = ocr_data.get("file_name", jf.stem)

        cls = classify_document(ocr_data)

        if cls.is_cotizacion:
            # Buscar el PDF original por nombre
            pdf_origen = next((f for f in src_pdfs.rglob(file_name) if f.is_file()), None)
            if not pdf_origen:
                logger.warning(f"  ⚠ PDF no encontrado: {pdf_origen}")
                sin_pdf += 1
                continue

            shutil.copy2(pdf_origen, dst / pdf_origen.name)
            logger.info(
                f"  [green]✓ COTIZACIÓN[/green]  {file_name}  "
                f"│ keywords: {cls.matched_keywords}"
            )
            cotizaciones += 1
        else:
            logger.info(f"  [dim]─ otro       {file_name}[/dim]")
            otros += 1

    logger.info("\n" + "=" * 60)
    logger.info(f"  Total          : {total}")
    logger.info(f"  Cotizaciones   : [green]{cotizaciones}[/green]  → {dst.name}/")
    logger.info(f"  Otros          : {otros}")
    logger.info(f"  PDF no hallado : {sin_pdf}")
    logger.info("=" * 60)

    if cotizaciones == 0:
        logger.info("\n  Tip: ajusta las keywords en config/settings.py → COTIZACION_KEYWORDS")

    return {
        "total":        total,
        "cotizaciones": cotizaciones,
        "otros":        otros,
        "sin_pdf":      sin_pdf,
    }


def _args():
    p = argparse.ArgumentParser(description="Paso 2: clasificar JSONs y copiar cotizaciones.")
    p.add_argument("--json-dir", type=Path, default=None, help="Carpeta con los JSONs del paso 1")
    p.add_argument("--input",    type=Path, default=None, help="Carpeta con los PDFs originales")
    p.add_argument("--destino",  type=Path, default=None, help="Carpeta destino de cotizaciones")
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    r = clasificar(
        json_dir=args.json_dir,
        input_dir=args.input,
        destino_dir=args.destino,
    )
    sys.exit(0 if r["cotizaciones"] > 0 else 1)
