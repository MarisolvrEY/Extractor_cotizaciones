"""
main.py
--------
Corre los 3 pasos en secuencia o individualmente.

Pasos:
  1. step1_extraer.py    → OCR de todos los PDFs → data/output/json/
  2. step2_clasificar.py → detecta cotizaciones  → data/cotizaciones_encontradas/
  3. step3_llm.py        → LLM en cotizaciones   → data/output/campos/ + tablas

Uso:
  python main.py                    # los 3 pasos completos
  python main.py --paso 1           # solo paso 1
  python main.py --paso 2           # solo paso 2
  python main.py --paso 3           # solo paso 3
  python main.py --pasos 1 2        # pasos 1 y 2
  python main.py --prompt prompt.txt
"""
from __future__ import annotations

import argparse
import sys

from config import settings
from src.utils.logger import get_logger

logger = get_logger("main", settings.LOG_LEVEL)


def _args():
    p = argparse.ArgumentParser(
        description="Pipeline PDF: OCR → clasificación → LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py                    # pipeline completo
  python main.py --pasos 1 2        # solo OCR y clasificación
  python main.py --paso 3           # solo LLM (pasos 1 y 2 ya corridos)
  python main.py --prompt prompt.txt

Scripts individuales:
  python step1_extraer.py   [--input ...] [--json-dir ...]
  python step2_clasificar.py [--json-dir ...] [--input ...] [--destino ...]
  python step3_llm.py        [--cotizaciones ...] [--prompt ...]
        """,
    )
    p.add_argument(
        "--pasos", type=int, nargs="+", choices=[1, 2, 3],
        default=[1, 2, 3],
        help="Pasos a ejecutar (default: 1 2 3)",
    )
    p.add_argument("--prompt", type=str, default="prompt.txt", help="Archivo de prompt para el paso 3")
    return p.parse_args()


def main() -> int:
    args   = _args()
    pasos  = sorted(set(args.pasos))

    logger.info("=" * 60)
    logger.info(f"  PIPELINE PDF  — pasos: {pasos}")
    logger.info("=" * 60)

    # Validar credenciales según los pasos a correr
    if 1 in pasos or 2 in pasos:
        try:
            settings.validate_paso1()
        except ValueError as exc:
            logger.error(f"[red]{exc}[/red]")
            return 1

    if 3 in pasos:
        try:
            settings.validate_paso3()
        except ValueError as exc:
            logger.error(f"[red]{exc}[/red]")
            return 1

    # ── PASO 1 ────────────────────────────────────────────────────────────
    if 1 in pasos:
        logger.info("\n── PASO 1: Azure AI Content Understanding OCR ──")
        from step1_extraer import extraer
        r1 = extraer()
        if r1["exitosos"] == 0:
            logger.error("Ningún PDF se extrajo correctamente. Abortando.")
            return 1

    # ── PASO 2 ────────────────────────────────────────────────────────────
    if 2 in pasos:
        logger.info("\n── PASO 2: Clasificación de cotizaciones ──")
        from step2_clasificar import clasificar
        r2 = clasificar()
        if r2["cotizaciones"] == 0 and 3 in pasos:
            logger.warning("No se encontraron cotizaciones — el paso 3 no tiene qué procesar.")
            return 0

    # ── PASO 3 ────────────────────────────────────────────────────────────
    if 3 in pasos:
        logger.info("\n── PASO 3: LLM Azure AI Foundry ──")
        from step3_llm import procesar
        r3 = procesar(prompt_file=args.prompt)
        if r3["total"] == 0:
            return 1

    logger.info("\n[green]Pipeline finalizado.[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
