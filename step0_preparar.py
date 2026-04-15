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

Conversión de email a PDF (librerías Python puras, sin dependencias del sistema):
  1. xhtml2pdf  → pip install xhtml2pdf   (recomendada, HTML→PDF puro Python)    (alternativa)
  2. fpdf2       → pip install fpdf2        (fallback, solo texto)        (solo texto plano)

Output:
  data/procesables/                         ← archivos listos para OCR
  data/procesables/<nombre>_emailmeta.json  ← metadatos del email

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
import sys
import zipfile
from pathlib import Path

from config import settings
from src.utils.file_utils import SUPPORTED_EXTENSIONS
from src.utils.logger import get_logger

logger = get_logger("paso0", settings.LOG_LEVEL)

_EMAIL_EXTS   = {".eml", ".msg"}
_ARCHIVE_EXTS = {".zip", ".rar"}
_IMAGE_EXTS   = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif"}
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


# ─── Conversión HTML → PDF (sin LibreOffice) ──────────────────────────────────



def _html_a_pdf_xhtml2pdf(html: str, dest: Path) -> bool:
    try:
        from xhtml2pdf import pisa  # type: ignore
        with open(dest, "wb") as f:
            result = pisa.CreatePDF(html.encode("utf-8"), dest=f)
        return not result.err
    except ImportError:
        return False
    except Exception as exc:
        logger.debug(f"    xhtml2pdf error: {exc}")
        return False


def _texto_a_pdf_fpdf2(subject: str, sender: str, to: str,
                        date: str, body: str, dest: Path) -> bool:
    try:
        from fpdf import FPDF  # type: ignore
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        pdf.set_fill_color(240, 240, 240)
        pdf.rect(10, 10, 190, 30, "F")
        pdf.set_xy(12, 12)
        for label, value in [("Asunto", subject), ("De", sender),
                               ("Para", to), ("Fecha", date)]:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(20, 5, f"{label}:", ln=0)
            pdf.set_font("Helvetica", size=9)
            pdf.cell(0, 5, value[:100], ln=1)
        pdf.ln(5)
        pdf.set_font("Helvetica", size=9)
        for line in body.splitlines():
            pdf.multi_cell(0, 4, line[:200])
        pdf.output(str(dest))
        return True
    except ImportError:
        return False
    except Exception as exc:
        logger.debug(f"    fpdf2 error: {exc}")
        return False


def _email_a_pdf(subject: str, sender: str, to: str, date: str,
                  body_text: str, body_html: str, dest: Path) -> bool:
    """
    Intenta convertir el email a PDF usando las librerías disponibles.
    Orden: xhtml2pdf → fpdf2
    Retorna True si alguna tuvo éxito.
    """
    # Construir HTML con cabecera formateada
    body_src = body_html if body_html else f"<pre>{body_text}</pre>"
    html = f"""<html><head><meta charset='utf-8'>
    <style>
      body {{ font-family: Arial, sans-serif; padding: 20px; font-size: 10pt; }}
      .header {{ background: #f0f0f0; padding: 10px; border-bottom: 2px solid #ccc;
                 margin-bottom: 15px; font-size: 9pt; }}
      .header b {{ display: inline-block; width: 60px; }}
    </style></head><body>
    <div class='header'>
      <b>Asunto:</b> {subject}<br>
      <b>De:</b> {sender}<br>
      <b>Para:</b> {to}<br>
      <b>Fecha:</b> {date}
    </div>
    {body_src}
    </body></html>"""

    if _html_a_pdf_xhtml2pdf(html, dest):
        logger.debug("    → PDF via xhtml2pdf")
        return True
    if _texto_a_pdf_fpdf2(subject, sender, to, date, body_text, dest):
        logger.debug("    → PDF via fpdf2")
        return True
    return False


def _detectar_motor_pdf() -> str:
    """Devuelve el nombre del motor PDF disponible, o 'ninguno'."""
    for mod, name in [("xhtml2pdf", "xhtml2pdf"),
                      ("fpdf",      "fpdf2")]:
        try:
            __import__(mod)
            return name
        except (ImportError, OSError):
            continue
    return "ninguno"


# ─── ZIP / RAR ────────────────────────────────────────────────────────────────

def _extraer_zip(zip_path: Path, dest_dir: Path) -> bool:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = [m for m in zf.namelist() if "__MACOSX" not in m]
            zf.extractall(dest_dir, members=members)
        return True
    except Exception as exc:
        logger.warning(f"  ⚠ ZIP {zip_path.name}: {exc}")
        return False


def _extraer_rar(rar_path: Path, dest_dir: Path) -> bool:
    try:
        import rarfile  # type: ignore
        with rarfile.RarFile(rar_path, "r") as rf:
            rf.extractall(dest_dir)
        return True
    except ImportError:
        logger.warning("  ⚠ .rar: pip install rarfile")
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


# ─── Emails ───────────────────────────────────────────────────────────────────

def _procesar_eml(path: Path, dest_dir: Path) -> tuple[list[Path], dict]:
    raw = path.read_bytes()
    msg = email_lib.message_from_bytes(raw, policy=email_lib.policy.default)

    subject   = str(msg.get("Subject", "") or "")
    sender    = str(msg.get("From",    "") or "")
    to        = str(msg.get("To",      "") or "")
    date      = str(msg.get("Date",    "") or "")
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
    pdf_dest = _unique_dest(dest_dir, f"{path.stem}.pdf")
    if _email_a_pdf(subject, sender, to, date, body_text, body_html, pdf_dest):
        escritos.append(pdf_dest)
    else:
        # Fallback .txt
        txt_dest = _unique_dest(dest_dir, f"{path.stem}_cuerpo.txt")
        txt_dest.write_text(
            f"Asunto: {subject}\nDe: {sender}\nPara: {to}\nFecha: {date}\n\n{body_text}",
            encoding="utf-8",
        )
        escritos.append(txt_dest)

    return escritos, {"tipo": "email", "asunto": subject, "de": sender,
                       "para": to, "fecha": date, "origen": path.name}


def _procesar_msg(path: Path, dest_dir: Path) -> tuple[list[Path], dict]:
    try:
        import extract_msg  # type: ignore
    except ImportError:
        raise ImportError("Para .msg instala: pip install extract-msg")

    m         = extract_msg.Message(str(path))
    subject   = m.subject or ""
    sender    = m.sender  or ""
    to        = m.to      or ""
    date      = str(m.date or "")
    body_text = (m.body or "").strip()
    body_html = ""
    if hasattr(m, "htmlBody") and m.htmlBody:
        body_html = m.htmlBody.decode("utf-8", errors="replace")

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

    pdf_dest = _unique_dest(dest_dir, f"{path.stem}.pdf")
    if _email_a_pdf(subject, sender, to, date, body_text, body_html, pdf_dest):
        escritos.append(pdf_dest)
    else:
        txt_dest = _unique_dest(dest_dir, f"{path.stem}_cuerpo.txt")
        txt_dest.write_text(
            f"Asunto: {subject}\nDe: {sender}\nPara: {to}\nFecha: {date}\n\n{body_text}",
            encoding="utf-8",
        )
        escritos.append(txt_dest)

    m.close()
    return escritos, {"tipo": "email", "asunto": subject, "de": sender,
                       "para": to, "fecha": date, "origen": path.name}


# ─── Principal ────────────────────────────────────────────────────────────────

def preparar(
    input_dir:   Path | None = None,
    destino_dir: Path | None = None,
) -> dict:
    import tempfile
    settings.ensure_dirs()
    src = input_dir   or settings.INPUT_DIR
    dst = destino_dir or settings.PROCESABLES_DIR
    dst.mkdir(parents=True, exist_ok=True)

    motor = _detectar_motor_pdf()

    logger.info("=" * 60)
    logger.info("  PASO 0 — Preparar archivos")
    logger.info("=" * 60)
    logger.info(f"  Origen      : {src}  (recursivo)")
    logger.info(f"  Destino     : {dst}  (un solo nivel)")
    if motor != "ninguno":
        logger.info(f"  Motor PDF   : [green]{motor}[/green] → emails a PDF")
    else:
        logger.warning("  Motor PDF   : [yellow]ninguno instalado[/yellow] → emails a .txt")
        logger.info("    Instalar: pip install xhtml2pdf")

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
                    escritos, meta = _procesar_eml(archivo, dst)
                else:
                    escritos, meta = _procesar_msg(archivo, dst)

                # Guardar _emailmeta.json con el mismo nombre base del email original
                meta_path = dst / f"{archivo.stem}_emailmeta.json"
                meta_path.write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                )

                n_adj = len([e for e in escritos if e.suffix.lower() not in (".pdf", ".txt")])
                logger.info(
                    f"  [cyan]✉[/cyan]  {archivo.name}  "
                    f"→ {'PDF' if motor != 'ninguno' else 'TXT'} + {n_adj} adjunto(s)"
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
    logger.info(f"  Emails procesados     : {emails}  (motor: {motor})")
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
