"""
utils/extract_docx_images.py
------------------------------
Extrae las imágenes incrustadas en archivos .docx de una carpeta.
Las imágenes se guardan en data/output/docx_embedded/<nombre_docx>/.
Los .docx originales NO se modifican.

No requiere librerías externas — los .docx son ZIPs con imágenes en word/media/.

Uso:
  python utils/extract_docx_images.py
  python utils/extract_docx_images.py --carpeta data/input
"""
import argparse
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

_ROOT    = Path(__file__).resolve().parent.parent
_DEFAULT = _ROOT / "data" / "input"
_OUT_DIR = _ROOT / "data" / "output" / "docx_embedded"


def _sanitize(filename: str) -> str:
    name = Path(filename).stem
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name.strip(". ")[:150]


def run(root_dir: Path) -> dict:
    docx_files = [
        f for f in root_dir.rglob("*.docx")
        if "docx_embedded" not in str(f)
    ]
    print(f"Carpeta  : {root_dir}")
    print(f"Archivos : {len(docx_files)} .docx\n")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    total_imgs = 0
    con_imgs   = 0

    for docx_path in docx_files:
        images = []
        try:
            with zipfile.ZipFile(docx_path, "r") as zf:
                for entry in zf.namelist():
                    if entry.startswith("word/media/"):
                        img_name = Path(entry).name
                        if img_name:
                            images.append((img_name, zf.read(entry)))
        except Exception as e:
            print(f"  [ERROR] {docx_path.name}: {e}")
            continue

        if not images:
            print(f"  [SKIP] {docx_path.name} — sin imágenes")
            continue

        out_folder = _OUT_DIR / _sanitize(docx_path.name)
        out_folder.mkdir(parents=True, exist_ok=True)

        names = []
        for img_name, img_data in images:
            (out_folder / img_name).write_bytes(img_data)
            names.append(img_name)

        (out_folder / "metadata.txt").write_text(
            f"source: {docx_path}\nimage_count: {len(images)}\n"
            f"extracted: {datetime.now().isoformat()}\n\n"
            + "\n".join(f"  - {n}" for n in names),
            encoding="utf-8",
        )

        print(f"  [OK] {docx_path.name} → {len(images)} imagen(es)")
        total_imgs += len(images)
        con_imgs   += 1

    print(f"\nTotal: {total_imgs} imagen(es) de {con_imgs} .docx")
    print(f"Guardadas en: {_OUT_DIR}")
    return {"archivos": len(docx_files), "con_imagenes": con_imgs, "imagenes": total_imgs}


def _args():
    p = argparse.ArgumentParser(description="Extrae imágenes incrustadas de archivos .docx.")
    p.add_argument("--carpeta", type=Path, default=_DEFAULT)
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    if not args.carpeta.exists():
        print(f"[ERROR] No existe: {args.carpeta}")
        sys.exit(1)
    run(args.carpeta)
