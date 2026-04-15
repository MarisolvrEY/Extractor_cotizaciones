"""
utils/discovery.py
-------------------
Genera un inventario JSON de todos los archivos de una carpeta.
Útil para hacer un diagnóstico antes de correr el pipeline.

Output:
  data/output/  →  inventario_<carpeta>.json

Uso:
  python utils/discovery.py
  python utils/discovery.py --carpeta data/input
  python utils/discovery.py --carpeta data/procesables
"""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

_ROOT    = Path(__file__).resolve().parent.parent
_DEFAULT = _ROOT / "data" / "input"
_OUT_DIR = _ROOT / "data" / "output"


def run(root_dir: Path) -> Path:
    files = []
    ext_counter: Counter = Counter()

    skip_dirs = {"excel_embedded", "msg_attachments", "eml_attachments", "docx_embedded"}

    for dirpath, dirnames, filenames in root_dir.walk() if hasattr(root_dir, "walk") else _walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fname in filenames:
            filepath = dirpath / fname
            ext      = filepath.suffix.lower()
            files.append({
                "filename":      fname,
                "extension":     ext,
                "size_bytes":    filepath.stat().st_size,
                "size_kb":       round(filepath.stat().st_size / 1024, 2),
                "path":          str(filepath),
                "parent_folder": filepath.parent.name,
            })
            ext_counter[ext] += 1

    output = {
        "generado":    datetime.now().isoformat(),
        "carpeta":     str(root_dir),
        "total_files": len(files),
        "extensions":  dict(ext_counter.most_common()),
        "files":       files,
    }

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUT_DIR / f"inventario_{root_dir.name}.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Total archivos : {len(files)}")
    print(f"\nExtensiones:")
    for ext, count in ext_counter.most_common():
        print(f"  {ext or '(sin extensión)':20} {count}")
    print(f"\nInventario guardado en: {out_path}")
    return out_path


def _walk(root: Path):
    """Compatibilidad Python < 3.12 (Path.walk no existe)."""
    import os
    for dp, dn, fn in os.walk(root):
        yield Path(dp), dn, fn


def _args():
    p = argparse.ArgumentParser(description="Genera inventario JSON de una carpeta.")
    p.add_argument("--carpeta", type=Path, default=_DEFAULT,
                   help=f"Carpeta a analizar (default: {_DEFAULT})")
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    if not args.carpeta.exists():
        print(f"[ERROR] No existe: {args.carpeta}")
        sys.exit(1)
    run(args.carpeta)
