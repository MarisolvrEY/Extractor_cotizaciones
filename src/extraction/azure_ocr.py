"""
src/extraction/azure_ocr.py
----------------------------
Extrae el contenido de un PDF usando Azure AI Content Understanding
(Azure AI Foundry — REST API).

Flujo:
  1. POST  .../analyzers/<analyzer-id>:analyze  →  recibe resultId
  2. GET   .../analyzers/<analyzer-id>/results/<resultId>  (polling)
  3. Cuando status == "Succeeded" → parsear y retornar texto + páginas
"""
from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__, settings.LOG_LEVEL)

_POLL_TIMEOUT  = 120   # segundos máximos esperando el job
_POLL_INTERVAL = 3     # segundos entre cada consulta


def _headers() -> dict[str, str]:
    return {
        "Ocp-Apim-Subscription-Key": settings.AZURE_OCR_KEY,
        "Content-Type": "application/json",
    }


def _url_analyze() -> str:
    base = settings.AZURE_OCR_ENDPOINT.rstrip("/")
    return (
        f"{base}/contentunderstanding/analyzers/"
        f"{settings.AZURE_OCR_ANALYZER}:analyze"
        f"?api-version={settings.AZURE_OCR_API_VERSION}"
    )


def _url_result(result_id: str) -> str:
    base = settings.AZURE_OCR_ENDPOINT.rstrip("/")
    return (
        f"{base}/contentunderstanding/analyzers/"
        f"{settings.AZURE_OCR_ANALYZER}/results/{result_id}"
        f"?api-version={settings.AZURE_OCR_API_VERSION}"
    )


@retry(
    retry=retry_if_exception_type(requests.HTTPError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _submit(pdf_bytes: bytes) -> str:
    """Envía el PDF y retorna el resultId del job asíncrono."""
    payload = {"base64Source": base64.b64encode(pdf_bytes).decode()}
    resp = requests.post(_url_analyze(), headers=_headers(), json=payload, timeout=60)
    resp.raise_for_status()

    result_id = (
        resp.headers.get("Operation-Id")
        or resp.headers.get("operation-id")
        or resp.json().get("id", "")
    )
    if not result_id:
        raise ValueError(f"No se recibió resultId. Headers: {dict(resp.headers)}")
    return result_id


def _poll(result_id: str) -> dict[str, Any]:
    """Espera y retorna el body completo cuando el job termina."""
    elapsed = 0
    while elapsed < _POLL_TIMEOUT:
        resp = requests.get(_url_result(result_id), headers=_headers(), timeout=30)
        resp.raise_for_status()
        body = resp.json()
        status = body.get("status", "").lower()

        if status == "succeeded":
            return body
        if status in ("failed", "canceled"):
            err = body.get("error", {}).get("message", "sin detalle")
            raise RuntimeError(f"Job {result_id} terminó en estado '{status}': {err}")

        logger.debug(f"    polling {elapsed}s — {status}")
        time.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

    raise TimeoutError(f"Job {result_id} no terminó en {_POLL_TIMEOUT}s")


def _parse(body: dict[str, Any]) -> tuple[str, list[dict]]:
    """Extrae full_text y lista de páginas del body de respuesta."""
    full_lines: list[str] = []
    pages: list[dict] = []

    # Formato Content Understanding (AI Foundry)
    contents = body.get("result", {}).get("contents", [])
    if contents:
        for item in contents:
            page_num  = item.get("pageNumber", len(pages) + 1)
            page_text = item.get("markdown", item.get("text", ""))
            full_lines.append(page_text)
            pages.append({"page_number": page_num, "text": page_text})
    else:
        # Fallback: formato analyzeResult (Document Intelligence)
        for page in body.get("analyzeResult", {}).get("pages", []):
            lines = [ln.get("content", "") for ln in page.get("lines", [])]
            page_text = "\n".join(lines)
            full_lines.extend(lines)
            pages.append({
                "page_number": page.get("pageNumber", len(pages) + 1),
                "width": page.get("width"),
                "height": page.get("height"),
                "text": page_text,
            })

    return "\n".join(full_lines), pages


def extract_pdf(pdf_path: Path) -> dict[str, Any]:
    """
    Extrae texto de un PDF con Azure AI Content Understanding.

    Returns dict:
      file_name, full_text, pages, page_count,
      analyzer_id, extraction_status, error_message
    """
    logger.info(f"  OCR → {pdf_path.name}")
    result: dict[str, Any] = {
        "file_name":         pdf_path.name,
        "full_text":         "",
        "pages":             [],
        "page_count":        0,
        "analyzer_id":       settings.AZURE_OCR_ANALYZER,
        "extraction_status": "error",
        "error_message":     None,
    }
    try:
        result_id = _submit(pdf_path.read_bytes())
        body      = _poll(result_id)
        full_text, pages = _parse(body)
        result.update({
            "full_text":         full_text,
            "pages":             pages,
            "page_count":        len(pages),
            "extraction_status": "success",
        })
        logger.info(f"  ✓ {pdf_path.name} — {len(pages)} pág.")
    except FileNotFoundError:
        result["error_message"] = f"Archivo no encontrado: {pdf_path}"
        logger.error(result["error_message"])
    except requests.HTTPError as exc:
        result["error_message"] = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        logger.error(f"  ✗ {pdf_path.name} — {result['error_message']}")
        raise
    except Exception as exc:  # noqa: BLE001
        result["error_message"] = str(exc)
        logger.error(f"  ✗ {pdf_path.name} — {exc}")
    return result
