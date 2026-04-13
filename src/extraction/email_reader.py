"""
src/extraction/email_reader.py
-------------------------------
Lee archivos de email (.eml, .msg) y extrae:
  - Metadatos: asunto, remitente, destinatarios, fecha
  - Cuerpo del mensaje (texto plano, sin HTML)
  - Adjuntos: los guarda en un directorio temporal y retorna sus rutas
    para que el paso 1 los procese con Azure OCR si son PDF/imagen/Office

Dependencias:
  - .eml  → módulo estándar `email` de Python (sin dependencias extra)
  - .msg  → librería `extract-msg` (pip install extract-msg)
"""
from __future__ import annotations

import email
import email.policy
import re
import tempfile
from pathlib import Path
from typing import Any

from src.utils.logger import get_logger
from config import settings

logger = get_logger(__name__, settings.LOG_LEVEL)

# Extensiones de adjuntos que vale la pena procesar con OCR
_OCR_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif",
                   ".docx", ".xlsx", ".pptx"}


def _strip_html(html: str) -> str:
    """Quita etiquetas HTML y decodifica entidades básicas."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;",  "&", text)
    text = re.sub(r"&lt;",   "<", text)
    text = re.sub(r"&gt;",   ">", text)
    return re.sub(r"\s+", " ", text).strip()


# ── .eml ──────────────────────────────────────────────────────────────────────

def _read_eml(path: Path, attachments_dir: Path) -> dict[str, Any]:
    """Parsea un archivo .eml con el módulo estándar de Python."""
    raw = path.read_bytes()
    msg = email.message_from_bytes(raw, policy=email.policy.default)

    subject  = str(msg.get("Subject", "") or "")
    sender   = str(msg.get("From",    "") or "")
    to       = str(msg.get("To",      "") or "")
    date     = str(msg.get("Date",    "") or "")

    body_parts: list[str] = []
    attachment_paths: list[str] = []

    for part in msg.walk():
        ct   = part.get_content_type()
        disp = str(part.get("Content-Disposition", "") or "")

        if "attachment" in disp:
            filename = part.get_filename()
            if filename:
                ext = Path(filename).suffix.lower()
                if ext in _OCR_EXTENSIONS:
                    dest = attachments_dir / filename
                    dest.write_bytes(part.get_payload(decode=True))
                    attachment_paths.append(str(dest))
        elif ct == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                body_parts.append(payload.decode("utf-8", errors="replace"))
        elif ct == "text/html" and not body_parts:
            payload = part.get_payload(decode=True)
            if payload:
                body_parts.append(_strip_html(payload.decode("utf-8", errors="replace")))

    body = "\n".join(body_parts).strip()
    full_text = f"Asunto: {subject}\nDe: {sender}\nPara: {to}\nFecha: {date}\n\n{body}"

    return {
        "subject":          subject,
        "sender":           sender,
        "to":               to,
        "date":             date,
        "body":             body,
        "full_text":        full_text,
        "attachment_paths": attachment_paths,
    }


# ── .msg ──────────────────────────────────────────────────────────────────────

def _read_msg(path: Path, attachments_dir: Path) -> dict[str, Any]:
    """Parsea un archivo .msg de Outlook. Requiere: pip install extract-msg"""
    try:
        import extract_msg  # type: ignore
    except ImportError:
        raise ImportError(
            "Para leer archivos .msg instala: pip install extract-msg"
        )

    m = extract_msg.Message(str(path))

    subject  = m.subject  or ""
    sender   = m.sender   or ""
    to       = m.to       or ""
    date     = str(m.date or "")
    body     = (m.body    or "").strip()

    attachment_paths: list[str] = []
    for att in m.attachments:
        if att.longFilename:
            ext = Path(att.longFilename).suffix.lower()
            if ext in _OCR_EXTENSIONS:
                dest = attachments_dir / att.longFilename
                dest.write_bytes(att.data)
                attachment_paths.append(str(dest))

    full_text = f"Asunto: {subject}\nDe: {sender}\nPara: {to}\nFecha: {date}\n\n{body}"

    return {
        "subject":          subject,
        "sender":           sender,
        "to":               to,
        "date":             date,
        "body":             body,
        "full_text":        full_text,
        "attachment_paths": attachment_paths,
    }


# ── Función pública ───────────────────────────────────────────────────────────

def read_email(email_path: Path, attachments_dir: Path | None = None) -> dict[str, Any]:
    """
    Lee un archivo de email (.eml o .msg) y retorna su contenido.

    Args:
        email_path:      Ruta al archivo de email.
        attachments_dir: Dónde guardar los adjuntos extraídos.
                         Si es None, usa un directorio temporal.

    Returns:
        {
          file_name, full_text, subject, sender, to, date, body,
          attachment_paths,   ← rutas de adjuntos extraídos (para OCR)
          extraction_status, error_message
        }
    """
    logger.info(f"  Email → {email_path.name}")

    if attachments_dir is None:
        attachments_dir = Path(tempfile.mkdtemp(prefix="email_att_"))
    attachments_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "file_name":         email_path.name,
        "full_text":         "",
        "subject":           "",
        "sender":            "",
        "to":                "",
        "date":              "",
        "body":              "",
        "attachment_paths":  [],
        "extraction_status": "error",
        "error_message":     None,
    }

    try:
        ext = email_path.suffix.lower()
        if ext == ".eml":
            data = _read_eml(email_path, attachments_dir)
        elif ext == ".msg":
            data = _read_msg(email_path, attachments_dir)
        else:
            raise ValueError(f"Extensión no soportada para email: {ext}")

        result.update(data)
        result["extraction_status"] = "success"
        n_att = len(data["attachment_paths"])
        logger.info(f"  ✓ {email_path.name} — {n_att} adjunto(s) para OCR")

    except ImportError as exc:
        result["error_message"] = str(exc)
        logger.error(f"  ✗ {email_path.name} — {exc}")
    except Exception as exc:  # noqa: BLE001
        result["error_message"] = str(exc)
        logger.error(f"  ✗ {email_path.name} — {exc}")

    return result
