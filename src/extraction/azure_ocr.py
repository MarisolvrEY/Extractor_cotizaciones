"""
src/extraction/azure_ocr.py
----------------------------
Extrae el contenido de un archivo usando Azure Document Intelligence
(REST API — compatible con endpoints services.ai.azure.com y cognitiveservices.azure.com).

Flujo:
  1. POST  .../documentintelligence/documentModels/<model>:analyze  → resultId
  2. GET   .../documentintelligence/documentModels/<model>/analyzeResults/<resultId>
  3. Cuando status == "succeeded" → parsear y retornar texto + páginas
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

_POLL_TIMEOUT  = 120
_POLL_INTERVAL = 3


def _headers() -> dict[str, str]:
    return {
        "Ocp-Apim-Subscription-Key": settings.AZURE_OCR_KEY,
        "Content-Type": "application/json",
    }


def _url_analyze() -> str:
    base  = settings.AZURE_OCR_ENDPOINT.rstrip("/")
    model = settings.AZURE_OCR_ANALYZER
    ver   = settings.AZURE_OCR_API_VERSION
    return f"{base}/documentintelligence/documentModels/{model}:analyze?api-version={ver}"


def _url_result(result_id: str) -> str:
    base  = settings.AZURE_OCR_ENDPOINT.rstrip("/")
    model = settings.AZURE_OCR_ANALYZER
    ver   = settings.AZURE_OCR_API_VERSION
    return f"{base}/documentintelligence/documentModels/{model}/analyzeResults/{result_id}?api-version={ver}"


@retry(
    retry=retry_if_exception_type(requests.HTTPError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _submit(file_bytes: bytes) -> str:
    """Envía el archivo y retorna el resultId del job asíncrono."""
    b64     = base64.b64encode(file_bytes).decode()
    payload = {"base64Source": b64}

    resp = requests.post(_url_analyze(), headers=_headers(), json=payload, timeout=60)
    resp.raise_for_status()

    # El resultId viene en el header Operation-Location como última parte de la URL
    op_location = resp.headers.get("Operation-Location", "")
    if op_location:
        result_id = op_location.rstrip("/").split("/")[-1].split("?")[0]
        if result_id:
            return result_id

    # Fallback: header directo
    result_id = resp.headers.get("apim-request-id", "")
    if result_id:
        return result_id

    raise ValueError(
        f"No se recibió resultId.\n"
        f"Headers: {dict(resp.headers)}\n"
        f"Body: {resp.text[:300]}"
    )


def _poll(result_id: str) -> dict[str, Any]:
    """Espera y retorna el body completo cuando el job termina."""
    url     = _url_result(result_id)
    elapsed = 0

    while elapsed < _POLL_TIMEOUT:
        resp   = requests.get(url, headers=_headers(), timeout=30)
        resp.raise_for_status()
        body   = resp.json()
        status = body.get("status", "").lower()

        if status == "succeeded":
            return body
        if status in ("failed", "canceled"):
            err = body.get("error", {}).get("message", "sin detalle")
            raise RuntimeError(f"Job '{status}': {err}")

        logger.debug(f"    polling {elapsed}s — {status}")
        time.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

    raise TimeoutError(f"Job no terminó en {_POLL_TIMEOUT}s")


def _parse(body: dict[str, Any]) -> tuple[str, list[dict]]:
    """Extrae full_text y lista de páginas del body de Document Intelligence."""
    full_lines: list[str] = []
    pages:      list[dict] = []

    for page in body.get("analyzeResult", {}).get("pages", []):
        lines     = [ln.get("content", "") for ln in page.get("lines", [])]
        page_text = "\n".join(lines)
        full_lines.extend(lines)
        pages.append({
            "page_number": page.get("pageNumber", len(pages) + 1),
            "width":       page.get("width"),
            "height":      page.get("height"),
            "text":        page_text,
        })

    return "\n".join(full_lines), pages


def extract_pdf(file_path: Path) -> dict[str, Any]:
    """
    Extrae texto de un archivo con Azure Document Intelligence.

    Returns:
        { file_name, full_text, pages, page_count,
          analyzer_id, extraction_status, error_message }
    """
    logger.info(f"  OCR → {file_path.name}")

    result: dict[str, Any] = {
        "file_name":         file_path.name,
        "full_text":         "",
        "pages":             [],
        "page_count":        0,
        "analyzer_id":       settings.AZURE_OCR_ANALYZER,
        "extraction_status": "error",
        "error_message":     None,
    }

    try:
        result_id         = _submit(file_path.read_bytes())
        body              = _poll(result_id)
        full_text, pages  = _parse(body)
        result.update({
            "full_text":         full_text,
            "pages":             pages,
            "page_count":        len(pages),
            "extraction_status": "success",
        })
        logger.info(f"  ✓ {file_path.name} — {len(pages)} pág.")

    except FileNotFoundError:
        result["error_message"] = f"Archivo no encontrado: {file_path}"
        logger.error(result["error_message"])

    except requests.HTTPError as exc:
        result["error_message"] = (
            f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        )
        logger.error(f"  ✗ {file_path.name} — {result['error_message']}")
        raise

    except Exception as exc:  # noqa: BLE001
        result["error_message"] = str(exc)
        logger.error(f"  ✗ {file_path.name} — {exc}")

    return result
