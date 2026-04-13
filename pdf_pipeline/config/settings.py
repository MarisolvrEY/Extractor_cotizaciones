"""
config/settings.py
------------------
Configuración centralizada. Lee desde .env en la raíz del proyecto.
"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


class Settings:

    # ── Azure AI Content Understanding (OCR) ─────────────────────────────
    # Endpoint del recurso en AI Foundry:
    #   https://<resource>.services.ai.azure.com/
    AZURE_OCR_ENDPOINT: str   = os.getenv("AZURE_OCR_ENDPOINT", "")
    AZURE_OCR_KEY: str        = os.getenv("AZURE_OCR_KEY", "")
    AZURE_OCR_ANALYZER: str   = os.getenv("AZURE_OCR_ANALYZER", "prebuilt-read")
    AZURE_OCR_API_VERSION: str = os.getenv("AZURE_OCR_API_VERSION", "2024-12-01-preview")

    # ── Azure AI Foundry LLM ──────────────────────────────────────────────
    # Endpoint del modelo desplegado en AI Foundry, ej:
    #   https://<project>.openai.azure.com/  (Azure OpenAI)
    #   https://<endpoint>.inference.ai.azure.com/  (serverless)
    AZURE_LLM_ENDPOINT: str    = os.getenv("AZURE_LLM_ENDPOINT", "")
    AZURE_LLM_KEY: str         = os.getenv("AZURE_LLM_KEY", "")
    AZURE_LLM_DEPLOYMENT: str  = os.getenv("AZURE_LLM_DEPLOYMENT", "gpt-4o-mini")
    AZURE_LLM_API_VERSION: str = os.getenv("AZURE_LLM_API_VERSION", "2024-12-01-preview")
    AZURE_LLM_MAX_TOKENS: int  = int(os.getenv("AZURE_LLM_MAX_TOKENS", "2000"))
    AZURE_LLM_TEMPERATURE: float = float(os.getenv("AZURE_LLM_TEMPERATURE", "0.0"))

    # ── Paths ─────────────────────────────────────────────────────────────
    ROOT_DIR: Path           = _ROOT
    INPUT_DIR: Path          = _ROOT / os.getenv("INPUT_DIR",          "data/input")
    COTIZACIONES_DIR: Path   = _ROOT / os.getenv("COTIZACIONES_DIR",   "data/cotizaciones_encontradas")
    OUTPUT_OCR_DIR: Path     = _ROOT / os.getenv("OUTPUT_OCR_DIR",     "data/output/json")
    OUTPUT_CAMPOS_DIR: Path  = _ROOT / os.getenv("OUTPUT_CAMPOS_DIR",  "data/output/campos")
    OUTPUT_TABLES_DIR: Path  = _ROOT / os.getenv("OUTPUT_TABLES_DIR",  "data/output/tables")
    PROMPTS_DIR: Path        = _ROOT / os.getenv("PROMPTS_DIR",        "prompts")

    # ── Pipeline ──────────────────────────────────────────────────────────
    MAX_PDF_SIZE_MB: int = int(os.getenv("MAX_PDF_SIZE_MB", "50"))
    LOG_LEVEL: str       = os.getenv("LOG_LEVEL", "INFO")

    # ── Keywords para detectar cotizaciones ───────────────────────────────
    COTIZACION_KEYWORDS: list[str] = [
        "proforma", "pro forma",
        "cotización", "cotizacion", "cotizaciones",
        "presupuesto",
        "oferta económica", "oferta economica",
        "propuesta comercial",
        "propuesta económica", "propuesta economica",
        "quote", "quotation",
        "precio referencial",
        "lista de precios",
    ]

    def validate_paso1(self) -> None:
        errors = []
        if not self.AZURE_OCR_ENDPOINT:
            errors.append("AZURE_OCR_ENDPOINT no configurado")
        if not self.AZURE_OCR_KEY:
            errors.append("AZURE_OCR_KEY no configurado")
        if errors:
            raise ValueError("Credenciales OCR faltantes:\n" + "\n".join(f"  • {e}" for e in errors))

    def validate_paso3(self) -> None:
        errors = []
        if not self.AZURE_LLM_ENDPOINT:
            errors.append("AZURE_LLM_ENDPOINT no configurado")
        if not self.AZURE_LLM_KEY:
            errors.append("AZURE_LLM_KEY no configurado")
        if errors:
            raise ValueError("Credenciales LLM faltantes:\n" + "\n".join(f"  • {e}" for e in errors))

    def ensure_dirs(self) -> None:
        for d in (
            self.INPUT_DIR, self.COTIZACIONES_DIR,
            self.OUTPUT_OCR_DIR, self.OUTPUT_CAMPOS_DIR,
            self.OUTPUT_TABLES_DIR,
        ):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
