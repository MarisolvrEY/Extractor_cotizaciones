"""
utils/extract_eml_attachments.py
---------------------------------
Extrae los adjuntos de archivos .eml de una carpeta.
Los adjuntos se guardan en data/output/eml_attachments/<nombre_eml>/.
Los .eml originales NO se modifican.

Uso:
  python utils/extract_eml_attachments.py
  python utils/extract_eml_attachments.py --carpeta data/input
"""
import argparse
import re
import sys
from datetime import datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path

_ROOT    = Path(__file__).resolve().parent.parent
_DEFAULT = _ROOT / "data" / "input"
_OUT_DIR = _ROOT / "data" / "output" / "eml_attachments"


def _sanitize(filename: str) -> str:
    name = Path(filename).stem
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name.strip(". ")[:150]


def _collect_attachments(msg):
    """Recorre el mensaje recursivamente y recolecta adjuntos."""
    attachments = []
    for part in msg.walk():
        ct = part.get_content_type()
        if ct == "message/rfc822":
            payload = part.get_payload()
            inner   = payload[0] if isinstance(payload, list) else payload
            attachments.extend(_collect_attachments(inner))
            continue
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if not filename:
            continue
        data = part.get_payload(decode=True)
        if data:
            attachments.append((filename, data))
    return attachments


def run(root_dir: Path) -> dict:
    eml_files = [
        f for f in root_dir.rglob("*.eml")
        if "eml_attachments" not in str(f)
    ]
    print(f"Carpeta  : {root_dir}")
    print(f"Archivos : {len(eml_files)} .eml\n")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    total_att = 0
    con_adj   = 0

    for eml_path in eml_files:
        with open(eml_path, "rb") as f:
            msg = BytesParser(policy=policy.default).parse(f)

        subject     = msg.get("Subject", "") or ""
        sender      = msg.get("From",    "") or ""
        date        = msg.get("Date",    "") or ""
        attachments = _collect_attachments(msg)

        if not attachments:
            print(f"  [SKIP] {eml_path.name} — sin adjuntos")
            continue

        out_folder = _OUT_DIR / _sanitize(eml_path.name)
        out_folder.mkdir(parents=True, exist_ok=True)

        names = []
        for att_name, att_data in attachments:
            dest = out_folder / att_name
            dest.write_bytes(att_data)
            names.append(att_name)

        # metadata.txt
        (out_folder / "metadata.txt").write_text(
            f"source: {eml_path}\nsubject: {subject}\nsender: {sender}\n"
            f"date: {date}\nextracted: {datetime.now().isoformat()}\n\n"
            + "\n".join(f"  - {n}" for n in names),
            encoding="utf-8",
        )

        print(f"  [OK] {eml_path.name} → {len(attachments)} adjunto(s)")
        total_att += len(attachments)
        con_adj   += 1

    print(f"\nTotal: {total_att} adjunto(s) de {con_adj} .eml")
    print(f"Guardados en: {_OUT_DIR}")
    return {"archivos": len(eml_files), "con_adjuntos": con_adj, "adjuntos": total_att}


def _args():
    p = argparse.ArgumentParser(description="Extrae adjuntos de archivos .eml.")
    p.add_argument("--carpeta", type=Path, default=_DEFAULT)
    return p.parse_args()


if __name__ == "__main__":
    args = _args()
    if not args.carpeta.exists():
        print(f"[ERROR] No existe: {args.carpeta}")
        sys.exit(1)
    run(args.carpeta)
