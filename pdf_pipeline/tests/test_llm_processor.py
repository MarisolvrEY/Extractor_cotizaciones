"""
tests/test_llm_processor.py
----------------------------
Pruebas unitarias para el procesador LLM.
Usa mocks para no consumir créditos de OpenAI.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.processing.llm_processor import _clean_json_response, process_cotizacion


class TestCleanJsonResponse:
    def test_strips_markdown_block(self):
        raw = '```json\n{"key": "value"}\n```'
        assert _clean_json_response(raw) == '{"key": "value"}'

    def test_strips_plain_markdown_block(self):
        raw = '```\n{"key": "value"}\n```'
        assert _clean_json_response(raw) == '{"key": "value"}'

    def test_plain_json_unchanged(self):
        raw = '{"key": "value"}'
        assert _clean_json_response(raw) == raw

    def test_strips_whitespace(self):
        raw = '   {"key": "value"}   '
        assert _clean_json_response(raw) == '{"key": "value"}'


class TestProcessCotizacion:
    def _make_doc(self, name: str = "cotizacion.pdf") -> dict:
        return {
            "file_name": name,
            "full_text": "Proforma N° 001\nProveedor: ACME\nTotal: 5000",
            "extraction_status": "success",
            "classification": {"is_cotizacion": True},
        }

    @patch("src.processing.llm_processor.load_prompt")
    @patch("src.processing.llm_processor._call_llm")
    def test_successful_extraction(self, mock_llm, mock_prompt):
        mock_prompt.return_value = "Extrae los datos del documento."
        expected = {"numero_cotizacion": "001", "total": 5000.0}
        mock_llm.return_value = json.dumps(expected)

        result = process_cotizacion(self._make_doc())

        assert result["llm_status"] == "success"
        assert result["extracted_fields"] == expected
        assert result["error_message"] is None

    @patch("src.processing.llm_processor.load_prompt")
    @patch("src.processing.llm_processor._call_llm")
    def test_handles_invalid_json_response(self, mock_llm, mock_prompt):
        mock_prompt.return_value = "Prompt de prueba."
        mock_llm.return_value = "Esto no es JSON válido"

        result = process_cotizacion(self._make_doc())

        assert result["llm_status"] == "error"
        assert "JSON" in result["error_message"]

    @patch("src.processing.llm_processor.load_prompt")
    def test_handles_missing_prompt_file(self, mock_prompt):
        mock_prompt.side_effect = FileNotFoundError("Prompt no encontrado")

        result = process_cotizacion(self._make_doc())

        assert result["llm_status"] == "error"

    @patch("src.processing.llm_processor.load_prompt")
    def test_handles_empty_text(self, mock_prompt):
        mock_prompt.return_value = "Prompt de prueba."
        doc = self._make_doc()
        doc["full_text"] = "   "

        result = process_cotizacion(doc)

        assert result["llm_status"] == "error"
        assert "texto" in result["error_message"].lower()

    @patch("src.processing.llm_processor.load_prompt")
    @patch("src.processing.llm_processor._call_llm")
    def test_handles_markdown_wrapped_json(self, mock_llm, mock_prompt):
        mock_prompt.return_value = "Prompt."
        expected = {"total": 999.0}
        mock_llm.return_value = f'```json\n{json.dumps(expected)}\n```'

        result = process_cotizacion(self._make_doc())

        assert result["llm_status"] == "success"
        assert result["extracted_fields"] == expected
