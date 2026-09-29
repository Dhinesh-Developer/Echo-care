import streamlit as st
from datetime import date, datetime

import db, styles, ui, llm, rag, labs, docreader

user = ui.page_setup("Medical Reports", "📄")
styles.hero("Medical Reports & Photos",
            "Gemini Vision reads lab reports and prescriptions straight from a photo or PDF. "
            "Text/OCR parsing is the fallback.", eyebrow="Reports")

LAB_PROMPT = ("Extract every lab test from this report. Return ONLY JSON: "
              '{"report_date": "YYYY-MM-DD or null", "fields": [{"test": "name", "value": "number only", '
              '"unit": "unit or null", "reference_range": "e.g. 12.0-15.5 or <200, or null"}], '
              '"summary": "one neutral sentence describing the report"}. Do not interpret or diagnose.')
RX_PROMPT = ("Read this prescription. Return ONLY JSON: "
             '{"date": "YYYY-MM-DD or null", "doctor": "name or null", "medicines": [{"name": "", "dose": "", '
             '"frequency": "e.g. twice daily", "duration": "e.g. 5 days or null"}], "notes": "instructions or null"}. '
             "If handwriting is unclear, give your best reading and never invent a medicine.")
PHOTO_PROMPT = ("You are looking at a photo a patient uploaded of a visible skin/wound/body concern. "
                "1) Describe only what is visibly present (colour, size relative to surroundings, texture, borders, location) in neutral terms. "
                "2) Do NOT name or suggest any disease or diagnosis. "
                "3) Say which type of specialist usually assesses findings like this (choose from: General Medicine, Dermatology, Orthopedics, ENT, Gynecology). "
                "4) List any warning signs that would justify prompt in-person evaluation (e.g. rapid growth, bleeding, spreading redness, pus, severe swelling, fever). "
                "5) Note that photo quality limits what can be described. Keep it under 150 words.")

tab_doc, tab_photo, tab_manual = st.tabs(["📄 Lab report / prescription", "📷 Photo analysis", "✍️ Add values manually"])

with tab_doc:
    c1, c2 = st.columns(2)
    doc_type = c1.radio("Document type", ["Lab report", "Prescription"], horizontal=True)
    method = c2.radio("Reading method", ["Gemini Vision (recommended)", "Text / OCR parsing"], horizontal=True)
    uploaded = st.file_uploader("Upload PDF or image", type=["pdf", "png", "jpg", "jpeg", "webp"], key="doc_upload")
    rdate = st.date_input("Report date", value=date.today(), max_value=date.today())

    if uploaded and st.button("Analyze document", type="primary"):
        data = uploaded.read()
        fields, summary, used = [], "", None
        if method.startswith("Gemini"):
            with st.spinner("Gemini is reading your document..."):
                res = llm.gemini_generate_json(LAB_PROMPT if doc_type == "Lab report" else RX_PROMPT,
                                               parts=docreader.to_vision_parts(data, uploaded.name)) if llm.gemini_configured() else {"ok": False, "reason": "GOOGLE_API_KEY is not configured."}
            parsed = labs.parse_json_loose(res.get("text")) if res.get("ok") else None
            if parsed:
                used = "gemini-vision"
                if doc_type == "Lab report":
                    fields = labs.normalize_vision_fields(parsed.get("fields"))
                    summary = parsed.get("summary") or ""
                    if parsed.get("report_date"):
                        try:
                            rdate = datetime.strptime(parsed["report_date"], "%Y-%m-%d").date()
                        except ValueError:
                            pass
                else:
                    st.session_state["rx_meds"] = [m for m in parsed.get("medicines", []) if isinstance(m, dict) and m.get("name")]
                    summary = "Prescription: " + "; ".join(f"{m.get('name')} {m.get('dose') or ''} {m.get('frequency') or ''}".strip() for m in st.session_state["rx_meds"])
            else:
                st.warning(f"Gemini Vision unavailable ({res.get('reason') or 'could not parse the response'}). Falling back to text/OCR.")
        if used is None:  # text / OCR path (also the automatic fallback)
            with st.spinner("Extracting text..."):
                text, used = docreader.extract_text(data, uploaded.name)
                fields, summary = labs.extract_fields(text), text[:1500]
            if not text:
                st.error("No text could be read. Install Tesseract for scanned files, or configure Gemini for Vision.")
        if used and (fields or summary):
            db.insert_report(user["id"], uploaded.name, used, summary[:2000], fields, rdate.isoformat())
            fs = "; ".join(f"{f['test']}: {f['value']} {f['unit'] or ''}" + (" (OUT OF RANGE)" if f["out_of_range"] else "") for f in fields)
            rag.chunk_and_store(user["id"], "report", fs or summary, {"filename": uploaded.name})
            st.success(f"Saved via {used}: {len(fields)} lab value(s) found." if doc_type == "Lab report" else "Prescription read and saved.")

    if st.session_state.get("rx_meds"):
        st.markdown("##### Medicines found in the prescription")
        st.dataframe(st.session_state["rx_meds"], use_container_width=True, hide_index=True)
        st.caption("Check these against the original prescription before adding. Handwriting can be misread.")
        if st.button("➕ Add all to my Medicine Tracker", type="primary"):
            for m in st.session_state["rx_meds"]:
                freq = (m.get("frequency") or "").lower()
                slots = ["Morning", "Afternoon", "Night"] if any(w in freq for w in ("thrice", "three", "tds", "3")) else \
                        ["Morning", "Night"] if any(w in freq for w in ("twice", "two", "bd", "bid", "2")) else \
                        ["Night"] if "night" in freq or "bed" in freq else ["Morning"]
                db.add_medicine(user["id"], m["name"], m.get("dose") or "", m.get("frequency") or "Once daily", slots,
                                date.today().isoformat(), None, m.get("duration") or "")
            st.session_state.pop("rx_meds")
            st.success("Added. Review them on the Medicines page.")
            st.rerun()

with tab_photo:
    st.info("Describes what is visible and suggests which specialist to see. It **never** names a condition.")
    img = st.file_uploader("Upload a clear, well-lit photo", type=["png", "jpg", "jpeg", "webp"], key="photo_upload")
    cam = st.camera_input("...or take one now") if st.toggle("Use camera") else None
    src = img or cam
    if src and st.button("Analyze photo", type="primary"):
        ext = (getattr(src, "name", "photo.jpg") or "photo.jpg").lower().rsplit(".", 1)[-1]
        with st.spinner("Gemini Vision is looking at the photo..."):
            res = llm.gemini_vision([(src.getvalue(), docreader.MIME.get(ext, "image/jpeg"))], PHOTO_PROMPT)
        if res["ok"]:
            st.session_state["photo_result"] = res["text"]
        else:
            st.warning(f"Photo analysis unavailable: {res.get('reason')}")
    if st.session_state.get("photo_result"):
        st.markdown(f'<div class="ec-card">{st.session_state["photo_result"]}<div class="ec-disclaimer">Not a diagnosis. '
                    'See a clinician in person for any concern.</div></div>', unsafe_allow_html=True)
        if st.button("Save this description to my evidence"):
            rag.chunk_and_store(user["id"], "photo", st.session_state.pop("photo_result"), {})
            st.success("Saved to your evidence record.")
            st.rerun()

with tab_manual:
    with st.form("manual_lab", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1.4])
        test = c1.text_input("Test name", placeholder="Hemoglobin")
        value = c2.text_input("Value", placeholder="11.2")
        unit = c3.text_input("Unit", placeholder="g/dL")
        ref = c4.text_input("Reference range", placeholder="12.0-15.5")
        mdate = st.date_input("Test date", value=date.today(), max_value=date.today(), key="manual_date")
        if st.form_submit_button("Add value", type="primary"):
            if test.strip() and labs.to_float(value) is not None:
                f = [{"test": test.strip(), "value": value.strip(), "unit": unit.strip() or None,
                      "reference_range": ref.strip() or None, "out_of_range": labs.is_out_of_range(value, ref)}]
                db.insert_report(user["id"], "Manual entry", "manual", f"{test} {value} {unit}", f, mdate.isoformat())
                rag.chunk_and_store(user["id"], "report", f"{test}: {value} {unit}" + (" (OUT OF RANGE)" if f[0]["out_of_range"] else ""), {})
                st.success("Added.")
            else:
                st.error("Enter a test name and a numeric value.")

st.divider()
st.markdown("#### Past reports")
reports = db.get_reports(user["id"])
if not reports:
    st.caption("Nothing uploaded yet.")
for r in reports:
    with st.expander(f"📄 {r['filename']} · {r['report_date']} · via {r['extraction_method']}"):
        if r["fields"]:
            for f in r["fields"]:
                flag = " ⚠️ out of range" if f["out_of_range"] else ""
                st.write(f"**{f['test']}**: {f['value']} {f['unit'] or ''} (ref: {f['reference_range'] or 'n/a'}){flag}")
        else:
            st.text((r["raw_text_excerpt"] or "")[:600])
