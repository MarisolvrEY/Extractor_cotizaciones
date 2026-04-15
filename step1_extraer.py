"""
step1_extraer.py
-----------------
PASO 1 — OCR de todos los archivos en data/procesables/ con Azure Document Intelligence.

Si existe un <nombre>_emailmeta.json junto al archivo (generado por step0 para emails),
lo incorpora en el JSON de salida bajo la clave "email_meta".

Output:
  data/output/json/<nombre>_ocr.json

Uso:
  python step1_extraer.py
  python step1_extraer.py --origen data/procesables
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tqdm import tqdm

from config import settings
from src.extraction.azure_ocr import extract_pdf
from src.utils.file_utils import collect_files, save_json, SUPPORTED_EXTENSIONS
from src.utils.logger import get_logger

logger = get_logger("paso1", settings.LOG_LEVEL)

_TXT_EXTENSIONS      = {".txt"}
_EMAILMETA_SUFFIX    = "_emailmeta.json"


def _load_emailmeta(archivo: Path) -> dict | None:
    """
    Busca un archivo <stem>_emailmeta.json junto al archivo dado.
    Retorna el dict si existe, None si no.
    """
    meta_path = archivo.parent / f"{archivo.stem}{_EMAILMETA_SUFFIX}"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def extraer(
    origen_dir: Path | None = None,
    json_dir:   Path | None = None,
) -> dict:
    settings.ensure_dirs()
    src      = origen_dir or settings.PROCESABLES_DIR
    dst_json = json_dir   or settings.OUTPUT_OCR_DIR

    logger.info("=" * 60)
    logger.info("  PASO 1 — Azure Document Intelligence OCR")
    logger.info("=" * 60)
    logger.info(f"  Origen   : {src}")
    logger.info(f"  JSONs    : {dst_json}")
    logger.info(f"  Analyzer : {settings.AZURE_OCR_ANALYZER}")

    # Excluir los _emailmeta.json de la lista de archivos a procesar
    archivos = [
        f for f in collect_files(src)
        if not f.name.endswith(_EMAILMETA_SUFFIX)
    ]

    if not archivos:
        logger.warning(f"No hay archivos en {src}. ¿Corriste el paso 0?")
        return {"total": 0, "exitosos": 0, "errores": 0}

    exitosos = 0
    errores  = 0

    logger.info(f"\nProcesando {len(archivos)} archivo(s)…\n")

    for archivo in tqdm(archivos, desc="OCR", unit="archivo"):
        ext = archivo.suffix.lower()

        if ext in _TXT_EXTENSIONS:
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
            result = extract_pdf(archivo)

        # Si existe metadato de email, incorporarlo al JSON
        email_meta = _load_emailmeta(archivo)
        if email_meta:
            result["email_meta"] = email_meta
            logger.debug(f"    email_meta fusionado: {email_meta.get('de', '')} | {email_meta.get('fecha', '')}")

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
    p = argparse.ArgumentParser(description="Paso 1: OCR con Azure Document Intelligence.")
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
