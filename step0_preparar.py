"""
step0_preparar.py
------------------
PASO 0 — Aplana todos los archivos de data/input/ en data/procesables/.

Qué hace:
  - Recorre data/input/ recursivamente (subcarpetas, sub-subcarpetas, etc.)
  - Copia cada archivo a data/procesables/ en un solo nivel
  - Si dos archivos distintos tienen el mismo nombre, agrega un sufijo numérico
  - Para emails (.eml / .msg):
      · Extrae el cuerpo como <nombre>_cuerpo.txt
      · Extrae cada adjunto como archivo suelto
      · No copia el .eml / .msg original (ya está representado por el .txt + adjuntos)

Output:
  data/procesables/    ← todos los archivos al mismo nivel, listos para OCR

Uso:
  python step0_preparar.py
  python step0_preparar.py --input data/input --destino data/procesables
"""
from __future__ import annotations

import argparse
import email as email_lib
import email.policy
import re
import shutil
import sys
from pathlib import Path

from config import settings
from src.utils.file_utils import SUPPORTED_EXTENSIONS
from src.utils.logger import get_logger

logger = get_logger("paso0", settings.LOG_LEVEL)

_EMAIL_EXTS = {".eml", ".msg"}
_OTHER_EXTS = SUPPORTED_EXTENSIONS - _EMAIL_EXTS


def _unique_dest(dest_dir: Path, filename: str) -> Path:
    """
    Retorna una ruta en dest_dir que no colisione con archivos existentes.
    Si 'factura.pdf' ya existe → 'factura_2.pdf', 'factura_3.pdf', etc.
    """
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    ext  = Path(filename).suffix
    counter = 2
    while True:
        candidate = dest_dir / f"{stem}_{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;",  "&", text)
    text = re.sub(r"&lt;",   "<", text)
    text = re.sub(r"&gt;",   ">", text)
    return re.sub(r"\s+", " ", text).strip()


def _procesar_eml(path: Path, dest_dir: Path) -> list[Path]:
    """
    Parsea un .eml y escribe en dest_dir:
      - <nombre>_cuerpo.txt  con asunto + cuerpo del mensaje
      - un archivo por cada adjunto soportado

    Retorna lista de archivos escritos.
    """
    raw = path.read_bytes()
    msg = email_lib.message_from_bytes(raw, policy=email_lib.policy.default)

    subject = str(msg.get("Subject", "") or "")
    sender  = str(msg.get("From",    "") or "")
    to      = str(msg.get("To",      "") or "")
    date    = str(msg.get("Date",    "") or "")

    body_parts: list[str] = []
    escritos:   list[Path] = []

    for part in msg.walk():
        ct   = part.get_content_type()
        disp = str(part.get("Content-Disposition", "") or "")

        if "attachment" in disp:
            filename = part.get_filename()
            if filename:
                ext = Path(filename).suffix.lower()
                if ext in _OTHER_EXTS:
                    data = part.get_payload(decode=True)
                    if data:
                        dest = _unique_dest(dest_dir, filename)
                        dest.write_bytes(data)
                        escritos.append(dest)
                        logger.debug(f"    adjunto → {dest.name}")

        elif ct == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                body_parts.append(payload.decode("utf-8", errors="replace"))

        elif ct == "text/html" and not body_parts:
            payload = part.get_payload(decode=True)
            if payload:
                body_parts.append(_strip_html(payload.decode("utf-8", errors="replace")))

    # Guardar cuerpo como .txt
    body    = "\n".join(body_parts).strip()
    content = (
        f"Asunto: {subject}\n"
        f"De: {sender}\n"
        f"Para: {to}\n"
        f"Fecha: {date}\n"
        f"\n{body}"
    )
    txt_dest = _unique_dest(dest_dir, f"{path.stem}_cuerpo.txt")
    txt_dest.write_text(content, encoding="utf-8")
    escritos.append(txt_dest)

    return escritos


def _procesar_msg(path: Path, dest_dir: Path) -> list[Path]:
    """
    Parsea un .msg de Outlook y escribe en dest_dir:
      - <nombre>_cuerpo.txt
      - un archivo por cada adjunto soportado
    """
    try:
        import extract_msg  # type: ignore
    except ImportError:
        raise ImportError("Para .msg instala: pip install extract-msg")

    m       = extract_msg.Message(str(path))
    subject = m.subject or ""
    sender  = m.sender  or ""
    to      = m.to      or ""
    date    = str(m.date or "")
    body    = (m.body   or "").strip()

    escritos: list[Path] = []

    for att in m.attachments:
        filename = att.longFilename or att.shortFilename or ""
        if filename:
            ext = Path(filename).suffix.lower()
            if ext in _OTHER_EXTS and att.data:
                dest = _unique_dest(dest_dir, filename)
                dest.write_bytes(att.data)
                escritos.append(dest)
                logger.debug(f"    adjunto → {dest.name}")

    content = (
        f"Asunto: {subject}\n"
        f"De: {sender}\n"
        f"Para: {to}\n"
        f"Fecha: {date}\n"
        f"\n{body}"
    )
    txt_dest = _unique_dest(dest_dir, f"{path.stem}_cuerpo.txt")
    txt_dest.write_text(content, encoding="utf-8")
    escritos.append(txt_dest)

    return escritos


def preparar(
    input_dir:  Path | None = None,
    destino_dir: Path | None = None,
) -> dict:
    src = input_dir   or settings.INPUT_DIR
    dst = destino_dir or settings.PROCESABLES_DIR
    dst.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("  PASO 0 — Preparar archivos")
    logger.info("=" * 60)
    logger.info(f"  Origen  : {src}  (recursivo)")
    logger.info(f"  Destino : {dst}  (un solo nivel)")

    # Todos los archivos soportados, en cualquier subcarpeta
    todos = sorted(
        f for f in src.rglob("*")
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not todos:
        logger.warning("No se encontraron archivos soportados.")
        return {"total": 0, "copiados": 0, "emails": 0, "adjuntos": 0, "errores": 0}

    copiados = 0
    emails   = 0
    adjuntos = 0
    errores  = 0

    logger.info(f"\nArchivos encontrados: {len(todos)}\n")

    for archivo in todos:
        ext = archivo.suffix.lower()
        try:
            if ext in _EMAIL_EXTS:
                # Email → extraer cuerpo + adjuntos
                if ext == ".eml":
                    escritos = _procesar_eml(archivo, dst)
                else:
                    escritos = _procesar_msg(archivo, dst)

                n_adj = len([e for e in escritos if e.suffix.lower() != ".txt"])
                logger.info(
                    f"  [cyan]✉ email[/cyan]  {archivo.relative_to(src)}  "
                    f"→ cuerpo.txt + {n_adj} adjunto(s)"
                )
                emails   += 1
                adjuntos += n_adj

            else:
                # Cualquier otro archivo soportado → copiar plano
                dest = _unique_dest(dst, archivo.name)
                shutil.copy2(archivo, dest)
                rel  = archivo.relative_to(src)
                logger.info(f"  [green]✓ copiado[/green]  {rel}  →  {dest.name}")
                copiados += 1

        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ {archivo.name} — {exc}")
            errores += 1

    total_en_destino = copiados + adjuntos + emails  # emails = n archivos .txt

    logger.info("\n" + "=" * 60)
    logger.info(f"  Archivos de entrada    : {len(todos)}")
    logger.info(f"  Archivos copiados      : [green]{copiados}[/green]")
    logger.info(f"  Emails procesados      : {emails}  (cuerpo + adjuntos)")
    logger.info(f"  Adjuntos extraídos     : {adjuntos}")
    logger.info(f"  Errores                : {errores}")
    logger.info(f"  Total en {dst.name}/  : {total_en_destino} archivo(s)")
    logger.info("=" * 60)

    return {
        "total":    len(todos),
        "copiados": copiados,
        "emails":   emails,
        "adjuntos": adjuntos,
        "errores":  errores,
    }


def _args():
    p = argparse.ArgumentParser(
        description="Paso 0: aplana todos los archivos de input en una carpeta plana."
    )
    p.add_argument("--input",   type=Path, default=None, help="Carpeta de entrada (recursiva)")
    p.add_argument("--destino", type=Path, default=None, help="Carpeta plana de salida")
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    r = preparar(input_dir=args.input, destino_dir=args.destino)
    sys.exit(0 if r["total"] > 0 else 1)
