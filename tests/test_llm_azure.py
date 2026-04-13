"""
tests/test_llm_azure.py
------------------------
Tests para el procesador LLM de Azure AI Foundry.
Usa mocks — no consume créditos reales.
"""
import json
from unittest.mock import patch
import pytest
from src.processing.llm_azure import run_llm, _clean


class TestClean:
    def test_strips_markdown(self):
        assert _clean('```json\n{"k": 1}\n```') == '{"k": 1}'

    def test_plain_json_unchanged(self):
        assert _clean('{"k": 1}') == '{"k": 1}'


class TestRunLlm:
    def _doc(self, name="cot.pdf", text="Proforma N°001 Total: 500"):
        return {"file_name": name, "full_text": text, "extraction_status": "success"}

    @patch("src.processing.llm_azure._call")
    def test_success(self, mock_call):
        mock_call.return_value = '{"total": 500}'
        r = run_llm(self._doc(), "Extrae campos.")
        assert r["llm_status"] == "success"
        assert r["campos"]["total"] == 500

    @patch("src.processing.llm_azure._call")
    def test_invalid_json(self, mock_call):
        mock_call.return_value = "esto no es json"
        r = run_llm(self._doc(), "Extrae campos.")
        assert r["llm_status"] == "error"

    def test_empty_text(self):
        doc = self._doc(text="   ")
        r = run_llm(doc, "Extrae campos.")
        assert r["llm_status"] == "error"
