"""
Busca y extrae recursivamente todos los archivos .zip y .rar en la carpeta dataset.
Extrae el contenido al mismo directorio donde se encuentra el archivo comprimido.
Maneja archivos anidados (archivos dentro de archivos) ejecutando varias pasadas.
"""

import os
import shutil
import zipfile
import rarfile

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")


def is_macosx_junk(filepath):
    """Verifica si un archivo es un artefacto (resource fork) de macOS."""
    return "__MACOSX" in filepath


def find_archives(root_dir):
    """Encuentra todos los archivos .zip y .rar bajo root_dir, omitiendo los artefactos __MACOSX."""
    archives = []
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            full_path = os.path.join(dirpath, fname)
            if fname.lower().endswith((".zip", ".rar")) and not is_macosx_junk(full_path):
                archives.append(full_path)
    return archives


def extract_zip(filepath):
    """Extrae un archivo .zip a su directorio padre.
    Recurre al comando unzip del sistema para archivos con problemas de codificación."""
    dest = os.path.dirname(filepath)
    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            zf.extractall(dest)
        print(f"  [ZIP OK] {filepath}")
        return True
    except Exception as e:
        error_msg = str(e)
        if "File name in directory" in error_msg and "differ" in error_msg:
            # Problema de codificación — usar el unzip del sistema como alternativa
            result = os.system(f'unzip -o -q "{filepath}" -d "{dest}"')
            # código 0 = OK, 256 (1) = advertencia (p.ej. nombres inconsistentes) pero los archivos se extrajeron
            if result in (0, 256):
                print(f"  [ZIP OK via unzip] {filepath}")
                return True
            else:
                print(f"  [ZIP FAIL via unzip] {filepath}: exit code {result}")
                return False
        else:
            print(f"  [ZIP FAIL] {filepath}: {e}")
            return False


def extract_rar(filepath):
    """Extrae un archivo .rar a su directorio padre."""
    dest = os.path.dirname(filepath)
    try:
        with rarfile.RarFile(filepath, "r") as rf:
            rf.extractall(dest)
        print(f"  [RAR OK] {filepath}")
        return True
    except (rarfile.BadRarFile, Exception) as e:
        print(f"  [RAR FAIL] {filepath}: {e}")
        return False


def run_extraction_pass(root_dir):
    """Ejecuta una pasada: busca y extrae todos los archivos. Retorna la cantidad de extracciones exitosas."""
    archives = find_archives(root_dir)
    if not archives:
        return 0

    print(f"\nFound {len(archives)} archive(s):")
    extracted = 0
    for filepath in archives:
        if filepath.lower().endswith(".zip"):
            success = extract_zip(filepath)
        else:
            success = extract_rar(filepath)

        if success:
            os.remove(filepath)
            extracted += 1

    return extracted


def main():
    print(f"Dataset directory: {DATASET_DIR}")
    pass_num = 0

    while True:
        pass_num += 1
        print(f"\n--- Pass {pass_num} ---")
        extracted = run_extraction_pass(DATASET_DIR)
        print(f"Extracted {extracted} archive(s) in pass {pass_num}.")

        if extracted == 0:
            break

    # Eliminar los directorios __MACOSX
    for dirpath, dirnames, _ in os.walk(DATASET_DIR, topdown=False):
        for dname in dirnames:
            if dname == "__MACOSX":
                macos_path = os.path.join(dirpath, dname)
                shutil.rmtree(macos_path)
                print(f"Removed macOS artifact: {macos_path}")

    remaining = find_archives(DATASET_DIR)
    if remaining:
        print(f"\n{len(remaining)} archive(s) could not be extracted:")
        for f in remaining:
            print(f"  {f}")
    else:
        print("\nAll archives extracted successfully.")


if __name__ == "__main__":
    main()
