"""
main.py
--------
Corre los pasos en secuencia o los que elijas.

  Paso 0  step0_preparar.py      Aplana archivos + extrae emails + descomprime ZIP/RAR
  Paso 1  step1_extraer.py       Azure OCR → JSONs de texto
  Paso 2  step2_clasificar.py    Detecta cotizaciones → carpeta separada
  Paso 3  step3_metadatos.py     Extrae metadatos → Excel + JSON por archivo
  Paso 4  step4_llm.py           LLM → campos estructurados + tabla resumen

Uso:
  python main.py                        # los 5 pasos
  python main.py --pasos 0 1 2          # solo preparar + OCR + clasificar
  python main.py --pasos 3 4            # solo metadatos + LLM
  python main.py --paso 4               # solo LLM
  python main.py --prompt prompt.txt    # prompt personalizado para paso 4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config import settings
from src.utils.logger import get_logger

logger = get_logger("main", settings.LOG_LEVEL)


def _args():
    p = argparse.ArgumentParser(
        description="Pipeline: preparar → OCR → clasificar → metadatos → LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pasos disponibles:
  0  Aplanar input/ + emails + ZIP/RAR  →  data/procesables/
  1  Azure OCR                          →  data/output/json/
  2  Clasificar cotizaciones            →  data/cotizaciones_encontradas/
  3  Metadatos                          →  data/output/metadatos/
  4  LLM extraer campos                 →  data/output/campos/ + tablas

Ejemplos:
  python main.py                   # pipeline completo
  python main.py --pasos 0 1 2     # hasta clasificar
  python main.py --pasos 3 4       # solo metadatos + LLM
  python main.py --paso 4          # solo LLM

Scripts individuales:
  python step0_preparar.py   [--input ...] [--destino ...]
  python step1_extraer.py    [--origen ...] [--json-dir ...]
  python step2_clasificar.py [--json-dir ...] [--input ...] [--destino ...]
  python step3_metadatos.py  [--origen ...] [--nombre ...]
  python step4_llm.py        [--cotizaciones ...] [--prompt ...]
        """,
    )
    p.add_argument(
        "--pasos", type=int, nargs="+", choices=[0, 1, 2, 3, 4],
        default=[0, 1, 2, 3, 4],
        help="Pasos a ejecutar (default: 0 1 2 3 4)",
    )
    p.add_argument("--prompt", type=str, default="prompt.txt")
    return p.parse_args()


def main() -> int:
    args  = _args()
    pasos = sorted(set(args.pasos))

    logger.info("=" * 60)
    logger.info(f"  PIPELINE PDF  — pasos: {pasos}")
    logger.info("=" * 60)

    if 1 in pasos:
        try:
            settings.validate_paso1()
        except ValueError as exc:
            logger.error(f"[red]{exc}[/red]")
            return 1

    if 4 in pasos:
        try:
            settings.validate_paso3()
        except ValueError as exc:
            logger.error(f"[red]{exc}[/red]")
            return 1

    # ── PASO 0 ────────────────────────────────────────────────────────────
    if 0 in pasos:
        logger.info("\n── PASO 0: Preparar archivos ──")
        from step0_preparar import preparar
        r0 = preparar()
        if r0["total"] == 0:
            logger.error("No se encontraron archivos en data/input/. Abortando.")
            return 1

    # ── PASO 1 ────────────────────────────────────────────────────────────
    if 1 in pasos:
        logger.info("\n── PASO 1: Azure AI Content Understanding OCR ──")
        from step1_extraer import extraer
        r1 = extraer()
        if r1["exitosos"] == 0:
            logger.error("Ningún archivo se procesó correctamente. Abortando.")
            return 1

    # ── PASO 2 ────────────────────────────────────────────────────────────
    if 2 in pasos:
        logger.info("\n── PASO 2: Clasificar cotizaciones ──")
        from step2_clasificar import clasificar
        r2 = clasificar()
        if r2["cotizaciones"] == 0 and (3 in pasos or 4 in pasos):
            logger.warning("No se encontraron cotizaciones — los pasos 3 y 4 no tienen qué procesar.")
            return 0

    # ── PASO 3 ────────────────────────────────────────────────────────────
    if 3 in pasos:
        logger.info("\n── PASO 3: Extracción de metadatos ──")
        from step3_metadatos import extraer_metadatos
        r3 = extraer_metadatos()
        if r3["total"] == 0:
            logger.warning("Sin archivos para extraer metadatos.")

    # ── PASO 4 ────────────────────────────────────────────────────────────
    if 4 in pasos:
        logger.info("\n── PASO 4: LLM Azure AI Foundry ──")
        from step4_llm import procesar
        r4 = procesar(prompt_file=args.prompt)
        if r4["total"] == 0:
            return 1

    logger.info("\n[green]Pipeline finalizado.[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
