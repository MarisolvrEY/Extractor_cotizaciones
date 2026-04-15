"""
step3_metadatos.py
-------------------
PASO 3 — Extrae metadatos de todos los archivos en data/cotizaciones_encontradas/.

Output:
  data/output/metadatos/metadata.xlsx          ← nombre configurable en .env → METADATA_XLSX
  data/output/metadatos/<nombre>_meta.json     ← uno por archivo

Uso:
  python step3_metadatos.py
  python step3_metadatos.py --excel mi_inventario
  python step3_metadatos.py --origen data/cotizaciones_encontradas
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config import settings
from src.utils.file_utils import save_json
from src.utils.logger import get_logger

logger = get_logger("paso3", settings.LOG_LEVEL)


def extraer_metadatos(
    origen_dir:  Path | None = None,
    output_dir:  Path | None = None,
    nombre_xlsx: str = "",
) -> dict:
    settings.ensure_dirs()
    src  = origen_dir or settings.COTIZACIONES_DIR
    dst  = output_dir or settings.OUTPUT_METADATOS_DIR
    nombre = nombre_xlsx or settings.METADATA_XLSX_NAME
    dst.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("  PASO 3 — Extracción de metadatos")
    logger.info("=" * 60)
    logger.info(f"  Origen  : {src}")
    logger.info(f"  Salida  : {dst}")
    logger.info(f"  Excel   : {nombre}.xlsx")

    archivos = sorted(f for f in src.iterdir() if f.is_file() and not f.name.startswith("."))
    if not archivos:
        logger.warning(f"No hay archivos en {src}. ¿Corriste el paso 2?")
        return {"total": 0, "exitosos": 0, "errores": 0}

    logger.info(f"\nAnalizando {len(archivos)} archivo(s)…\n")

    try:
        from src.metadata.extractor import extract_all, build_excel
    except ImportError as exc:
        logger.error(f"[red]Error importando extractor: {exc}[/red]")
        return {"total": 0, "exitosos": 0, "errores": 1}

    records  = []
    exitosos = 0
    errores  = 0

# DESPUÉS
    ocr_dir = settings.OUTPUT_OCR_DIR

    for archivo in archivos:
        logger.info(f"  → {archivo.name}")
        try:
            meta = extract_all(str(archivo))

            # Fusionar email_meta si existe en el OCR JSON
            ocr_json = ocr_dir / f"{archivo.stem}_ocr.json"
            if ocr_json.exists():
                import json as _json
                ocr_data = _json.loads(ocr_json.read_text(encoding="utf-8"))
                email_meta = ocr_data.get("email_meta")
                if email_meta:
                    meta["email_remitente"] = email_meta.get("de", "")
                    meta["email_destinatario"] = email_meta.get("para", "")
                    meta["email_asunto"]    = email_meta.get("asunto", "")
                    meta["email_fecha"]     = email_meta.get("fecha", "")
                    meta["email_origen"]    = email_meta.get("origen", "")

            records.append(meta)
            save_json(meta, dst, f"{archivo.stem}_meta.json")
            exitosos += 1
        except Exception as exc:
            logger.warning(f"  ⚠ {archivo.name}: {exc}")
            records.append({"fs_nombre_archivo": archivo.name, "error_general": str(exc)})
            errores += 1

    # Excel con nombre configurable
    xlsx_path = dst / f"{nombre}.xlsx"
    try:
        build_excel(records, str(xlsx_path))
        logger.info(f"\n  Excel → {xlsx_path}")
    except Exception as exc:
        logger.error(f"  ✗ No se pudo generar Excel: {exc}")

    logger.info("\n" + "=" * 60)
    logger.info(f"  Total    : {len(archivos)}")
    logger.info(f"  Exitosos : [green]{exitosos}[/green]")
    logger.info(f"  Errores  : {errores}")
    logger.info("=" * 60)

    return {"total": len(archivos), "exitosos": exitosos, "errores": errores, "xlsx": str(xlsx_path)}


def _args():
    p = argparse.ArgumentParser(description="Paso 3: extraer metadatos de cotizaciones.")
    p.add_argument("--origen", type=Path, default=None,
                   help="Carpeta con los archivos (default: data/cotizaciones_encontradas)")
    p.add_argument("--excel",  type=str,  default="",
                   help=f"Nombre del Excel sin .xlsx (default: {settings.METADATA_XLSX_NAME!r} según .env)")
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    r = extraer_metadatos(origen_dir=args.origen, nombre_xlsx=args.excel)
    sys.exit(0 if r["exitosos"] > 0 else 1)
