"""
src/processing/llm_azure.py
----------------------------
Envía el texto de una cotización al LLM desplegado en Azure AI Foundry
y retorna los campos extraídos como dict.

Usa la API REST de Azure OpenAI / AI Foundry (compatible con OpenAI format).
Endpoint esperado:
  Azure OpenAI:  https://<resource>.openai.azure.com/
  Serverless:    https://<endpoint>.inference.ai.azure.com/
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__, settings.LOG_LEVEL)


def _chat_url() -> str:
    base = settings.AZURE_LLM_ENDPOINT.rstrip("/")
    return (
        f"{base}/openai/deployments/{settings.AZURE_LLM_DEPLOYMENT}"
        f"/chat/completions?api-version={settings.AZURE_LLM_API_VERSION}"
    )


def _headers() -> dict[str, str]:
    return {
        "api-key": settings.AZURE_LLM_KEY,
        "Content-Type": "application/json",
    }


def _clean(raw: str) -> str:
    """Quita bloques ```json ... ``` si el modelo los incluye."""
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    return m.group(1).strip() if m else raw


@retry(
    retry=retry_if_exception_type(requests.HTTPError),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _call(system_prompt: str, user_content: str) -> str:
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
        "max_tokens":   settings.AZURE_LLM_MAX_TOKENS,
        "temperature":  settings.AZURE_LLM_TEMPERATURE,
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(_chat_url(), headers=_headers(), json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def run_llm(
    ocr_result: dict[str, Any],
    system_prompt: str,
) -> dict[str, Any]:
    """
    Procesa una cotización con el LLM.

    Args:
        ocr_result:    Resultado de azure_ocr.extract_pdf()
        system_prompt: Texto del prompt (leído desde prompts/)

    Returns:
        {
          file_name,
          llm_status: "success" | "error",
          campos: dict,          ← campos extraídos por el LLM
          error_message: str | None,
          raw_response: str,
        }
    """
    file_name = ocr_result.get("file_name", "unknown")
    logger.info(f"  LLM → {file_name}")

    out: dict[str, Any] = {
        "file_name":     file_name,
        "llm_status":    "error",
        "campos":        {},
        "error_message": None,
        "raw_response":  "",
    }

    full_text = ocr_result.get("full_text", "").strip()
    if not full_text:
        out["error_message"] = "Texto vacío, no se puede procesar"
        logger.warning(f"  ⚠ {file_name}: texto vacío")
        return out

    user_content = (
        f"Archivo: {file_name}\n\n"
        f"--- CONTENIDO ---\n{full_text}\n--- FIN ---"
    )

    try:
        raw = _call(system_prompt, user_content)
        out["raw_response"] = raw
        out["campos"]       = json.loads(_clean(raw))
        out["llm_status"]   = "success"
        logger.info(f"  ✓ {file_name} — {len(out['campos'])} campo(s)")
    except requests.HTTPError as exc:
        out["error_message"] = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        logger.error(f"  ✗ {file_name} — {out['error_message']}")
        raise
    except json.JSONDecodeError as exc:
        out["error_message"] = f"JSON inválido del LLM: {exc}"
        logger.error(f"  ✗ {file_name} — {out['error_message']}")
    except Exception as exc:  # noqa: BLE001
        out["error_message"] = str(exc)
        logger.error(f"  ✗ {file_name} — {exc}")

    return out
