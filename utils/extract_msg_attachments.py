"""
utils/extract_msg_attachments.py
---------------------------------
Extrae los adjuntos de archivos .msg (Outlook) de una carpeta.
Los adjuntos se guardan en data/output/msg_attachments/<nombre_msg>/.
Los .msg originales NO se modifican.

Requiere: pip install extract-msg

Uso:
  python utils/extract_msg_attachments.py
  python utils/extract_msg_attachments.py --carpeta data/input
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

_ROOT    = Path(__file__).resolve().parent.parent
_DEFAULT = _ROOT / "data" / "input"
_OUT_DIR = _ROOT / "data" / "output" / "msg_attachments"


def _sanitize(filename: str) -> str:
    name = Path(filename).stem
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name.strip(". ")[:150]


def _collect_attachments(msg) -> list:
    import extract_msg as em  # type: ignore
    attachments = []
    for att in msg.attachments:
        if isinstance(att.data, em.Message):
            attachments.extend(_collect_attachments(att.data))
        elif att.data:
            name = att.longFilename or att.shortFilename
            if name:
                attachments.append((name, att.data))
    return attachments


def run(root_dir: Path) -> dict:
    try:
        import extract_msg  # noqa: F401
    except ImportError:
        print("[ERROR] pip install extract-msg")
        return {}

    msg_files = [
        f for f in root_dir.rglob("*.msg")
        if "msg_attachments" not in str(f)
    ]
    print(f"Carpeta  : {root_dir}")
    print(f"Archivos : {len(msg_files)} .msg\n")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    total_att = 0
    con_adj   = 0

    for msg_path in msg_files:
        import extract_msg as em
        try:
            msg = em.Message(str(msg_path))
        except Exception as e:
            print(f"  [ERROR] {msg_path.name}: {e}")
            continue

        subject     = msg.subject or ""
        sender      = msg.sender  or ""
        date        = str(msg.date or "")
        attachments = _collect_attachments(msg)
        msg.close()

        if not attachments:
            print(f"  [SKIP] {msg_path.name} — sin adjuntos")
            continue

        out_folder = _OUT_DIR / _sanitize(msg_path.name)
        out_folder.mkdir(parents=True, exist_ok=True)

        names = []
        for att_name, att_data in attachments:
            dest = out_folder / att_name
            dest.write_bytes(att_data)
            names.append(att_name)

        (out_folder / "metadata.txt").write_text(
            f"source: {msg_path}\nsubject: {subject}\nsender: {sender}\n"
            f"date: {date}\nextracted: {datetime.now().isoformat()}\n\n"
            + "\n".join(f"  - {n}" for n in names),
            encoding="utf-8",
        )

        print(f"  [OK] {msg_path.name} → {len(attachments)} adjunto(s)")
        total_att += len(attachments)
        con_adj   += 1

    print(f"\nTotal: {total_att} adjunto(s) de {con_adj} .msg")
    print(f"Guardados en: {_OUT_DIR}")
    return {"archivos": len(msg_files), "con_adjuntos": con_adj, "adjuntos": total_att}


def _args():
    p = argparse.ArgumentParser(description="Extrae adjuntos de archivos .msg.")
    p.add_argument("--carpeta", type=Path, default=_DEFAULT)
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    if not args.carpeta.exists():
        print(f"[ERROR] No existe: {args.carpeta}")
        sys.exit(1)
    run(args.carpeta)
