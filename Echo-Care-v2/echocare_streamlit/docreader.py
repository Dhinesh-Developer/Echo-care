"""Turns uploaded documents into inputs for Gemini Vision (page images) or the text/OCR fallback."""
import io

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24.3
except ImportError:  # older installs
    import fitz
from PIL import Image

MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}


def pdf_to_png_pages(file_bytes: bytes, max_pages: int = 4, dpi: int = 130) -> list[tuple[bytes, str]]:
    parts = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            parts.append((page.get_pixmap(dpi=dpi).tobytes("png"), "image/png"))
    return parts


def to_vision_parts(file_bytes: bytes, filename: str) -> list[tuple[bytes, str]]:
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        return pdf_to_png_pages(file_bytes)
    return [(file_bytes, MIME.get(ext, "image/jpeg"))]


def extract_text_pymupdf(file_bytes: bytes) -> str:
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        return "".join(page.get_text() for page in doc).strip()


def extract_text_ocr(file_bytes: bytes, is_pdf: bool) -> str:
    try:
        import pytesseract
    except ImportError:
        return ""
    try:
        if is_pdf:
            text = ""
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    text += pytesseract.image_to_string(Image.open(io.BytesIO(page.get_pixmap(dpi=250).tobytes("png")))) + "\n"
            return text.strip()
        return pytesseract.image_to_string(Image.open(io.BytesIO(file_bytes))).strip()
    except Exception:  # tesseract binary not installed
        return ""


def extract_text(file_bytes: bytes, filename: str) -> tuple[str, str]:
    """Returns (text, method): PyMuPDF for digital PDFs, OCR for scans and photos."""
    is_pdf = filename.lower().endswith(".pdf")
    if is_pdf:
        text = extract_text_pymupdf(file_bytes)
        if len(text) >= 40:
            return text, "pymupdf"
        return extract_text_ocr(file_bytes, True), "ocr"
    return extract_text_ocr(file_bytes, False), "ocr"
