"""
step3_llm.py
-------------
PASO 3 — Pasa las cotizaciones por el LLM de Azure AI Foundry.

Por cada PDF en data/cotizaciones_encontradas/:
  - Lee su JSON de OCR (del paso 1) para obtener el texto
  - Lo envía al LLM con el prompt definido en prompts/prompt.txt
  - Guarda los campos extraídos como JSON en data/output/campos/
  - Al final genera tabla resumen CSV + XLSX en data/output/tables/

Requiere que los pasos 1 y 2 ya hayan corrido.

Output:
  data/output/campos/<nombre>_campos.json   (uno por cotización)
  data/output/tables/resumen.csv
  data/output/tables/resumen.xlsx

Uso:
  python step3_llm.py
  python step3_llm.py --prompt mi_prompt.txt
  python step3_llm.py --cotizaciones data/cotizaciones_encontradas
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from config import settings
from src.processing.llm_azure import run_llm
from src.utils.file_utils import save_json
from src.utils.logger import get_logger

logger = get_logger("paso4", settings.LOG_LEVEL)


def _load_ocr_json(file_name: str, json_dir: Path) -> dict | None:
    """Busca el JSON de OCR correspondiente al PDF."""
    stem = Path(file_name).stem
    candidate = json_dir / f"{stem}_ocr.json"
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    logger.warning(f"  ⚠ JSON de OCR no encontrado: {candidate}")
    return None


def _load_prompt(prompt_file: str) -> str:
    path = settings.PROMPTS_DIR / prompt_file
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt no encontrado: {path}\n"
            f"Crea el archivo con las instrucciones para el LLM."
        )
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(
            f"El archivo de prompt está vacío: {path}\n"
            f"Escribe las instrucciones y el JSON esperado."
        )
    return content


def _build_table(llm_results: list[dict]) -> pd.DataFrame:
    """Construye DataFrame aplanando los campos extraídos."""
    rows = []
    for r in llm_results:
        row = {"archivo": r["file_name"], "estado": r["llm_status"]}
        if r["llm_status"] == "success":
            row.update(_flatten(r["campos"]))
        else:
            row["error"] = r["error_message"]
        rows.append(row)
    df = pd.DataFrame(rows)
    # "archivo" y "estado" primero
    cols = ["archivo", "estado"] + [c for c in df.columns if c not in ("archivo", "estado")]
    return df[cols]


def _flatten(d: dict, parent: str = "", sep: str = ".") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{parent}{sep}{k}" if parent else k
        if isinstance(v, dict):
            out.update(_flatten(v, key, sep))
        elif isinstance(v, list):
            out[key] = ", ".join(str(i) for i in v)
        else:
            out[key] = v
    return out


def procesar(
    cotizaciones_dir: Path | None = None,
    json_dir: Path | None = None,
    campos_dir: Path | None = None,
    tables_dir: Path | None = None,
    prompt_file: str = "prompt.txt",
) -> dict:
    settings.ensure_dirs()
    src      = cotizaciones_dir or settings.COTIZACIONES_DIR
    ocr_dir  = json_dir         or settings.OUTPUT_OCR_DIR
    dst_camp = campos_dir       or settings.OUTPUT_CAMPOS_DIR
    dst_tbl  = tables_dir       or settings.OUTPUT_TABLES_DIR

    logger.info("=" * 60)
    logger.info("  PASO 4 — LLM Azure AI Foundry")
    logger.info("=" * 60)
    logger.info(f"  Cotizaciones : {src}")
    logger.info(f"  Prompt       : prompts/{prompt_file}")
    logger.info(f"  Modelo       : {settings.AZURE_LLM_DEPLOYMENT}")
    logger.info(f"  Campos JSON  : {dst_camp}")
    logger.info(f"  Tablas       : {dst_tbl}")

    # Cargar prompt
    try:
        system_prompt = _load_prompt(prompt_file)
    except (FileNotFoundError, ValueError) as exc:
        logger.error(f"[red]{exc}[/red]")
        sys.exit(1)

    pdfs = sorted(src.glob("*.pdf"))
    if not pdfs:
        logger.warning(f"No hay PDFs en {src}. ¿Corriste el paso 2?")
        return {"total": 0, "exitosos": 0, "errores": 0}

    logger.info(f"\nProcesando {len(pdfs)} cotización(es)…\n")

    llm_results = []

    for pdf in tqdm(pdfs, desc="LLM", unit="pdf"):
        # Recuperar el JSON de OCR del paso 1
        ocr_data = _load_ocr_json(pdf.name, ocr_dir)
        if ocr_data is None:
            llm_results.append({
                "file_name":     pdf.name,
                "llm_status":    "error",
                "campos":        {},
                "error_message": "JSON de OCR no encontrado — corre el paso 1 primero",
                "raw_response":  "",
            })
            continue

        # Llamar al LLM
        result = run_llm(ocr_data, system_prompt)
        llm_results.append(result)

        # Guardar JSON de campos por cotización
        save_json(result, dst_camp, f"{pdf.stem}_campos.json")

    # Tabla resumen
    df = _build_table(llm_results)
    csv_path  = dst_tbl / "resumen.csv"
    xlsx_path = dst_tbl / "resumen.xlsx"
    df.to_csv(csv_path,  index=False, encoding="utf-8-sig")
    df.to_excel(xlsx_path, index=False, engine="openpyxl")

    exitosos = sum(1 for r in llm_results if r["llm_status"] == "success")
    errores  = len(llm_results) - exitosos

    logger.info("\n" + "=" * 60)
    logger.info(f"  Total procesados : {len(pdfs)}")
    logger.info(f"  Exitosos         : [green]{exitosos}[/green]")
    logger.info(f"  Errores          : {errores}")
    logger.info(f"  JSONs de campos  : {dst_camp.name}/")
    logger.info(f"  Tabla CSV        : {csv_path.name}")
    logger.info(f"  Tabla XLSX       : {xlsx_path.name}")
    logger.info("=" * 60)

    return {
        "total":    len(pdfs),
        "exitosos": exitosos,
        "errores":  errores,
        "csv":      str(csv_path),
        "xlsx":     str(xlsx_path),
    }


def _args():
    p = argparse.ArgumentParser(description="Paso 3: procesar cotizaciones con LLM de Azure AI Foundry.")
    p.add_argument("--cotizaciones", type=Path, default=None, help="Carpeta con PDFs de cotizaciones")
    p.add_argument("--json-dir",     type=Path, default=None, help="Carpeta con JSONs del paso 1")
    p.add_argument("--campos-dir",   type=Path, default=None, help="Carpeta de salida para campos JSON")
    p.add_argument("--prompt",       type=str,  default="prompt.txt", help="Archivo de prompt")
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    try:
        settings.validate_paso3()
    except ValueError as exc:
        logger.error(f"[red]{exc}[/red]")
        sys.exit(1)
    r = procesar(
        cotizaciones_dir=args.cotizaciones,
        json_dir=args.json_dir,
        campos_dir=args.campos_dir,
        prompt_file=args.prompt,
    )
    sys.exit(0 if r["exitosos"] > 0 else 1)
