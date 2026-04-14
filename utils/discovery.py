"""
Genera un inventario en JSON de todos los archivos en la carpeta dataset.
Produce dataset_inventory.json con información básica de cada archivo
y un resumen de las extensiones encontradas.
"""

import json
import os
from collections import Counter

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset_inventory.json")

# Omitir los directorios creados por nuestros scripts de preprocesamiento
SKIP_DIRS = {"excel_embedded", "msg_attachments"}


def main():
    files = []
    ext_counter = Counter()

    for dirpath, dirnames, filenames in os.walk(DATASET_DIR):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            filepath = os.path.join(dirpath, fname)
            ext = os.path.splitext(fname)[1].lower()
            size = os.path.getsize(filepath)

            files.append({
                "filename": fname,
                "extension": ext,
                "size_bytes": size,
                "path": filepath,
                "parent_folder": os.path.basename(dirpath),
            })
            ext_counter[ext] += 1

    summary = {
        "total_files": len(files),
        "extensions": dict(ext_counter.most_common()),
    }

    output = {
        "summary": summary,
        "files": files,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Total files: {len(files)}")
    print(f"\nExtensions breakdown:")
    for ext, count in ext_counter.most_common():
        print(f"  {ext or '(no extension)'}: {count}")
    print(f"\nInventory saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
