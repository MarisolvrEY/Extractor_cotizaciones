"""
Extrae los adjuntos de los archivos .msg (correos de Outlook) en la carpeta dataset.
Los adjuntos se guardan en dataset/msg_attachments/<nombre_msg_saneado>/ junto con un archivo metadata.txt.
Los archivos .msg originales no se modifican.
"""

import os
import re
from datetime import datetime

import extract_msg

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
OUTPUT_DIR = os.path.join(DATASET_DIR, "msg_attachments")


def sanitize_folder_name(filename):
    """Convierte un nombre de archivo en un nombre de carpeta seguro."""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    return name[:150]


def find_msg_files(root_dir):
    """Encuentra todos los archivos .msg, omitiendo el directorio de salida."""
    files = []
    for dirpath, _, filenames in os.walk(root_dir):
        if "msg_attachments" in dirpath:
            continue
        for fname in filenames:
            if fname.lower().endswith(".msg"):
                files.append(os.path.join(dirpath, fname))
    return files


def collect_attachments_recursive(msg):
    """Recolecta recursivamente los archivos adjuntos, incluyendo los de correos .msg anidados."""
    attachments = []
    for att in msg.attachments:
        if isinstance(att.data, extract_msg.Message):
            # Correo anidado — entrar recursivamente
            attachments.extend(collect_attachments_recursive(att.data))
        elif att.data:
            name = att.longFilename or att.shortFilename
            if name:
                attachments.append((name, att.data))
    return attachments


def extract_attachments(msg_path):
    """Abre un archivo .msg y retorna sus metadatos y adjuntos."""
    try:
        msg = extract_msg.Message(msg_path)
    except Exception as e:
        print(f"  [ERROR] Could not open {msg_path}: {e}")
        return None, []

    metadata = {
        "subject": msg.subject or "",
        "sender": msg.sender or "",
        "date": msg.date or "",
    }

    attachments = collect_attachments_recursive(msg)

    msg.close()
    return metadata, attachments


def write_metadata(output_folder, msg_path, msg_name, email_meta, attachment_names):
    """Escribe metadata.txt con información sobre el archivo .msg de origen."""
    metadata_path = os.path.join(output_folder, "metadata.txt")
    with open(metadata_path, "w", encoding="utf-8") as f:
        f.write(f"source_path: {msg_path}\n")
        f.write(f"filename: {msg_name}\n")
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

    msg_files = find_msg_files(DATASET_DIR)
    print(f"\nFound {len(msg_files)} .msg file(s)\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total_attachments = 0
    files_with_attachments = 0

    for msg_path in msg_files:
        msg_name = os.path.basename(msg_path)
        email_meta, attachments = extract_attachments(msg_path)

        if email_meta is None:
            continue

        if not attachments:
            print(f"  [SKIP] {msg_name} — no attachments")
            continue

        folder_name = sanitize_folder_name(msg_name)
        output_folder = os.path.join(OUTPUT_DIR, folder_name)
        os.makedirs(output_folder, exist_ok=True)

        attachment_names = []
        for att_name, att_data in attachments:
            att_path = os.path.join(output_folder, att_name)
            with open(att_path, "wb") as f:
                f.write(att_data)
            attachment_names.append(att_name)

        write_metadata(output_folder, msg_path, msg_name, email_meta, attachment_names)

        print(f"  [OK] {msg_name} — {len(attachments)} attachment(s) → {output_folder}")
        total_attachments += len(attachments)
        files_with_attachments += 1

    print(f"\nDone. Extracted {total_attachments} attachment(s) from {files_with_attachments} .msg file(s).")


if __name__ == "__main__":
    main()
