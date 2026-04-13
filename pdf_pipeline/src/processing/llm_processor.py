"""
src/processing/llm_processor.py
--------------------------------
Envía el texto de cada cotización a GPT-4.1-mini con el prompt
definido en prompts/ y parsea la respuesta como JSON estructurado.

El prompt debe instruir al modelo a devolver ÚNICAMENTE un objeto JSON
válido (sin texto adicional, sin bloques ```json```).
"""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from src.utils.file_utils import load_prompt
from src.utils.logger import get_logger

logger = get_logger(__name__, settings.LOG_LEVEL)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _clean_json_response(raw: str) -> str:
    """
    Limpia la respuesta del modelo para obtener JSON puro.
    Elimina bloques ```json ... ``` si el modelo los incluye por error.
    """
    raw = raw.strip()
    # Quitar bloque markdown si existe
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if match:
        return match.group(1).strip()
    return raw


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _call_llm(system_prompt: str, user_content: str) -> str:
    """Llama a la API de OpenAI y devuelve el texto de la respuesta."""
    response = _get_client().chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_tokens=settings.OPENAI_MAX_TOKENS,
        temperature=settings.OPENAI_TEMPERATURE,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},  # fuerza JSON válido
    )
    return response.choices[0].message.content or ""


def process_cotizacion(
    cotizacion_doc: dict[str, Any],
    prompt_file: str = "cotizacion_prompt.txt",
) -> dict[str, Any]:
    """
    Procesa un documento de cotización con el LLM.

    Args:
        cotizacion_doc: Resultado enriquecido de extracción + clasificación.
        prompt_file:    Nombre del archivo de prompt en prompts/.

    Returns:
        dict con:
          - file_name
          - llm_status: "success" | "error"
          - extracted_fields: dict con los campos extraídos por el LLM
          - error_message: str | None
          - raw_response: str (respuesta cruda del LLM, para debugging)
    """
    file_name: str = cotizacion_doc.get("file_name", "unknown")
    logger.info(f"  LLM → procesando: [bold]{file_name}[/bold]")

    result: dict[str, Any] = {
        "file_name": file_name,
        "llm_status": "error",
        "extracted_fields": {},
        "error_message": None,
        "raw_response": "",
    }

    try:
        system_prompt = load_prompt(prompt_file)
        full_text = cotizacion_doc.get("full_text", "")

        if not full_text.strip():
            result["error_message"] = "El documento no tiene texto extraído."
            return result

        # Construimos el mensaje de usuario con contexto
        user_content = (
            f"Nombre del archivo: {file_name}\n\n"
            f"--- CONTENIDO DEL DOCUMENTO ---\n{full_text}\n"
            f"--- FIN DEL CONTENIDO ---"
        )

        raw = _call_llm(system_prompt, user_content)
        result["raw_response"] = raw

        cleaned = _clean_json_response(raw)
        extracted = json.loads(cleaned)

        result["extracted_fields"] = extracted
        result["llm_status"] = "success"
        logger.info(f"  ✓ {file_name}: {len(extracted)} campo(s) extraído(s)")

    except FileNotFoundError as exc:
        result["error_message"] = str(exc)
        logger.error(f"  ✗ {file_name}: prompt no encontrado — {exc}")

    except json.JSONDecodeError as exc:
        result["error_message"] = f"No se pudo parsear JSON del LLM: {exc}"
        logger.error(f"  ✗ {file_name}: JSON inválido — {exc}")

    except Exception as exc:  # noqa: BLE001
        result["error_message"] = str(exc)
        logger.exception(f"  ✗ {file_name}: error LLM — {exc}")

    return result


def process_all_cotizaciones(
    cotizaciones: list[dict[str, Any]],
    prompt_file: str = "cotizacion_prompt.txt",
) -> list[dict[str, Any]]:
    """
    Procesa en secuencia todas las cotizaciones con el LLM.

    Returns:
        Lista de resultados LLM por documento.
    """
    logger.info(f"Procesando {len(cotizaciones)} cotización(es) con LLM…")
    results: list[dict[str, Any]] = []

    for doc in cotizaciones:
        llm_result = process_cotizacion(doc, prompt_file)
        results.append(llm_result)

    success = sum(1 for r in results if r["llm_status"] == "success")
    logger.info(f"LLM completado: {success}/{len(results)} exitosos.")
    return results
