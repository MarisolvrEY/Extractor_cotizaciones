"""
tests/test_classifier.py
------------------------
Pruebas unitarias para el clasificador de documentos.
No requieren credenciales externas.
"""

import pytest

from src.classification.document_classifier import classify_document, filter_cotizaciones


def _make_doc(file_name: str, text: str, status: str = "success") -> dict:
    return {
        "file_name": file_name,
        "full_text": text,
        "extraction_status": status,
        "page_count": 1,
        "pages": [],
    }


class TestClassifyDocument:
    def test_detects_proforma(self):
        doc = _make_doc("doc1.pdf", "Esta es una PROFORMA de servicios de limpieza.")
        result = classify_document(doc)
        assert result.is_cotizacion is True
        assert "proforma" in result.matched_keywords

    def test_detects_cotizacion(self):
        doc = _make_doc("doc2.pdf", "Adjunto nuestra cotización para el proyecto.")
        result = classify_document(doc)
        assert result.is_cotizacion is True

    def test_detects_presupuesto(self):
        doc = _make_doc("doc3.pdf", "Presupuesto aprobado para Q3 2025.")
        result = classify_document(doc)
        assert result.is_cotizacion is True

    def test_does_not_detect_plain_invoice(self):
        doc = _make_doc("doc4.pdf", "Factura N° 001-0012345. Gracias por su compra.")
        result = classify_document(doc)
        assert result.is_cotizacion is False
        assert result.matched_keywords == []

    def test_failed_extraction_is_not_cotizacion(self):
        doc = _make_doc("doc5.pdf", "", status="error")
        result = classify_document(doc)
        assert result.is_cotizacion is False

    def test_case_insensitive(self):
        doc = _make_doc("doc6.pdf", "COTIZACIÓN N° 2024-001")
        result = classify_document(doc)
        assert result.is_cotizacion is True

    def test_deduplicates_keywords(self):
        doc = _make_doc("doc7.pdf", "Cotización de cotización. Presupuesto 2025.")
        result = classify_document(doc)
        # 'cotización' y 'presupuesto' como únicos
        assert len(result.matched_keywords) == 2


class TestFilterCotizaciones:
    def test_filters_correctly(self):
        docs = [
            _make_doc("a.pdf", "Proforma de servicios"),
            _make_doc("b.pdf", "Contrato de arrendamiento"),
            _make_doc("c.pdf", "Cotización de equipos de cómputo"),
        ]
        cotizaciones, all_cls = filter_cotizaciones(docs)
        assert len(cotizaciones) == 2
        assert len(all_cls) == 3

    def test_empty_input(self):
        cotizaciones, all_cls = filter_cotizaciones([])
        assert cotizaciones == []
        assert all_cls == []
