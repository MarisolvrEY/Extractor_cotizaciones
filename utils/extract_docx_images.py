"""
Extrae las imágenes incrustadas en archivos .docx de la carpeta dataset.
Las imágenes se guardan en dataset/docx_embedded/<nombre_docx_saneado>/ junto con un archivo metadata.txt.
Los archivos .docx originales no se modifican.
Usa solo la librería estándar — los .docx son archivos ZIP con imágenes en word/media/.
"""

import os
import re
import zipfile
from datetime import datetime

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
OUTPUT_DIR = os.path.join(DATASET_DIR, "docx_embedded")


def sanitize_folder_name(filename):
    """Convierte un nombre de archivo en un nombre de carpeta seguro."""
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    return name[:150]


def find_docx_files(root_dir):
    """Encuentra todos los archivos .docx, omitiendo el directorio de salida."""
    files = []
    for dirpath, _, filenames in os.walk(root_dir):
        if "docx_embedded" in dirpath:
            continue
        for fname in filenames:
            if fname.lower().endswith(".docx"):
                files.append(os.path.join(dirpath, fname))
    return files


def extract_images_from_docx(docx_path):
    """Extrae imágenes desde word/media/ dentro de la estructura ZIP del .docx.
    Retorna una lista de tuplas (nombre_imagen, bytes_imagen)."""
    images = []
    try:
        with zipfile.ZipFile(docx_path, "r") as zf:
            for entry in zf.namelist():
                if entry.startswith("word/media/"):
                    image_name = os.path.basename(entry)
                    if image_name:
                        image_data = zf.read(entry)
                        images.append((image_name, image_data))
    except (zipfile.BadZipFile, Exception) as e:
        print(f"  [ERROR] Could not read {docx_path}: {e}")
    return images


def write_metadata(output_folder, docx_path, docx_name, image_filenames):
    """Escribe metadata.txt con información sobre el archivo .docx de origen."""
    metadata_path = os.path.join(output_folder, "metadata.txt")
    with open(metadata_path, "w", encoding="utf-8") as f:
        f.write(f"source_path: {docx_path}\n")
        f.write(f"filename: {docx_name}\n")
        f.write(f"image_count: {len(image_filenames)}\n")
        f.write(f"extracted_on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"\nimages:\n")
        for img_name in image_filenames:
            f.write(f"  - {img_name}\n")


def main():
    print(f"Dataset directory: {DATASET_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")

    docx_files = find_docx_files(DATASET_DIR)
    print(f"\nFound {len(docx_files)} .docx file(s)\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total_images = 0
    files_with_images = 0

    for docx_path in docx_files:
        docx_name = os.path.basename(docx_path)
        images = extract_images_from_docx(docx_path)

        if not images:
            print(f"  [SKIP] {docx_name} — no images")
            continue

        folder_name = sanitize_folder_name(docx_name)
        output_folder = os.path.join(OUTPUT_DIR, folder_name)
        os.makedirs(output_folder, exist_ok=True)

        image_filenames = []
        for img_name, img_data in images:
            img_path = os.path.join(output_folder, img_name)
            with open(img_path, "wb") as f:
                f.write(img_data)
            image_filenames.append(img_name)

        write_metadata(output_folder, docx_path, docx_name, image_filenames)

        print(f"  [OK] {docx_name} — {len(images)} image(s) → {output_folder}")
        total_images += len(images)
        files_with_images += 1

    print(f"\nDone. Extracted {total_images} image(s) from {files_with_images} .docx file(s).")


if __name__ == "__main__":
    main()
