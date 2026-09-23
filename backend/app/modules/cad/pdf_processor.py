from app.modules.takeoff.schemas import CanonicalQuantity
"""
PDF Processing Pipeline for construction drawings.

Default (always available):
  - pdfplumber: text, lines, tables, rects from vector PDFs

Optional (install separately for scanned PDFs):
  pip install paddleocr paddlepaddle-tiny
  - PaddleOCR: OCR for scanned drawings, scale detection, dimension extraction
"""
import re
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Optional heavy dependencies ───────────────────────────────────────────────
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import numpy as np
    import cv2
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False


@dataclass
class PDFDimension:
    text: str
    value: Optional[float]
    unit: Optional[str]
    bbox: Tuple[float, float, float, float]  # (x0, top, x1, bottom)
    page_number: int
    confidence: float = 1.0


@dataclass
class PDFScaleInfo:
    scale_ratio: Optional[float]   # e.g. 0.01 for 1:100
    scale_text: Optional[str]      # e.g. "1:100"
    confidence: float
    method: str                    # "text_extraction" | "ocr" | "not_found"


class PDFProcessor:
    """
    Two-tier PDF processing:
    Tier 1 (always): pdfplumber — fast, works on vector PDFs
    Tier 2 (optional): PaddleOCR — for scanned/raster PDFs
    """

    def __init__(self):
        self._ocr = None  # Lazy-init PaddleOCR

    def _get_ocr(self):
        if self._ocr is None:
            if not PADDLEOCR_AVAILABLE:
                raise RuntimeError(
                    "PaddleOCR is not installed. "
                    "Run: pip install paddleocr paddlepaddle-tiny\n"
                    "This is optional — only needed for scanned PDFs."
                )
            self._ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        return self._ocr

    # ── 1. Text + layout extraction (pdfplumber) ──────────────────────────────

    def extract_text_and_layout(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract text, lines, rects, and tables from a PDF.
        Works on vector PDFs without OCR.
        """
        if not PDFPLUMBER_AVAILABLE:
            raise RuntimeError("pdfplumber is not installed. Run: pip install pdfplumber")

        result: Dict[str, Any] = {"pages": [], "total_pages": 0}

        with pdfplumber.open(pdf_path) as pdf:
            result["total_pages"] = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages):
                page_data: Dict[str, Any] = {
                    "page_number": page_num + 1,
                    "width": page.width,
                    "height": page.height,
                    "words": [],
                    "lines": [],
                    "rects": [],
                    "tables": [],
                }

                for word in (page.extract_words() or []):
                    page_data["words"].append({
                        "text": word["text"],
                        "x0": word["x0"], "top": word["top"],
                        "x1": word["x1"], "bottom": word["bottom"],
                    })

                for line in (page.lines or []):
                    page_data["lines"].append({
                        "x0": line["x0"], "top": line["top"],
                        "x1": line["x1"], "bottom": line["bottom"],
                    })

                for rect in (page.rects or []):
                    page_data["rects"].append({
                        "x0": rect["x0"], "top": rect["top"],
                        "x1": rect["x1"], "bottom": rect["bottom"],
                    })

                for table in (page.extract_tables() or []):
                    page_data["tables"].append(table)

                result["pages"].append(page_data)

        return result

    # ── 2. Scale detection ────────────────────────────────────────────────────

    def detect_scale(self, pdf_path: str) -> PDFScaleInfo:
        """
        Detect drawing scale (e.g. 1:100) from the PDF.
        Tries pdfplumber text first; falls back to OCR if available.
        """
        # --- Tier 1: pdfplumber text ---
        if PDFPLUMBER_AVAILABLE:
            result = self._detect_scale_from_text(pdf_path)
            if result.scale_ratio is not None:
                return result

        # --- Tier 2: PaddleOCR (optional) ---
        if PADDLEOCR_AVAILABLE and PYMUPDF_AVAILABLE:
            try:
                return self._detect_scale_ocr(pdf_path)
            except Exception as exc:
                logger.warning(f"OCR scale detection failed: {exc}")

        return PDFScaleInfo(scale_ratio=None, scale_text=None, confidence=0.0, method="not_found")

    def _detect_scale_from_text(self, pdf_path: str) -> PDFScaleInfo:
        patterns = [
            r"SCALE\s*[:\-]?\s*(\d+)\s*[:/]\s*(\d+)",
            r"(\d+)\s*[:/]\s*(\d+)",
            r"1\s*[:/]\s*(\d+)",
        ]
        with pdfplumber.open(pdf_path) as pdf:
            # Check first page (title block usually there)
            page = pdf.pages[0]
            text = page.extract_text() or ""
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) == 2:
                        num, den = int(groups[0]), int(groups[1])
                    else:
                        num, den = 1, int(groups[0])
                    if den > 0:
                        return PDFScaleInfo(
                            scale_ratio=num / den,
                            scale_text=f"{num}:{den}",
                            confidence=0.85,
                            method="text_extraction",
                        )
        return PDFScaleInfo(scale_ratio=None, scale_text=None, confidence=0.0, method="not_found")

    def _detect_scale_ocr(self, pdf_path: str) -> PDFScaleInfo:
        """OCR-based scale detection for scanned PDFs."""
        import fitz
        import numpy as np
        import cv2

        ocr = self._get_ocr()
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        ocr_result = ocr.ocr(img_rgb, cls=True)
        texts = []
        for line in (ocr_result or []):
            if line:
                for word_info in line:
                    if word_info[1][1] > 0.5:
                        texts.append(word_info[1][0])

        patterns = [
            r"SCALE\s*[:\-]?\s*(\d+)\s*[:/]\s*(\d+)",
            r"(\d+)\s*[:/]\s*(\d+)",
            r"1\s*[:/]\s*(\d+)",
        ]
        for text in texts:
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) == 2:
                        num, den = int(groups[0]), int(groups[1])
                    else:
                        num, den = 1, int(groups[0])
                    if den > 0:
                        return PDFScaleInfo(
                            scale_ratio=num / den,
                            scale_text=f"{num}:{den}",
                            confidence=0.75,
                            method="ocr",
                        )
        return PDFScaleInfo(scale_ratio=None, scale_text=None, confidence=0.0, method="not_found")

    # ── 3. Dimension extraction ───────────────────────────────────────────────

    def detect_dimensions(self, pdf_path: str) -> List[PDFDimension]:
        """
        Extract dimension text from PDF.
        Tier 1: pdfplumber word extraction + regex
        Tier 2: PaddleOCR (if available)
        """
        dims: List[PDFDimension] = []

        if PDFPLUMBER_AVAILABLE:
            dims.extend(self._dims_from_text(pdf_path))

        if not dims and PADDLEOCR_AVAILABLE and PYMUPDF_AVAILABLE:
            try:
                dims.extend(self._dims_from_ocr(pdf_path))
            except Exception as exc:
                logger.warning(f"OCR dimension extraction failed: {exc}")

        return dims

    def _dims_from_text(self, pdf_path: str) -> List[PDFDimension]:
        dims: List[PDFDimension] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                for word in (page.extract_words() or []):
                    value, unit = self._parse_dim_text(word["text"])
                    if value is not None:
                        dims.append(PDFDimension(
                            text=word["text"],
                            value=value,
                            unit=unit,
                            bbox=(word["x0"], word["top"], word["x1"], word["bottom"]),
                            page_number=page_num + 1,
                            confidence=0.9,
                        ))
        return dims

    def _dims_from_ocr(self, pdf_path: str) -> List[PDFDimension]:
        import fitz
        import numpy as np
        import cv2

        dims: List[PDFDimension] = []
        ocr = self._get_ocr()
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            ocr_result = ocr.ocr(img_rgb, cls=True)
            for line in (ocr_result or []):
                if not line:
                    continue
                for word_info in line:
                    text = word_info[1][0].strip()
                    confidence = word_info[1][1]
                    if confidence < 0.6:
                        continue
                    value, unit = self._parse_dim_text(text)
                    if value is not None:
                        bbox_pts = word_info[0]
                        dims.append(PDFDimension(
                            text=text,
                            value=value,
                            unit=unit,
                            bbox=(
                                bbox_pts[0][0] / 2.0, bbox_pts[0][1] / 2.0,
                                bbox_pts[2][0] / 2.0, bbox_pts[2][1] / 2.0,
                            ),
                            page_number=page_num + 1,
                            confidence=confidence,
                        ))
        return dims

    @staticmethod
    def _parse_dim_text(text: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Parse a text string to extract a numeric dimension value and unit.
        Examples: "5000" → (5000, None), "5.0m" → (5.0, "m"), "10mm" → (10, "mm")
        """
        match = re.search(r"([+-]?[\d,]+\.?\d*)\s*([a-zA-Z]*)", text.replace(",", ""))
        if match:
            try:
                value = float(match.group(1))
                unit = match.group(2).strip() or None
                # Filter out non-dimension numbers (e.g. page numbers, dates)
                if value <= 0 or value > 1_000_000:
                    return None, None
                return value, unit
            except ValueError:
                pass
        return None, None

    # ── 4. Canvas JSON for browser rendering ─────────────────────────────────

    def pdf_to_canvas_json(self, pdf_path: str, page_number: int = 1) -> Dict[str, Any]:
        """
        Convert a PDF page to JSON for Fabric.js / Canvas2D rendering.
        Returns paths (lines), rects, and text objects.
        """
        if not PDFPLUMBER_AVAILABLE:
            return {"error": "pdfplumber not installed"}

        with pdfplumber.open(pdf_path) as pdf:
            if page_number > len(pdf.pages):
                return {"error": f"Page {page_number} does not exist"}
            page = pdf.pages[page_number - 1]

            data: Dict[str, Any] = {
                "page_number": page_number,
                "width": page.width,
                "height": page.height,
                "paths": [],
                "rects": [],
                "texts": [],
            }

            for line in (page.lines or []):
                data["paths"].append({
                    "type": "line",
                    "x1": line["x0"], "y1": line["top"],
                    "x2": line["x1"], "y2": line["bottom"],
                    "stroke": "#000000", "strokeWidth": 1,
                })

            for rect in (page.rects or []):
                data["rects"].append({
                    "x": rect["x0"], "y": rect["top"],
                    "width": rect["x1"] - rect["x0"],
                    "height": rect["bottom"] - rect["top"],
                    "stroke": "#000000", "fill": None,
                })

            for word in (page.extract_words() or []):
                data["texts"].append({
                    "text": word["text"],
                    "x": word["x0"], "y": word["top"],
                    "fontSize": 10, "fill": "#000000",
                })

            return data

    # ── 5. Enriched dimensions (with nearby context) ──────────────────────────

    def extract_dimensions_with_context(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extract dimensions and annotate each with nearby words (for UI tooltips).
        """
        dims = self.detect_dimensions(pdf_path)
        layout = self.extract_text_and_layout(pdf_path)
        enriched = []

        for dim in dims:
            page_idx = dim.page_number - 1
            page_words = layout["pages"][page_idx]["words"] if page_idx < len(layout["pages"]) else []

            nearby = []
            for word in page_words:
                dist = self._bbox_distance(
                    (word["x0"], word["top"], word["x1"], word["bottom"]),
                    dim.bbox,
                )
                if dist < 50:
                    nearby.append({"text": word["text"], "distance": round(dist, 1)})

            enriched.append({**asdict(dim), "nearby_objects": nearby})

        return enriched

    @staticmethod
    def _bbox_distance(
        a: Tuple[float, float, float, float],
        b: Tuple[float, float, float, float],
    ) -> float:
        ax = (a[0] + a[2]) / 2
        ay = (a[1] + a[3]) / 2
        bx = (b[0] + b[2]) / 2
        by = (b[1] + b[3]) / 2
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    def extract_canonical(self, file_path: str, project_id: str, drawing_id: str) -> List[CanonicalQuantity]:
        """
        Extracts measurements and annotations from a PDF and converts to CanonicalQuantity.
        Currently handles manual measurements stored in the PDF (if any) or text-based dimensions.
        """
        # This will be expanded as we implement the actual PDF parsing logic
        return []
