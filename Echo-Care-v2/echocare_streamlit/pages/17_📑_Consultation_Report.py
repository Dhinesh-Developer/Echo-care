import streamlit as st
import styles, ui, report_pdf
from datetime import date

user = ui.page_setup("Consultation Report", "📑")
styles.hero("One-click PDF for Your Doctor", "Everything you've recorded, organised for a consultation. Choose what to include.", eyebrow="Report")

st.markdown("#### Include")
cols = st.columns(2)
include = {}
for i, (key, label) in enumerate(report_pdf.SECTIONS.items()):
    include[key] = cols[i % 2].checkbox(label, value=True, key=f"inc_{key}")

if st.button("📑 Generate PDF", type="primary"):
    with st.spinner("Building your report..."):
        st.session_state["pdf_bytes"] = report_pdf.build_pdf(user["id"], user["name"], include)
        st.session_state["pdf_for"] = user["id"]

if st.session_state.get("pdf_bytes") and st.session_state.get("pdf_for") == user["id"]:
    st.success("Your report is ready.")
    st.download_button("⬇️ Download PDF", st.session_state["pdf_bytes"],
                       f"EchoCare_{user['name'].replace(' ', '_')}_{date.today().isoformat()}.pdf", "application/pdf", type="primary")
st.caption("The PDF contains only what you recorded, with confidence labels on AI insights. It is not a diagnosis. "
           "Tamil/Hindi text you typed may not render in the PDF (English is fully supported).")
