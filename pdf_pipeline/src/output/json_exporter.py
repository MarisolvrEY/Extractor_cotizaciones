"""
src/output/json_exporter.py
----------------------------
Genera los artefactos de salida del pipeline:

1. JSON individual por PDF procesado (extracción + clasificación + LLM).
2. Tabla resumen en CSV y XLSX con los campos extraídos por el LLM.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from config import settings
from src.utils.file_utils import save_json
from src.utils.logger import get_logger

logger = get_logger(__name__, settings.LOG_LEVEL)


# ─────────────────────────────────────────────────────────────────────────────
# JSON individuales
# ─────────────────────────────────────────────────────────────────────────────

def export_individual_jsons(
    extraction_results: list[dict[str, Any]],
    classification_map: dict[str, dict[str, Any]],
    llm_results_map: dict[str, dict[str, Any]],
    output_dir: Path | None = None,
) -> list[Path]:
    """
    Escribe un JSON por cada PDF procesado con toda la información disponible:
      - Datos de extracción (texto, páginas)
      - Resultado de clasificación
      - Campos extraídos por el LLM (si aplica)

    Args:
        extraction_results:  Lista de dicts de azure_ocr.
        classification_map:  {file_name: ClassificationResult.to_dict()}
        llm_results_map:     {file_name: resultado LLM} (solo cotizaciones)
        output_dir:          Directorio de salida (default: settings.OUTPUT_JSON_DIR)

    Returns:
        Lista de Paths de los JSON generados.
    """
    dest = output_dir or settings.OUTPUT_JSON_DIR
    generated: list[Path] = []

    for doc in extraction_results:
        file_name: str = doc["file_name"]
        stem = Path(file_name).stem

        # Unimos todo en un único documento
        combined: dict[str, Any] = {
            "file_name": file_name,
            "extraction": {
                "status": doc.get("extraction_status"),
                "page_count": doc.get("page_count", 0),
                "pages": doc.get("pages", []),
                "full_text": doc.get("full_text", ""),
                "error_message": doc.get("error_message"),
            },
            "classification": classification_map.get(file_name, {}),
            "llm_extraction": llm_results_map.get(file_name, None),
        }

        path = save_json(combined, dest, f"{stem}.json")
        generated.append(path)

    logger.info(f"JSON individuales generados: {len(generated)} archivo(s) en {dest}")
    return generated


# ─────────────────────────────────────────────────────────────────────────────
# Tabla resumen
# ─────────────────────────────────────────────────────────────────────────────

def build_summary_table(
    llm_results: list[dict[str, Any]],
) -> pd.DataFrame:
    """
    Construye un DataFrame con una fila por cotización procesada.
    Las columnas serán: file_name + todos los campos que devolvió el LLM.
    Se tolera que distintos documentos tengan campos ligeramente distintos
    (se usa pd.json_normalize + union de columnas).
    """
    rows: list[dict[str, Any]] = []

    for r in llm_results:
        row: dict[str, Any] = {"file_name": r["file_name"], "llm_status": r["llm_status"]}
        if r["llm_status"] == "success":
            fields = r.get("extracted_fields", {})
            # Aplanamos un nivel de anidamiento si fuera necesario
            flat = _flatten_dict(fields)
            row.update(flat)
        else:
            row["error_message"] = r.get("error_message", "")
        rows.append(row)

    df = pd.DataFrame(rows)

    # file_name y llm_status primero
    priority_cols = ["file_name", "llm_status"]
    other_cols = [c for c in df.columns if c not in priority_cols]
    df = df[priority_cols + other_cols]

    return df


def export_summary_table(
    llm_results: list[dict[str, Any]],
    output_dir: Path | None = None,
    filename_stem: str = "resumen_cotizaciones",
) -> dict[str, Path]:
    """
    Exporta la tabla resumen a CSV y XLSX.

    Returns:
        {"csv": Path, "xlsx": Path}
    """
    dest = output_dir or settings.OUTPUT_TABLES_DIR
    dest.mkdir(parents=True, exist_ok=True)

    df = build_summary_table(llm_results)

    csv_path = dest / f"{filename_stem}.csv"
    xlsx_path = dest / f"{filename_stem}.xlsx"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")  # utf-8-sig para Excel
    df.to_excel(xlsx_path, index=False, engine="openpyxl")

    logger.info(f"Tabla resumen: {len(df)} fila(s)")
    logger.info(f"  CSV  → {csv_path}")
    logger.info(f"  XLSX → {xlsx_path}")

    return {"csv": csv_path, "xlsx": xlsx_path}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _flatten_dict(
    d: dict[str, Any],
    parent_key: str = "",
    sep: str = ".",
) -> dict[str, Any]:
    """
    Aplana un dict anidado un nivel.
    Ejemplo: {"proveedor": {"nombre": "ACME"}} → {"proveedor.nombre": "ACME"}
    """
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        elif isinstance(v, list):
            items.append((new_key, ", ".join(str(i) for i in v)))
        else:
            items.append((new_key, v))
    return dict(items)
