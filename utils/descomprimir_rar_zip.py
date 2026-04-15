"""
utils/descomprimir_rar_zip.py
------------------------------
Extrae recursivamente todos los ZIP y RAR de una carpeta.
Maneja archivos anidados (zips dentro de zips) con varias pasadas.
Elimina los comprimidos tras extraerlos y limpia carpetas __MACOSX.

Uso:
  python utils/descomprimir_rar_zip.py
  python utils/descomprimir_rar_zip.py --carpeta data/input
"""
import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

# Carpeta por defecto: data/input del proyecto
_ROOT    = Path(__file__).resolve().parent.parent
_DEFAULT = _ROOT / "data" / "input"


def is_macosx_junk(filepath: str) -> bool:
    return "__MACOSX" in filepath


def find_archives(root_dir: Path) -> list[Path]:
    return [
        f for f in root_dir.rglob("*")
        if f.is_file()
        and f.suffix.lower() in (".zip", ".rar")
        and not is_macosx_junk(str(f))
    ]


def extract_zip(filepath: Path) -> bool:
    dest = filepath.parent
    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            members = [m for m in zf.namelist() if not is_macosx_junk(m)]
            zf.extractall(dest, members=members)
        print(f"  [ZIP OK] {filepath.name}")
        return True
    except Exception as e:
        # Fallback al comando unzip del sistema (problemas de encoding)
        result = os.system(f'unzip -o -q "{filepath}" -d "{dest}"')
        if result in (0, 256):
            print(f"  [ZIP OK via unzip] {filepath.name}")
            return True
        print(f"  [ZIP FAIL] {filepath.name}: {e}")
        return False


def extract_rar(filepath: Path) -> bool:
    try:
        import rarfile  # type: ignore
        with rarfile.RarFile(filepath, "r") as rf:
            rf.extractall(filepath.parent)
        print(f"  [RAR OK] {filepath.name}")
        return True
    except ImportError:
        print("  [RAR SKIP] pip install rarfile  +  unrar en el sistema")
        return False
    except Exception as e:
        print(f"  [RAR FAIL] {filepath.name}: {e}")
        return False


def run(root_dir: Path) -> int:
    """Extrae todos los comprimidos. Retorna total extraídos."""
    total = 0
    print(f"Carpeta: {root_dir}")

    while True:
        archives = find_archives(root_dir)
        if not archives:
            break
        print(f"\n  {len(archives)} comprimido(s) encontrado(s):")
        extraidos = 0
        for f in archives:
            ok = extract_zip(f) if f.suffix.lower() == ".zip" else extract_rar(f)
            if ok:
                f.unlink()
                extraidos += 1
                total += 1
        if extraidos == 0:
            break  # sin progreso → evitar bucle infinito

    # Limpiar __MACOSX
    for d in root_dir.rglob("__MACOSX"):
        if d.is_dir():
            shutil.rmtree(d)
            print(f"  Eliminado: {d}")

    remaining = find_archives(root_dir)
    if remaining:
        print(f"\n  {len(remaining)} archivo(s) no se pudieron extraer:")
        for f in remaining:
            print(f"    {f}")
    else:
        print("\n  Todos los comprimidos extraídos correctamente.")

    return total


def _args():
    p = argparse.ArgumentParser(description="Extrae ZIP/RAR recursivamente.")
    p.add_argument("--carpeta", type=Path, default=_DEFAULT,
                   help=f"Carpeta a procesar (default: {_DEFAULT})")
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    if not args.carpeta.exists():
        print(f"[ERROR] No existe: {args.carpeta}")
        sys.exit(1)
    n = run(args.carpeta)
    print(f"\nTotal extraídos: {n}")
