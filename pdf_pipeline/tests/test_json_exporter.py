"""
tests/test_json_exporter.py
----------------------------
Pruebas unitarias para el exportador de resultados.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.output.json_exporter import (
    build_summary_table,
    export_individual_jsons,
    export_summary_table,
    _flatten_dict,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _extraction_doc(name: str, status: str = "success") -> dict:
    return {
        "file_name": name,
        "extraction_status": status,
        "page_count": 2,
        "pages": [{"page_number": 1, "text": "Cotización N° 001"}],
        "full_text": "Cotización N° 001\nProveedor: ACME SAC",
        "error_message": None,
    }


def _llm_result(name: str, fields: dict | None = None, status: str = "success") -> dict:
    return {
        "file_name": name,
        "llm_status": status,
        "extracted_fields": fields or {"numero_cotizacion": "001", "total": 1500.0},
        "error_message": None,
        "raw_response": "{}",
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFlattenDict:
    def test_flat_dict_unchanged(self):
        d = {"a": 1, "b": "hola"}
        assert _flatten_dict(d) == d

    def test_nested_dict_flattened(self):
        d = {"proveedor": {"nombre": "ACME", "ruc": "12345"}}
        flat = _flatten_dict(d)
        assert flat == {"proveedor.nombre": "ACME", "proveedor.ruc": "12345"}

    def test_list_joined_as_string(self):
        d = {"items": ["a", "b", "c"]}
        flat = _flatten_dict(d)
        assert flat["items"] == "a, b, c"


class TestBuildSummaryTable:
    def test_returns_dataframe(self):
        results = [_llm_result("a.pdf"), _llm_result("b.pdf")]
        df = build_summary_table(results)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_file_name_is_first_column(self):
        df = build_summary_table([_llm_result("x.pdf")])
        assert df.columns[0] == "file_name"

    def test_failed_llm_has_error_column(self):
        results = [_llm_result("bad.pdf", status="error")]
        results[0]["error_message"] = "Timeout"
        df = build_summary_table(results)
        assert "error_message" in df.columns

    def test_empty_results_returns_empty_df(self):
        df = build_summary_table([])
        assert df.empty


class TestExportIndividualJsons:
    def test_creates_one_json_per_doc(self, tmp_path):
        docs = [_extraction_doc("doc1.pdf"), _extraction_doc("doc2.pdf")]
        cls_map = {
            "doc1.pdf": {"is_cotizacion": True, "matched_keywords": ["cotización"]},
            "doc2.pdf": {"is_cotizacion": False, "matched_keywords": []},
        }
        llm_map = {
            "doc1.pdf": _llm_result("doc1.pdf"),
        }
        paths = export_individual_jsons(docs, cls_map, llm_map, output_dir=tmp_path)
        assert len(paths) == 2
        assert all(p.exists() for p in paths)

    def test_json_contains_all_sections(self, tmp_path):
        docs = [_extraction_doc("x.pdf")]
        cls_map = {"x.pdf": {"is_cotizacion": True}}
        llm_map = {"x.pdf": _llm_result("x.pdf")}

        paths = export_individual_jsons(docs, cls_map, llm_map, output_dir=tmp_path)
        content = json.loads(paths[0].read_text(encoding="utf-8"))

        assert "extraction" in content
        assert "classification" in content
        assert "llm_extraction" in content


class TestExportSummaryTable:
    def test_creates_csv_and_xlsx(self, tmp_path):
        results = [_llm_result("a.pdf"), _llm_result("b.pdf")]
        paths = export_summary_table(results, output_dir=tmp_path)

        assert paths["csv"].exists()
        assert paths["xlsx"].exists()

    def test_csv_has_correct_rows(self, tmp_path):
        results = [_llm_result("a.pdf"), _llm_result("b.pdf"), _llm_result("c.pdf")]
        paths = export_summary_table(results, output_dir=tmp_path)

        df = pd.read_csv(paths["csv"])
        assert len(df) == 3
