"""
src/classification/document_classifier.py
------------------------------------------
Clasifica documentos como "cotización" o "otro" buscando keywords
en el texto extraído por OCR.

Estrategia — opción 3 (más robusta):
  1. Normaliza el texto: quita acentos, pasa a minúsculas
     → "Cotización", "COTIZACION", "cotizaciòn" (OCR con error) son equivalentes
  2. Usa raíces en las keywords (no palabras completas)
     → "cotiz" detecta cotizar, cotización, cotizaciones, cotizado, cotizando…
  3. \b solo al inicio del patrón
     → evita falsos positivos pero permite sufijos libres
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__, settings.LOG_LEVEL)


# ── Normalización ─────────────────────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    """
    Quita tildes/acentos y convierte a minúsculas.
    "Cotización" → "cotizacion"
    "PRESUPUÉSTO" → "presupuesto"
    "proformá"   → "proforma"   (OCR con error de tilde)
    """
    return (
        unicodedata.normalize("NFD", texto.lower())
        .encode("ascii", "ignore")
        .decode()
    )


# ── Compilar patrón con keywords normalizadas ─────────────────────────────────
# Se normaliza cada keyword igual que el texto → comparación siempre consistente
# Se usa \b solo al inicio para que "cotiz" matchee "cotización" (sufijo libre)

_KEYWORDS_NORM: list[str] = [_normalizar(kw) for kw in settings.COTIZACION_KEYWORDS]

# Separar keywords en dos grupos:
#   - raíces (una sola palabra): usan \b al inicio
#   - frases (contienen espacio): búsqueda literal sin \b
_stems  = [kw for kw in _KEYWORDS_NORM if " " not in kw]
_phrases = [kw for kw in _KEYWORDS_NORM if " " in kw]

_parts: list[str] = []
if _stems:
    _parts.append(r"\b(" + "|".join(re.escape(s) for s in _stems) + r")")
if _phrases:
    _parts.append(r"(" + "|".join(re.escape(p) for p in _phrases) + r")")

_PATTERN: re.Pattern = re.compile(
    "|".join(_parts),
    flags=re.IGNORECASE,
)


# ── Resultado ─────────────────────────────────────────────────────────────────

class ClassificationResult:
    def __init__(
        self,
        file_name:        str,
        is_cotizacion:    bool,
        matched_keywords: list[str],
        confidence_note:  str,
    ) -> None:
        self.file_name        = file_name
        self.is_cotizacion    = is_cotizacion
        self.matched_keywords = matched_keywords
        self.confidence_note  = confidence_note

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name":        self.file_name,
            "is_cotizacion":    self.is_cotizacion,
            "matched_keywords": self.matched_keywords,
            "confidence_note":  self.confidence_note,
        }

    def __repr__(self) -> str:
        label = "COTIZACIÓN" if self.is_cotizacion else "OTRO"
        return f"<ClassificationResult [{label}] file={self.file_name!r} keywords={self.matched_keywords}>"


# ── Clasificador ──────────────────────────────────────────────────────────────

def classify_document(extraction_result: dict[str, Any]) -> ClassificationResult:
    """
    Clasifica un documento como cotización o no.

    Proceso:
      1. Lee full_text del resultado de OCR
      2. Normaliza (sin acentos, minúsculas)
      3. Busca raíces de keywords en el texto normalizado
      4. Retorna ClassificationResult con veredicto y matches encontrados
    """
    file_name: str = extraction_result.get("file_name", "unknown")

    if extraction_result.get("extraction_status") != "success":
        logger.warning(f"  ⚠ {file_name}: extracción fallida, marcado como OTRO.")
        return ClassificationResult(
            file_name=file_name,
            is_cotizacion=False,
            matched_keywords=[],
            confidence_note="Extracción fallida, no clasificable.",
        )

    raw_text:  str = extraction_result.get("full_text", "")
    norm_text: str = _normalizar(raw_text)

    matches = _PATTERN.findall(norm_text)

    # Cada match es un tuple de grupos; extraer el grupo no vacío
    seen: set[str] = set()
    unique_matches: list[str] = []
    for m in matches:
        # m es un tuple, tomar el primer grupo no vacío
        if isinstance(m, tuple):
            key = next((g for g in m if g), None)
        else:
            key = m
        if key:
            key = key.lower()
            if key not in seen:
                seen.add(key)
                unique_matches.append(key)

    is_cotizacion = len(unique_matches) > 0

    if is_cotizacion:
        note = (
            f"Encontradas {len(matches)} coincidencia(s) "
            f"de {len(unique_matches)} keyword(s) única(s)."
        )
        logger.info(f"  → {file_name}: [green]COTIZACIÓN[/green] — {unique_matches}")
    else:
        note = "Ninguna keyword encontrada (texto normalizado)."
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
    """Filtra y retorna solo los documentos clasificados como cotización."""
    logger.info(f"Clasificando {len(extraction_results)} documento(s)…")

    all_classifications: list[ClassificationResult] = []
    cotizaciones:        list[dict[str, Any]]        = []

    for doc in extraction_results:
        cls = classify_document(doc)
        all_classifications.append(cls)
        if cls.is_cotizacion:
            cotizaciones.append({**doc, "classification": cls.to_dict()})

    logger.info(
        f"Clasificación completa: "
        f"[green]{len(cotizaciones)} cotización(es)[/green] de "
        f"{len(extraction_results)} documento(s)."
    )
    return cotizaciones, all_classifications
