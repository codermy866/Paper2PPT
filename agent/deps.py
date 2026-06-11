from __future__ import annotations

import importlib
import os
import shutil
from pathlib import Path
from typing import Any, Dict


def _importable(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


def _tesseract_cmd() -> str:
    env = os.getenv("TESSERACT_CMD", "").strip()
    if env and Path(env).exists():
        return env
    bundled = Path(__file__).resolve().parent / "runtime" / "tesseract" / "usr" / "bin" / "tesseract"
    if bundled.exists():
        return str(bundled)
    found = shutil.which("tesseract")
    return found or ""


def check_dependencies() -> Dict[str, Any]:
    tesseract = _tesseract_cmd()
    tessdata = os.getenv("TESSDATA_PREFIX", "").strip()
    bundled_tessdata = Path(__file__).resolve().parent / "runtime" / "tesseract" / "usr" / "share" / "tesseract-ocr" / "4.00" / "tessdata"
    if not tessdata and bundled_tessdata.exists():
        tessdata = str(bundled_tessdata)

    return {
        "pymupdf": _importable("fitz"),
        "pdfplumber": _importable("pdfplumber"),
        "pytesseract": _importable("pytesseract"),
        "pillow": _importable("PIL"),
        "tesseract_binary": bool(tesseract),
        "tesseract_cmd": tesseract,
        "tessdata_prefix": tessdata,
        "ocr_ready": bool(tesseract) and _importable("pytesseract") and _importable("PIL"),
        "figures_ready": _importable("fitz"),
        "tables_ready": _importable("pdfplumber"),
    }
