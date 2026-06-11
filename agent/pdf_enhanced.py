from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import List, Tuple

from deps import _tesseract_cmd
from models import ParsedFigure, ParsedTable
from text_utils import looks_like_figure_legend_noise


def _trim_caption_to_sentence(caption: str) -> str:
    """Cut a greedily-matched caption at the first sentence boundary or the next
    figure/table marker, so legend and axis text after the caption is dropped."""
    text = re.sub(r"\s+", " ", caption or "").strip()
    if not text:
        return ""
    # Stop before a second figure/table label that got pulled in.
    text = re.split(r"\s+(?:Figure|Fig\.|Table|图|表)\s*\d+", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    # Keep only the first sentence; captions are normally a single sentence.
    sentence = re.split(r"(?<=[。.!?！？])\s", text, maxsplit=1)[0].strip()
    return (sentence or text).strip(" -·:：")


def text_quality_score(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    signal = text_signal_length(stripped)
    suspicious = len(re.findall(r"[\ufffdÃÂâ€œâ€™�\x00-\x08\x0b\x0c\x0e-\x1f]", stripped))
    weird = len(re.findall(r"[^\u4e00-\u9fffA-Za-z0-9\s,.;:!?，。；：！？、()（）\[\]{}\-/+*=<>%&'\"“”‘’]", stripped))
    penalty = suspicious * 3 + weird * 0.7
    return max(0.0, signal - penalty) / max(len(stripped), 1)


def text_signal_length(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text))


def is_text_garbled(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    signal = text_signal_length(stripped)
    if signal < 12:
        return True
    replacement_count = stripped.count("\ufffd")
    suspicious = len(re.findall(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", stripped))
    mojibake = len(re.findall(r"[ÃÂâ€œâ€™�]", stripped))
    if replacement_count + suspicious + mojibake >= max(6, len(stripped) * 0.02):
        return True
    readable = signal + len(re.findall(r"[\s,.;:!?，。；：！？、()（）\-]", stripped))
    return readable / max(len(stripped), 1) < 0.45


def extract_text_with_pymupdf(pdf_path: str) -> str:
    try:
        import fitz  # type: ignore
    except ImportError:
        return ""
    chunks: List[str] = []
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            blocks = sorted(page.get_text("blocks"), key=lambda item: (item[1], item[0]))
            page_lines = []
            for block in blocks:
                text = re.sub(r"[ \t]+", " ", str(block[4])).strip()
                if text:
                    page_lines.append(text)
            if page_lines:
                chunks.append("\n".join(page_lines))
        doc.close()
    except Exception:
        return ""
    return "\n\n".join(chunks)


def detect_language(text: str) -> str:
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    total = chinese + latin
    if total == 0:
        return "en"
    if chinese >= 8 and chinese / total >= 0.15:
        return "zh"
    if chinese > latin:
        return "zh"
    return "en"


def reflow_dual_column_text(page_text: str) -> Tuple[str, bool]:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if len(lines) < 8:
        return page_text, False

    mid = len(lines) // 2
    left, right = lines[:mid], lines[mid:]
    if abs(len(left) - len(right)) > max(4, len(lines) * 0.35):
        return page_text, False

    left_avg = sum(len(x) for x in left) / max(len(left), 1)
    right_avg = sum(len(x) for x in right) / max(len(right), 1)
    if left_avg < 18 or right_avg < 18:
        return page_text, False

    merged = []
    for idx in range(max(len(left), len(right))):
        if idx < len(left):
            merged.append(left[idx])
        if idx < len(right):
            merged.append(right[idx])
    return "\n".join(merged), True


def extract_tables_from_text(raw_text: str) -> List[ParsedTable]:
    tables: List[ParsedTable] = []
    blocks = re.split(r"\n{2,}", raw_text)
    for idx, block in enumerate(blocks):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        pipe_rows = [line for line in lines if "|" in line and line.count("|") >= 2]
        if len(pipe_rows) >= 2:
            markdown = "\n".join(pipe_rows[:20])
            tables.append(
                ParsedTable(
                    page_index=0,
                    table_id=f"table-{len(tables) + 1}",
                    markdown=markdown,
                    row_count=len(pipe_rows),
                    col_count=max(line.count("|") for line in pipe_rows),
                )
            )
            continue
        if len(lines) >= 3 and all(re.search(r"\s{2,}|\t", line) for line in lines[:5]):
            markdown = "\n".join(f"| {line.replace(chr(9), ' | ')} |" for line in lines[:12])
            tables.append(
                ParsedTable(
                    page_index=0,
                    table_id=f"table-{len(tables) + 1}",
                    markdown=markdown,
                    row_count=len(lines),
                    col_count=2,
                )
            )
    return tables[:6]


def _save_pixmap_as_white_rgb_png(pix: "object", output_path: Path) -> None:
    """Save rendered PDF pixels with a white background to avoid black alpha masks."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        pix.save(str(output_path))
        return

    mode = "RGBA" if getattr(pix, "alpha", 0) else "RGB"
    image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    if image.mode in {"RGBA", "LA"}:
        canvas = Image.new("RGB", image.size, "white")
        canvas.paste(image, mask=image.getchannel("A"))
        image = canvas
    else:
        image = image.convert("RGB")
    image.save(output_path, "PNG")


def _render_pdf_clip_image(
    pdf_path: str,
    page_index: int,
    bbox: tuple[float, float, float, float] | None,
    output_path: Path,
    zoom: float = 2.0,
) -> str:
    try:
        import fitz  # type: ignore
    except ImportError:
        return ""

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(pdf_path)
        page = doc[page_index]
        rect = fitz.Rect(*bbox) if bbox else page.rect
        rect = rect & page.rect
        if rect.is_empty or rect.width < 4 or rect.height < 4:
            doc.close()
            return ""
        pix = page.get_pixmap(
            matrix=fitz.Matrix(zoom, zoom),
            clip=rect,
            colorspace=fitz.csRGB,
            alpha=False,
        )
        _save_pixmap_as_white_rgb_png(pix, output_path)
        doc.close()
        return str(output_path)
    except Exception:
        return ""


def _normalize_image_file_to_white_png(input_path: Path, output_path: Path) -> str:
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        if input_path != output_path:
            shutil.copyfile(input_path, output_path)
        return str(output_path)

    try:
        image = Image.open(input_path)
        if image.mode in {"RGBA", "LA"}:
            canvas = Image.new("RGB", image.size, "white")
            canvas.paste(image, mask=image.getchannel("A"))
            image = canvas
        else:
            image = image.convert("RGB")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, "PNG")
        return str(output_path)
    except Exception:
        return ""


def _is_image_file_usable(image_path: str) -> bool:
    try:
        from PIL import Image, ImageStat  # type: ignore
    except ImportError:
        return bool(image_path and Path(image_path).exists())

    try:
        image = Image.open(image_path).convert("RGB")
        width, height = image.size
        if width < 80 or height < 60:
            return False
        thumb = image.resize((64, 64))
        stat = ImageStat.Stat(thumb)
        avg = sum(stat.mean) / 3
        spread = sum(stat.stddev) / 3
        if avg < 12:
            return False
        if avg > 250 and spread < 3:
            return False
        return True
    except Exception:
        return False


def _figure_caption_from_page_text(page_text: str, page_index: int) -> str:
    compact = re.sub(r"\s+", " ", page_text or "").strip()
    patterns = [
        r"(?:Figure|Fig\.)\s*\d+[:：.\s-].{0,220}",
        r"图\s*\d+[:：.\s-].{0,180}",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact, re.IGNORECASE)
        if match:
            caption = _trim_caption_to_sentence(match.group(0).strip())
            if caption and not looks_like_figure_legend_noise(caption):
                return caption
    hints = []
    lowered = compact.lower()
    for label, tokens in (
        ("方法相关图片", ("method", "framework", "architecture", "algorithm", "model", "方法", "框架", "算法", "模型")),
        ("实验结果图片", ("result", "experiment", "performance", "metric", "ablation", "结果", "实验", "指标", "消融")),
        ("数据与设置图片", ("dataset", "benchmark", "setting", "数据集", "评价指标", "设置")),
    ):
        if any(token in lowered for token in tokens):
            hints.append(label)
    hint = " / ".join(hints) if hints else "论文图片"
    return f"第 {page_index + 1} 页{hint}"


def extract_figures_from_pdf(pdf_path: str, output_dir: Path) -> List[ParsedFigure]:
    figures: List[ParsedFigure] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        import fitz  # type: ignore
    except ImportError:
        return figures

    doc = fitz.open(pdf_path)
    fig_idx = 0
    for page_index, page in enumerate(doc):
        page_text = page.get_text("text") or ""
        caption = _figure_caption_from_page_text(page_text, page_index)
        for img in page.get_images(full=True):
            xref = img[0]
            rects = page.get_image_rects(xref)
            rendered = False
            for rect_idx, rect in enumerate(rects[:2]):
                if rect.width < 24 or rect.height < 24:
                    continue
                fig_idx += 1
                pad_x = min(12, rect.width * 0.08)
                pad_y = min(12, rect.height * 0.08)
                clip = (
                    rect.x0 - pad_x,
                    rect.y0 - pad_y,
                    rect.x1 + pad_x,
                    rect.y1 + pad_y,
                )
                out_path = output_dir / f"figure_p{page_index + 1}_{fig_idx}.png"
                image_path = _render_pdf_clip_image(pdf_path, page_index, clip, out_path)
                if not image_path or not _is_image_file_usable(image_path):
                    fig_idx -= 1
                    continue
                rendered = True
                figures.append(
                    ParsedFigure(
                        page_index=page_index,
                        figure_id=f"figure-{fig_idx}",
                        caption=caption,
                        image_path=image_path,
                    )
                )
                if len(figures) >= 8:
                    break
            if rendered:
                if len(figures) >= 8:
                    break
                continue
            try:
                base = doc.extract_image(xref)
                fig_idx += 1
                raw_path = output_dir / f"figure_p{page_index + 1}_{fig_idx}_raw.{base.get('ext', 'png')}"
                out_path = output_dir / f"figure_p{page_index + 1}_{fig_idx}.png"
                raw_path.write_bytes(base["image"])
                image_path = _normalize_image_file_to_white_png(raw_path, out_path) or str(raw_path)
                if not _is_image_file_usable(image_path):
                    fig_idx -= 1
                    continue
                figures.append(
                    ParsedFigure(
                        page_index=page_index,
                        figure_id=f"figure-{fig_idx}",
                        caption=caption,
                        image_path=image_path,
                    )
                )
            except Exception:
                continue
            if len(figures) >= 8:
                break
        if len(figures) >= 8:
            break
    doc.close()
    return figures


def ocr_pdf_pages(pdf_path: str) -> Tuple[str, bool]:
    tesseract_cmd = _tesseract_cmd()
    if not tesseract_cmd:
        return "", False
    try:
        import fitz  # type: ignore
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        return "", False

    bundled_tessdata = Path(__file__).resolve().parent / "runtime" / "tesseract" / "usr" / "share" / "tesseract-ocr" / "4.00" / "tessdata"
    if bundled_tessdata.exists() and not os.getenv("TESSDATA_PREFIX"):
        os.environ["TESSDATA_PREFIX"] = str(bundled_tessdata.parent.parent.parent.parent)

    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    doc = fitz.open(pdf_path)
    chunks: List[str] = []
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        try:
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
        except Exception:
            text = pytesseract.image_to_string(img, lang="eng")
        if text.strip():
            chunks.append(text.strip())
    doc.close()
    if not chunks:
        return "", False
    return "\n\n".join(chunks), True


def _render_table_image(
    pdf_path: str,
    page_index: int,
    bbox: tuple[float, float, float, float] | None,
    output_path: Path,
) -> str:
    return _render_pdf_clip_image(pdf_path, page_index, bbox, output_path, zoom=2.0)


def extract_table_screenshots_from_pdf(pdf_path: str, output_dir: Path, max_tables: int = 8) -> List[ParsedTable]:
    tables: List[ParsedTable] = []
    try:
        import fitz  # type: ignore
    except ImportError:
        return tables

    output_dir.mkdir(parents=True, exist_ok=True)
    table_pattern = re.compile(r"\bTable\s*\d+|表\s*\d+", re.IGNORECASE)
    try:
        doc = fitz.open(pdf_path)
        for page_index, page in enumerate(doc):
            page_text = page.get_text("text") or ""
            matches = list(table_pattern.finditer(page_text))
            if not matches:
                continue
            for match_idx, match in enumerate(matches[:2]):
                table_no = len(tables) + 1
                out_path = output_dir / f"table_page_p{page_index + 1}_{match_idx + 1}.png"
                image_path = _render_table_image(pdf_path, page_index, None, out_path)
                caption = re.sub(r"\s+", " ", page_text[match.start() : match.start() + 180]).strip()
                tables.append(
                    ParsedTable(
                        page_index=page_index,
                        table_id=f"table-p{page_index + 1}-{match_idx + 1}",
                        markdown=caption or f"第 {page_index + 1} 页表格截图",
                        row_count=0,
                        col_count=0,
                        image_path=image_path,
                    )
                )
                if len(tables) >= max_tables:
                    doc.close()
                    return tables
        doc.close()
    except Exception:
        return tables
    return tables


def extract_tables_with_pdfplumber(pdf_path: str, output_dir: Path | None = None) -> List[ParsedTable]:
    tables: List[ParsedTable] = []
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        return tables

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            found_tables = page.find_tables() or []
            extracted_tables = page.extract_tables() or []
            max_count = max(len(found_tables), len(extracted_tables))
            for t_idx in range(max_count):
                table = extracted_tables[t_idx] if t_idx < len(extracted_tables) else []
                if not table:
                    continue
                rows = [" | ".join(cell or "" for cell in row) for row in table[:15]]
                image_path = ""
                if output_dir:
                    bbox = found_tables[t_idx].bbox if t_idx < len(found_tables) else None
                    image_path = _render_table_image(
                        pdf_path,
                        page_index,
                        bbox,
                        output_dir / f"table_p{page_index + 1}_{t_idx + 1}.png",
                    )
                tables.append(
                    ParsedTable(
                        page_index=page_index,
                        table_id=f"table-p{page_index + 1}-{t_idx + 1}",
                        markdown="\n".join(rows),
                        row_count=len(table),
                        col_count=max(len(row) for row in table),
                        image_path=image_path,
                    )
                )
                if len(tables) >= 8:
                    return tables
    return tables
