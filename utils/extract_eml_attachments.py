"""
Extrae los adjuntos de los archivos .eml (correos estándar) en la carpeta dataset.
Los adjuntos se guardan en dataset/eml_attachments/<nombre_eml_saneado>/ junto con un archivo metadata.txt.
Los archivos .eml originales no se modifican.
Usa el módulo email incorporado de Python — sin dependencias externas.
"""

import os
import re
from datetime import datetime
from email import policy
from email.parser import BytesParser

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
OUTPUT_DIR = os.path.join(DATASET_DIR, "eml_attachments")


def sanitize_folder_name(filename):
    """Convierte un nombre de archivo en un nombre de carpeta seguro."""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    return name[:150]


def find_eml_files(root_dir):
    """Encuentra todos los archivos .eml, omitiendo el directorio de salida."""
    files = []
    for dirpath, _, filenames in os.walk(root_dir):
        if "eml_attachments" in dirpath:
            continue
        for fname in filenames:
            if fname.lower().endswith(".eml"):
                files.append(os.path.join(dirpath, fname))
    return files


def collect_attachments_recursive(msg):
    """Recorre todas las partes del correo; recolecta las que son adjuntos.
    Entra recursivamente a las partes message/rfc822 anidadas para encontrar adjuntos internos."""
    attachments = []
    for part in msg.walk():
        content_type = part.get_content_type()

        # Correo anidado — entrar recursivamente a su contenido
        if content_type == "message/rfc822":
            payload = part.get_payload()
            if payload:
                inner = payload[0] if isinstance(payload, list) else payload
                attachments.extend(collect_attachments_recursive(inner))
            continue

        # Omitir las partes contenedoras multipart
        if part.is_multipart():
            continue

        # Un adjunto tiene un nombre de archivo (Content-Disposition: attachment/inline con filename)
        filename = part.get_filename()
        if not filename:
            continue

        data = part.get_payload(decode=True)
        if data:
            attachments.append((filename, data))

    return attachments


def extract_attachments(eml_path):
    """Parsea un archivo .eml y retorna sus metadatos y adjuntos."""
    try:
        with open(eml_path, "rb") as f:
            msg = BytesParser(policy=policy.default).parse(f)
    except Exception as e:
        print(f"  [ERROR] Could not parse {eml_path}: {e}")
        return None, []

    metadata = {
        "subject": msg.get("Subject", "") or "",
        "sender": msg.get("From", "") or "",
        "date": msg.get("Date", "") or "",
    }

    attachments = collect_attachments_recursive(msg)
    return metadata, attachments


def write_metadata(output_folder, eml_path, eml_name, email_meta, attachment_names):
    """Escribe metadata.txt con información sobre el archivo .eml de origen."""
    metadata_path = os.path.join(output_folder, "metadata.txt")
    with open(metadata_path, "w", encoding="utf-8") as f:
        f.write(f"source_path: {eml_path}\n")
        f.write(f"filename: {eml_name}\n")
        f.write(f"subject: {email_meta['subject']}\n")
        f.write(f"sender: {email_meta['sender']}\n")
        f.write(f"date: {email_meta['date']}\n")
        f.write(f"attachment_count: {len(attachment_names)}\n")
        f.write(f"extracted_on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"\nattachments:\n")
        for name in attachment_names:
            f.write(f"  - {name}\n")


def main():
    print(f"Dataset directory: {DATASET_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")

    eml_files = find_eml_files(DATASET_DIR)
    print(f"\nFound {len(eml_files)} .eml file(s)\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total_attachments = 0
    files_with_attachments = 0

    for eml_path in eml_files:
        eml_name = os.path.basename(eml_path)
        email_meta, attachments = extract_attachments(eml_path)

        if email_meta is None:
            continue

        if not attachments:
            print(f"  [SKIP] {eml_name} — no attachments")
            continue

        folder_name = sanitize_folder_name(eml_name)
        output_folder = os.path.join(OUTPUT_DIR, folder_name)
        os.makedirs(output_folder, exist_ok=True)

        attachment_names = []
        for att_name, att_data in attachments:
            att_path = os.path.join(output_folder, att_name)
            with open(att_path, "wb") as f:
                f.write(att_data)
            attachment_names.append(att_name)

        write_metadata(output_folder, eml_path, eml_name, email_meta, attachment_names)

        print(f"  [OK] {eml_name} — {len(attachments)} attachment(s) → {output_folder}")
        total_attachments += len(attachments)
        files_with_attachments += 1

    print(f"\nDone. Extracted {total_attachments} attachment(s) from {files_with_attachments} .eml file(s).")


if __name__ == "__main__":
    main()
