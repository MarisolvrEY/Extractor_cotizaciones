"""
step0_preparar.py
------------------
PASO 0 — Aplana todos los archivos de data/input/ en data/procesables/.

Qué hace:
  - Recorre data/input/ recursivamente
  - ZIP / RAR  → extrae el contenido (maneja anidados con varias pasadas)
  - .eml / .msg → extrae cuerpo como .txt + cada adjunto como archivo suelto
                  (las imágenes adjuntas también se guardan)
  - Resto       → copia plano a data/procesables/
  - Si dos archivos tienen el mismo nombre agrega sufijo numérico

Output:
  data/procesables/    ← todo al mismo nivel, listo para OCR

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
import tempfile
import zipfile
from pathlib import Path

from config import settings
from src.utils.file_utils import SUPPORTED_EXTENSIONS
from src.utils.logger import get_logger

logger = get_logger("paso0", settings.LOG_LEVEL)

_EMAIL_EXTS    = {".eml", ".msg"}
_ARCHIVE_EXTS  = {".zip", ".rar"}
_OTHER_EXTS    = SUPPORTED_EXTENSIONS - _EMAIL_EXTS   # archivos que van directo a procesables


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _unique_dest(dest_dir: Path, filename: str) -> Path:
    """Devuelve una ruta libre de colisiones en dest_dir."""
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem    = Path(filename).stem
    ext     = Path(filename).suffix
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


# ─── ZIP / RAR ────────────────────────────────────────────────────────────────

def _extraer_zip(zip_path: Path, dest_dir: Path) -> bool:
    """Extrae un ZIP en dest_dir. Retorna True si tuvo éxito."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Omitir artefactos de macOS
            members = [m for m in zf.namelist() if "__MACOSX" not in m]
            zf.extractall(dest_dir, members=members)
        return True
    except Exception as exc:
        logger.warning(f"  ⚠ No se pudo extraer ZIP {zip_path.name}: {exc}")
        return False


def _extraer_rar(rar_path: Path, dest_dir: Path) -> bool:
    """Extrae un RAR en dest_dir. Requiere: pip install rarfile + unrar en PATH."""
    try:
        import rarfile  # type: ignore
        with rarfile.RarFile(rar_path, "r") as rf:
            rf.extractall(dest_dir)
        return True
    except ImportError:
        logger.warning("  ⚠ Para .rar instala: pip install rarfile  (y unrar en el sistema)")
        return False
    except Exception as exc:
        logger.warning(f"  ⚠ No se pudo extraer RAR {rar_path.name}: {exc}")
        return False


def _descomprimir_recursivo(src_dir: Path) -> int:
    """
    Busca y extrae todos los ZIP/RAR en src_dir (varias pasadas para manejar anidados).
    Elimina el archivo comprimido tras extraerlo.
    Retorna el total de archivos extraídos.
    """
    total = 0
    while True:
        archivos = [
            f for f in src_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in _ARCHIVE_EXTS
            and "__MACOSX" not in str(f)
        ]
        if not archivos:
            break

        extraidos_en_pasada = 0
        for archivo in archivos:
            dest = archivo.parent
            if archivo.suffix.lower() == ".zip":
                ok = _extraer_zip(archivo, dest)
            else:
                ok = _extraer_rar(archivo, dest)

            if ok:
                archivo.unlink()
                extraidos_en_pasada += 1
                total += 1
                logger.debug(f"    extraído → {archivo.name}")

        if extraidos_en_pasada == 0:
            break  # sin progreso, evitar bucle infinito

    # Limpiar carpetas __MACOSX si quedaron
    for macos_dir in src_dir.rglob("__MACOSX"):
        if macos_dir.is_dir():
            shutil.rmtree(macos_dir, ignore_errors=True)

    return total


# ─── Emails ───────────────────────────────────────────────────────────────────

def _procesar_eml(path: Path, dest_dir: Path) -> list[Path]:
    """
    Extrae de un .eml:
      - cuerpo como <nombre>_cuerpo.txt
      - cada adjunto soportado (PDF, imágenes, Office, etc.) como archivo suelto
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
                ext  = Path(filename).suffix.lower()
                data = part.get_payload(decode=True)
                # Guardamos todo adjunto soportado: PDFs, imágenes, Office
                if ext in _OTHER_EXTS and data:
                    dest = _unique_dest(dest_dir, filename)
                    dest.write_bytes(data)
                    escritos.append(dest)
                    logger.debug(f"    adjunto email → {dest.name}")

        elif ct == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                body_parts.append(payload.decode("utf-8", errors="replace"))

        elif ct == "text/html" and not body_parts:
            payload = part.get_payload(decode=True)
            if payload:
                body_parts.append(_strip_html(payload.decode("utf-8", errors="replace")))

    body    = "\n".join(body_parts).strip()
    content = (
        f"Asunto: {subject}\nDe: {sender}\nPara: {to}\nFecha: {date}\n\n{body}"
    )
    txt_dest = _unique_dest(dest_dir, f"{path.stem}_cuerpo.txt")
    txt_dest.write_text(content, encoding="utf-8")
    escritos.append(txt_dest)

    return escritos


def _procesar_msg(path: Path, dest_dir: Path) -> list[Path]:
    """Extrae cuerpo + adjuntos de un .msg de Outlook."""
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
                logger.debug(f"    adjunto msg → {dest.name}")

    content  = f"Asunto: {subject}\nDe: {sender}\nPara: {to}\nFecha: {date}\n\n{body}"
    txt_dest = _unique_dest(dest_dir, f"{path.stem}_cuerpo.txt")
    txt_dest.write_text(content, encoding="utf-8")
    escritos.append(txt_dest)

    return escritos


# ─── Principal ────────────────────────────────────────────────────────────────

def preparar(
    input_dir:   Path | None = None,
    destino_dir: Path | None = None,
) -> dict:
    settings.ensure_dirs()
    src = input_dir   or settings.INPUT_DIR
    dst = destino_dir or settings.PROCESABLES_DIR
    dst.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("  PASO 0 — Preparar archivos")
    logger.info("=" * 60)
    logger.info(f"  Origen  : {src}  (recursivo)")
    logger.info(f"  Destino : {dst}  (un solo nivel)")

    # ── 1. Extraer ZIP / RAR en un directorio temporal ────────────────────
    # Copiamos input a un tmp para no modificar el original
    tmp = Path(tempfile.mkdtemp(prefix="preparar_tmp_"))
    shutil.copytree(src, tmp / "input", dirs_exist_ok=True)
    trabajo = tmp / "input"

    n_zips = _descomprimir_recursivo(trabajo)
    if n_zips:
        logger.info(f"\n  Archivos comprimidos extraídos: {n_zips}")

    # ── 2. Recolectar todo lo que quedó (incluyendo lo descomprimido) ─────
    todos = sorted(
        f for f in trabajo.rglob("*")
        if f.is_file()
        and f.suffix.lower() in (SUPPORTED_EXTENSIONS | _ARCHIVE_EXTS)
        and "__MACOSX" not in str(f)
    )

    if not todos:
        logger.warning("No se encontraron archivos soportados.")
        shutil.rmtree(tmp, ignore_errors=True)
        return {"total": 0, "copiados": 0, "emails": 0, "adjuntos": 0, "errores": 0}

    copiados = 0
    emails   = 0
    adjuntos = 0
    errores  = 0

    logger.info(f"\nArchivos a procesar: {len(todos)}\n")

    for archivo in todos:
        ext = archivo.suffix.lower()
        try:
            if ext in _EMAIL_EXTS:
                if ext == ".eml":
                    escritos = _procesar_eml(archivo, dst)
                else:
                    escritos = _procesar_msg(archivo, dst)

                n_adj = len([e for e in escritos if e.suffix.lower() != ".txt"])
                logger.info(
                    f"  [cyan]✉ email[/cyan]  {archivo.name}  "
                    f"→ cuerpo.txt + {n_adj} adjunto(s)"
                )
                emails   += 1
                adjuntos += n_adj

            elif ext in _OTHER_EXTS:
                dest = _unique_dest(dst, archivo.name)
                shutil.copy2(archivo, dest)
                logger.info(f"  [green]✓[/green]  {archivo.name}  →  {dest.name}")
                copiados += 1

        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ {archivo.name} — {exc}")
            errores += 1

    shutil.rmtree(tmp, ignore_errors=True)

    total_dest = copiados + emails + adjuntos

    logger.info("\n" + "=" * 60)
    logger.info(f"  Comprimidos extraídos  : {n_zips}")
    logger.info(f"  Archivos copiados      : [green]{copiados}[/green]")
    logger.info(f"  Emails procesados      : {emails}")
    logger.info(f"  Adjuntos de emails     : {adjuntos}  (PDFs, imágenes, Office)")
    logger.info(f"  Errores                : {errores}")
    logger.info(f"  Total en procesables/  : {total_dest}")
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
        description="Paso 0: aplana archivos (extrae ZIP/RAR, procesa emails)."
    )
    p.add_argument("--input",   type=Path, default=None)
    p.add_argument("--destino", type=Path, default=None)
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    r = preparar(input_dir=args.input, destino_dir=args.destino)
    sys.exit(0 if r["total"] > 0 else 1)
