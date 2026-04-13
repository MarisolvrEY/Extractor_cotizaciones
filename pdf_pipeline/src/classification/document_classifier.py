"""
src/classification/document_classifier.py
------------------------------------------
Clasifica documentos extraídos como "cotización" o "otro"
basándose en la presencia de palabras clave en el texto completo.

La lógica es deliberadamente simple y determinista (sin IA) para
que sea rápida, trazable y no dependa de llamadas externas.
"""

from __future__ import annotations

import re
from typing import Any

from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__, settings.LOG_LEVEL)

# Pre-compila el patrón con todas las keywords (case-insensitive)
_KEYWORDS_PATTERN: re.Pattern = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in settings.COTIZACION_KEYWORDS) + r")\b",
    flags=re.IGNORECASE,
)


class ClassificationResult:
    """Resultado inmutable de la clasificación de un documento."""

    def __init__(
        self,
        file_name: str,
        is_cotizacion: bool,
        matched_keywords: list[str],
        confidence_note: str,
    ) -> None:
        self.file_name = file_name
        self.is_cotizacion = is_cotizacion
        self.matched_keywords = matched_keywords
        self.confidence_note = confidence_note

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "is_cotizacion": self.is_cotizacion,
            "matched_keywords": self.matched_keywords,
            "confidence_note": self.confidence_note,
        }

    def __repr__(self) -> str:
        label = "COTIZACIÓN" if self.is_cotizacion else "OTRO"
        return (
            f"<ClassificationResult [{label}] "
            f"file={self.file_name!r} "
            f"keywords={self.matched_keywords}>"
        )


def classify_document(extraction_result: dict[str, Any]) -> ClassificationResult:
    """
    Analiza el texto de un documento extraído y decide si es una cotización.

    Args:
        extraction_result: Salida de azure_ocr.extract_pdf()

    Returns:
        ClassificationResult con veredicto y keywords encontradas.
    """
    file_name: str = extraction_result.get("file_name", "unknown")

    # Si la extracción falló, no se puede clasificar
    if extraction_result.get("extraction_status") != "success":
        logger.warning(f"  ⚠ {file_name}: extracción fallida, marcado como OTRO.")
        return ClassificationResult(
            file_name=file_name,
            is_cotizacion=False,
            matched_keywords=[],
            confidence_note="Extracción fallida, no clasificable.",
        )

    full_text: str = extraction_result.get("full_text", "")
    matches = _KEYWORDS_PATTERN.findall(full_text)

    # Dedup preservando orden de aparición
    seen: set[str] = set()
    unique_matches: list[str] = []
    for m in matches:
        key = m.lower()
        if key not in seen:
            seen.add(key)
            unique_matches.append(m.lower())

    is_cotizacion = len(unique_matches) > 0

    if is_cotizacion:
        note = f"Encontradas {len(matches)} coincidencia(s) de {len(unique_matches)} keyword(s) única(s)."
        logger.info(f"  → {file_name}: [green]COTIZACIÓN[/green] — {unique_matches}")
    else:
        note = "Ninguna keyword de cotización encontrada."
        logger.info(f"  → {file_name}: [dim]OTRO[/dim]")

    return ClassificationResult(
        file_name=file_name,
        is_cotizacion=is_cotizacion,
        matched_keywords=unique_matches,
        confidence_note=note,
    )


def filter_cotizaciones(
    extraction_results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[ClassificationResult]]:
    """
    Filtra una lista de resultados de extracción y retorna solo los
    documentos clasificados como cotización.

    Returns:
        (cotizaciones, all_classifications)
        - cotizaciones: subconjunto de extraction_results que son cotizaciones
        - all_classifications: clasificación de TODOS los documentos
    """
    logger.info(f"Clasificando {len(extraction_results)} documento(s)…")

    all_classifications: list[ClassificationResult] = []
    cotizaciones: list[dict[str, Any]] = []

    for doc in extraction_results:
        cls = classify_document(doc)
        all_classifications.append(cls)
        if cls.is_cotizacion:
            # Enriquecemos el doc con metadatos de clasificación
            cotizaciones.append({**doc, "classification": cls.to_dict()})

    logger.info(
        f"Clasificación completa: "
        f"[green]{len(cotizaciones)} cotización(es)[/green] de "
        f"{len(extraction_results)} documento(s)."
    )
    return cotizaciones, all_classifications
