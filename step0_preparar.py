"""
step0_preparar.py
------------------
PASO 0 — Aplana todos los archivos de data/input/ en data/procesables/.

Qué hace:
  - Recorre data/input/ recursivamente
  - ZIP / RAR    → extrae el contenido (maneja anidados)
  - .eml / .msg  → convierte el cuerpo del email a PDF
                   extrae adjuntos que NO son imágenes (pdf, docx, xlsx, pptx…)
                   guarda un <nombre>_emailmeta.json con remitente, fecha, asunto
  - Resto        → copia plano tal cual

Conversión de email a PDF:
  Usa LibreOffice en modo headless.
    Windows : https://www.libreoffice.org/download
    Mac     : brew install libreoffice
    Linux   : apt install libreoffice
  Si LibreOffice no está disponible, guarda el cuerpo como .txt (fallback).

Output:
  data/procesables/                      ← archivos al mismo nivel listos para OCR
  data/procesables/<nombre>_emailmeta.json  ← metadatos del email (remitente, fecha…)

Uso:
  python step0_preparar.py
  python step0_preparar.py --input data/input --destino data/procesables
"""
from __future__ import annotations

import argparse
import email as email_lib
import email.policy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from config import settings
from src.utils.file_utils import SUPPORTED_EXTENSIONS
from src.utils.logger import get_logger

logger = get_logger("paso0", settings.LOG_LEVEL)

_EMAIL_EXTS   = {".eml", ".msg"}
_ARCHIVE_EXTS = {".zip", ".rar"}
_IMAGE_EXTS   = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif"}
# Adjuntos de email que SÍ se extraen (todo excepto imágenes)
_ATT_EXTS     = SUPPORTED_EXTENSIONS - _EMAIL_EXTS - _IMAGE_EXTS


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _unique_dest(dest_dir: Path, filename: str) -> Path:
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem, ext = Path(filename).stem, Path(filename).suffix
    counter = 2
    while True:
        candidate = dest_dir / f"{stem}_{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    for ent, rep in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")]:
        text = text.replace(ent, rep)
    return re.sub(r"\s+", " ", text).strip()


# ─── LibreOffice ──────────────────────────────────────────────────────────────

def _libreoffice_cmd() -> str | None:
    """Retorna el comando de LibreOffice disponible, o None si no está instalado."""
    for cmd in ("libreoffice", "soffice"):
        try:
            subprocess.run([cmd, "--version"], capture_output=True, check=True)
            return cmd
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return None


def _html_a_pdf(html_content: str, dest_path: Path, lo_cmd: str) -> bool:
    """Convierte HTML a PDF usando LibreOffice. Retorna True si tuvo éxito."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_html = Path(tmp) / "email.html"
        tmp_html.write_text(html_content, encoding="utf-8")
        try:
            result = subprocess.run(
                [lo_cmd, "--headless", "--convert-to", "pdf",
                 "--outdir", str(tmp), str(tmp_html)],
                capture_output=True, timeout=120,
            )
            if result.returncode == 0:
                generated = Path(tmp) / "email.pdf"
                if generated.exists():
                    shutil.copy2(generated, dest_path)
                    return True
        except subprocess.TimeoutExpired:
            logger.warning("  ⚠ Timeout en conversión LibreOffice")
    return False


# ─── ZIP / RAR ────────────────────────────────────────────────────────────────

def _extraer_zip(zip_path: Path, dest_dir: Path) -> bool:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = [m for m in zf.namelist() if "__MACOSX" not in m]
            zf.extractall(dest_dir, members=members)
        return True
    except Exception as exc:
        r = subprocess.run(f'unzip -o -q "{zip_path}" -d "{dest_dir}"',
                           shell=True, capture_output=True)
        if r.returncode in (0, 1):
            return True
        logger.warning(f"  ⚠ ZIP {zip_path.name}: {exc}")
        return False


def _extraer_rar(rar_path: Path, dest_dir: Path) -> bool:
    try:
        import rarfile  # type: ignore
        with rarfile.RarFile(rar_path, "r") as rf:
            rf.extractall(dest_dir)
        return True
    except ImportError:
        logger.warning("  ⚠ .rar: pip install rarfile  +  unrar en el sistema")
        return False
    except Exception as exc:
        logger.warning(f"  ⚠ RAR {rar_path.name}: {exc}")
        return False


def _descomprimir_recursivo(src_dir: Path) -> int:
    total = 0
    while True:
        archivos = [f for f in src_dir.rglob("*")
                    if f.is_file() and f.suffix.lower() in _ARCHIVE_EXTS
                    and "__MACOSX" not in str(f)]
        if not archivos:
            break
        extraidos = 0
        for f in archivos:
            ok = _extraer_zip(f, f.parent) if f.suffix.lower() == ".zip" \
                 else _extraer_rar(f, f.parent)
            if ok:
                f.unlink()
                extraidos += 1
                total += 1
        if extraidos == 0:
            break
    for d in src_dir.rglob("__MACOSX"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
    return total


# ─── Email → PDF ──────────────────────────────────────────────────────────────

def _construir_html_email(subject: str, sender: str, to: str,
                          date: str, body: str, is_html: bool) -> str:
    """Construye un HTML bien formateado con los datos del email."""
    header = (
        f"<div style='font-family:Arial;border-bottom:2px solid #ccc;padding-bottom:8px;margin-bottom:16px'>"
        f"<b>Asunto:</b> {subject}<br>"
        f"<b>De:</b> {sender}<br>"
        f"<b>Para:</b> {to}<br>"
        f"<b>Fecha:</b> {date}"
        f"</div>"
    )
    body_html = body if is_html else f"<pre style='font-family:Arial;white-space:pre-wrap'>{body}</pre>"
    return f"<html><body style='font-family:Arial;padding:20px'>{header}{body_html}</body></html>"


def _procesar_eml(path: Path, dest_dir: Path, lo_cmd: str | None) -> tuple[list[Path], dict]:
    """
    Procesa un .eml:
      - Convierte el cuerpo a PDF (o .txt si no hay LibreOffice)
      - Extrae adjuntos que no sean imágenes
      - Retorna (archivos_escritos, email_meta)
    """
    raw = path.read_bytes()
    msg = email_lib.message_from_bytes(raw, policy=email_lib.policy.default)

    subject = str(msg.get("Subject", "") or "")
    sender  = str(msg.get("From",    "") or "")
    to      = str(msg.get("To",      "") or "")
    date    = str(msg.get("Date",    "") or "")

    body_text = ""
    body_html = ""
    escritos: list[Path] = []

    for part in msg.walk():
        ct   = part.get_content_type()
        disp = str(part.get("Content-Disposition", "") or "")

        if "attachment" in disp:
            filename = part.get_filename()
            if filename:
                ext  = Path(filename).suffix.lower()
                data = part.get_payload(decode=True)
                if ext in _ATT_EXTS and data:
                    dest = _unique_dest(dest_dir, filename)
                    dest.write_bytes(data)
                    escritos.append(dest)
                    logger.debug(f"    adjunto → {dest.name}")
        elif ct == "text/plain" and not body_text:
            payload = part.get_payload(decode=True)
            if payload:
                body_text = payload.decode("utf-8", errors="replace")
        elif ct == "text/html" and not body_html:
            payload = part.get_payload(decode=True)
            if payload:
                body_html = payload.decode("utf-8", errors="replace")

    # Convertir cuerpo a PDF
    body_src    = body_html if body_html else body_text
    is_html     = bool(body_html)
    html_content = _construir_html_email(subject, sender, to, date, body_src, is_html)

    pdf_dest = _unique_dest(dest_dir, f"{path.stem}.pdf")
    if lo_cmd and _html_a_pdf(html_content, pdf_dest, lo_cmd):
        escritos.append(pdf_dest)
        logger.debug(f"    email → PDF: {pdf_dest.name}")
    else:
        # Fallback: guardar como .txt
        txt_dest = _unique_dest(dest_dir, f"{path.stem}_cuerpo.txt")
        txt_dest.write_text(
            f"Asunto: {subject}\nDe: {sender}\nPara: {to}\nFecha: {date}\n\n{body_text}",
            encoding="utf-8",
        )
        escritos.append(txt_dest)
        if lo_cmd is None:
            logger.debug(f"    email → TXT (sin LibreOffice): {txt_dest.name}")

    email_meta = {
        "tipo":    "email",
        "asunto":  subject,
        "de":      sender,
        "para":    to,
        "fecha":   date,
        "origen":  path.name,
    }
    return escritos, email_meta


def _procesar_msg(path: Path, dest_dir: Path, lo_cmd: str | None) -> tuple[list[Path], dict]:
    """Procesa un .msg de Outlook: cuerpo → PDF + adjuntos no-imagen."""
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
    body_html = (m.htmlBody or b"").decode("utf-8", errors="replace") if hasattr(m, "htmlBody") else ""

    escritos: list[Path] = []

    for att in m.attachments:
        filename = att.longFilename or att.shortFilename or ""
        if filename and att.data:
            ext = Path(filename).suffix.lower()
            if ext in _ATT_EXTS:
                dest = _unique_dest(dest_dir, filename)
                dest.write_bytes(att.data)
                escritos.append(dest)
                logger.debug(f"    adjunto → {dest.name}")

    body_src     = body_html if body_html else body
    is_html      = bool(body_html)
    html_content = _construir_html_email(subject, sender, to, date, body_src, is_html)

    pdf_dest = _unique_dest(dest_dir, f"{path.stem}.pdf")
    if lo_cmd and _html_a_pdf(html_content, pdf_dest, lo_cmd):
        escritos.append(pdf_dest)
    else:
        txt_dest = _unique_dest(dest_dir, f"{path.stem}_cuerpo.txt")
        txt_dest.write_text(
            f"Asunto: {subject}\nDe: {sender}\nPara: {to}\nFecha: {date}\n\n{body}",
            encoding="utf-8",
        )
        escritos.append(txt_dest)

    m.close()

    email_meta = {
        "tipo":   "email",
        "asunto": subject,
        "de":     sender,
        "para":   to,
        "fecha":  date,
        "origen": path.name,
    }
    return escritos, email_meta


# ─── Principal ────────────────────────────────────────────────────────────────

def preparar(
    input_dir:   Path | None = None,
    destino_dir: Path | None = None,
) -> dict:
    settings.ensure_dirs()
    src = input_dir   or settings.INPUT_DIR
    dst = destino_dir or settings.PROCESABLES_DIR
    dst.mkdir(parents=True, exist_ok=True)

    lo_cmd = _libreoffice_cmd()

    logger.info("=" * 60)
    logger.info("  PASO 0 — Preparar archivos")
    logger.info("=" * 60)
    logger.info(f"  Origen      : {src}  (recursivo)")
    logger.info(f"  Destino     : {dst}  (un solo nivel)")
    if lo_cmd:
        logger.info(f"  LibreOffice : [green]disponible[/green] → emails a PDF")
    else:
        logger.warning("  LibreOffice : [yellow]no encontrado[/yellow] → emails a .txt")
        logger.info("    Instalar: https://www.libreoffice.org/download")

    tmp = Path(tempfile.mkdtemp(prefix="preparar_tmp_"))
    shutil.copytree(src, tmp / "input", dirs_exist_ok=True)
    trabajo = tmp / "input"

    n_zips = _descomprimir_recursivo(trabajo)
    if n_zips:
        logger.info(f"\n  Comprimidos extraídos: {n_zips}")

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

    copiados = emails = adjuntos = errores = 0

    logger.info(f"\nArchivos a procesar: {len(todos)}\n")

    for archivo in todos:
        ext = archivo.suffix.lower()
        try:
            if ext in _EMAIL_EXTS:
                if ext == ".eml":
                    escritos, meta = _procesar_eml(archivo, dst, lo_cmd)
                else:
                    escritos, meta = _procesar_msg(archivo, dst, lo_cmd)

                # Guardar _emailmeta.json junto al PDF/txt para que step1 lo lea
                pdf_escritos = [e for e in escritos if e.suffix.lower() in (".pdf", ".txt")
                                and "adjunto" not in e.name]
                if pdf_escritos:
                    meta_path = dst / f"{pdf_escritos[0].stem}_emailmeta.json"
                    meta_path.write_text(
                        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                    )

                n_adj = len([e for e in escritos
                             if e.suffix.lower() not in (".pdf", ".txt")])
                logger.info(
                    f"  [cyan]✉[/cyan]  {archivo.name}  "
                    f"→ {'PDF' if lo_cmd else 'TXT'} + {n_adj} adjunto(s)"
                )
                emails   += 1
                adjuntos += n_adj

            else:
                dest = _unique_dest(dst, archivo.name)
                shutil.copy2(archivo, dest)
                logger.info(f"  [green]✓[/green]  {archivo.name}")
                copiados += 1

        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ {archivo.name} — {exc}")
            errores += 1

    shutil.rmtree(tmp, ignore_errors=True)

    logger.info("\n" + "=" * 60)
    logger.info(f"  Comprimidos extraídos : {n_zips}")
    logger.info(f"  Archivos copiados     : [green]{copiados}[/green]")
    logger.info(f"  Emails procesados     : {emails}")
    logger.info(f"  Adjuntos extraídos    : {adjuntos}")
    logger.info(f"  Errores               : {errores}")
    logger.info("=" * 60)

    return {"total": len(todos), "copiados": copiados,
            "emails": emails, "adjuntos": adjuntos, "errores": errores}


def _args():
    p = argparse.ArgumentParser(
        description="Paso 0: aplana archivos, descomprime ZIP/RAR, emails → PDF."
    )
    p.add_argument("--input",   type=Path, default=None)
    p.add_argument("--destino", type=Path, default=None)
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    r = preparar(input_dir=args.input, destino_dir=args.destino)
    sys.exit(0 if r["total"] > 0 else 1)
