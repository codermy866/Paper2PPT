#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MIRROR="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
HOST="${PIP_TRUSTED_HOST:-pypi.tuna.tsinghua.edu.cn}"

echo "[Paper2PPT] Installing Python dependencies via ${MIRROR} ..."
python3 -m pip install --user -r requirements.txt \
  -i "$MIRROR" \
  --trusted-host "$HOST"

echo
echo "[Paper2PPT] Checking optional capabilities ..."
python3 - <<'PY'
from deps import check_dependencies
info = check_dependencies()
for key in ("pymupdf", "pdfplumber", "pytesseract", "pillow", "tesseract_binary", "ocr_ready", "figures_ready", "tables_ready"):
    print(f"  - {key}: {info[key]}")
if not info["tesseract_binary"]:
    print()
    print("OCR binary missing. Install system Tesseract (needs sudo):")
    print("  sudo apt-get install -y tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng")
    print("Or set TESSERACT_CMD=/path/to/tesseract if installed elsewhere.")
PY

echo
echo "[Paper2PPT] Done."
