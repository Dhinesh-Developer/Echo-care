import streamlit as st
import io
import re
import fitz  # PyMuPDF
from PIL import Image

import db, auth, styles, rag

st.set_page_config(page_title="Medical Reports — EchoCare", page_icon="📄", layout="wide")
auth.require_login()
styles.inject()
user = auth.current_user()

styles.hero("Medical Report Analysis", "Upload a lab report (PDF or photo). "
                                       "Digital PDFs parse directly; scans fall back to OCR.")

FIELD_PATTERN = re.compile(
    r"([A-Za-z][A-Za-z0-9 /()%-]{2,40}?)\s+([\d.]+)\s*([a-zA-Z/%µ]{0,10})\s*"
    r"\(?\s*([\d.]+\s*-\s*[\d.]+)?\s*\)?"
)


def extract_text_pymupdf(file_bytes: bytes) -> str:
    # PyMuPDF raises FzErrorFormat when a text file or damaged upload has
    # merely been given a .pdf extension.
    if not file_bytes.startswith(b"%PDF-"):
        raise ValueError("This file does not contain a valid PDF document.")
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc).strip()
    except Exception as exc:
        raise ValueError("This PDF could not be opened. It may be damaged or incomplete.") from exc


def extract_text_ocr(file_bytes: bytes, is_pdf: bool) -> str:
    try:
        import pytesseract
    except ImportError:
        return ""
    text = ""
    if is_pdf:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=250)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text += pytesseract.image_to_string(img) + "\n"
    else:
        img = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(img)
    return text.strip()


def extract_fields(text: str) -> list[dict]:
    fields = []
    for match in FIELD_PATTERN.finditer(text):
        name, value, unit, ref_range = match.groups()
        out_of_range = False
        if ref_range:
            try:
                low, high = [float(x.strip()) for x in ref_range.split("-")]
                out_of_range = not (low <= float(value) <= high)
            except ValueError:
                pass
        fields.append({"test": name.strip(), "value": value.strip(), "unit": (unit or "").strip() or None,
                        "reference_range": ref_range.strip() if ref_range else None, "out_of_range": out_of_range})
    return fields


uploaded = st.file_uploader("Upload report", type=["pdf", "png", "jpg", "jpeg"])
if uploaded and st.button("Analyze report", type="primary"):
    with st.spinner("Extracting text..."):
        file_bytes = uploaded.read()
        is_pdf = uploaded.name.lower().endswith(".pdf")
        if is_pdf:
            try:
                text = extract_text_pymupdf(file_bytes)
            except ValueError as exc:
                st.error(str(exc))
                st.info("Export or print the document as a real PDF, then upload it again.")
                text = None
            method = "pymupdf"
            if text is not None and len(text) < 40:
                try:
                    text = extract_text_ocr(file_bytes, True)
                    method = "ocr"
                except Exception:
                    st.error("This PDF could not be read for OCR. Try exporting it as a new PDF.")
                    text = None
        else:
            try:
                text = extract_text_ocr(file_bytes, False)
                method = "ocr"
            except Exception:
                st.error("This image could not be read. Try uploading a clear PNG or JPG image.")
                text = None

        if text is not None:
            if not text.strip():
                st.warning("No readable text was found in this report. Try a clearer scan or a digital PDF.")
            else:
                fields = extract_fields(text)
                db.insert_report(user["id"], uploaded.name, method, text[:2000], fields)

                field_summary = "; ".join(
                    f"{f['test']}: {f['value']} {f['unit'] or ''}" + (" (OUT OF RANGE)" if f["out_of_range"] else "")
                    for f in fields
                )
                if field_summary:
                    rag.chunk_and_store(user["id"], "report", field_summary, {"filename": uploaded.name})
                st.success(f"Analyzed via {method}. Found {len(fields)} structured field(s).")
                st.rerun()

st.divider()
st.markdown("### Past reports")
reports = db.get_reports(user["id"])
if not reports:
    st.caption("No reports uploaded yet.")
for r in reports:
    with st.expander(f"📄 {r['filename']} — via {r['extraction_method']} ({r['created_at'][:10]})"):
        if r["fields"]:
            for f in r["fields"]:
                flag = " ⚠️ out of range" if f["out_of_range"] else ""
                st.write(f"**{f['test']}**: {f['value']} {f['unit'] or ''} "
                         f"(ref: {f['reference_range'] or '—'}){flag}")
        else:
            st.caption("No structured fields detected. Raw text excerpt:")
            st.text(r["raw_text_excerpt"][:500])
