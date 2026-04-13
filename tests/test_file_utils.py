"""
tests/test_file_utils.py
------------------------
Pruebas unitarias para utilidades de archivos.
"""

import json
from pathlib import Path

import pytest

from src.utils.file_utils import collect_files, save_json, load_json, load_prompt


class TestCollectPdfs:
    def test_returns_only_pdfs(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"%PDF")
        (tmp_path / "b.pdf").write_bytes(b"%PDF")
        (tmp_path / "notas.txt").write_text("hola")
        result = collect_files(tmp_path)
        assert len(result) == 2
        assert all(p.suffix == ".pdf" for p in result)

    def test_empty_dir_returns_empty_list(self, tmp_path):
        result = collect_files(tmp_path)
        assert result == []

    def test_skips_oversized_files(self, tmp_path, monkeypatch):
        big_pdf = tmp_path / "grande.pdf"
        big_pdf.write_bytes(b"%PDF" + b"0" * 10)

        # Simulamos que el límite es 0 MB
        monkeypatch.setattr(
            "src.utils.file_utils.MAX_BYTES", 0
        )
        result = collect_files(tmp_path)
        assert result == []


class TestSaveLoadJson:
    def test_save_and_load_roundtrip(self, tmp_path):
        data = {"campo": "valor", "numero": 42, "lista": [1, 2, 3]}
        path = save_json(data, tmp_path, "test_output.json")

        assert path.exists()
        loaded = load_json(path)
        assert loaded == data

    def test_adds_json_extension(self, tmp_path):
        path = save_json({"x": 1}, tmp_path, "sin_extension")
        assert path.name == "sin_extension.json"

    def test_unicode_preserved(self, tmp_path):
        data = {"descripción": "Ñoño cotización", "precio": "S/ 150.00"}
        path = save_json(data, tmp_path, "unicode_test.json")
        loaded = load_json(path)
        assert loaded["descripción"] == "Ñoño cotización"


class TestLoadPrompt:
    def test_loads_existing_prompt(self, tmp_path, monkeypatch):
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("Extrae los datos del documento.", encoding="utf-8")

        monkeypatch.setattr("src.utils.file_utils.settings.PROMPTS_DIR", tmp_path)
        result = load_prompt("test_prompt.txt")
        assert result == "Extrae los datos del documento."

    def test_raises_if_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.file_utils.settings.PROMPTS_DIR", tmp_path)
        with pytest.raises(FileNotFoundError):
            load_prompt("inexistente.txt")
