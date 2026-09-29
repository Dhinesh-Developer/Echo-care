import io
import streamlit as st

import db, styles, ui

user = ui.page_setup("Emergency Card", "🚑")
styles.hero("Emergency Medical Card", "Blood group, allergies, medicines and contacts, viewable by anyone you share the link "
            "with, even without logging in.", eyebrow="Safety")

card = db.get_emergency_card(user["id"])
data = (card or {}).get("data", {})
BLOOD = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "Unknown"]

with st.form("card_form"):
    c1, c2 = st.columns(2)
    bg = c1.selectbox("Blood group", BLOOD, index=BLOOD.index(data.get("blood_group", "")) if data.get("blood_group", "") in BLOOD else 0)
    donor = c2.selectbox("Organ donor", ["", "Yes", "No"], index=["", "Yes", "No"].index(data.get("organ_donor", "")) if data.get("organ_donor", "") in ["", "Yes", "No"] else 0)
    allergies = st.text_input("Allergies", value=data.get("allergies", ""), placeholder="Penicillin, peanuts")
    conditions = st.text_input("Chronic conditions", value=data.get("conditions", ""), placeholder="Type 2 diabetes, hypertension")
    default_meds = ", ".join(f"{m['name']} {m['dose']}".strip() for m in db.get_medicines(user["id"]))
    meds = st.text_input("Current medicines", value=data.get("medications") or default_meds, help="Pre-filled from your Medicine Tracker")
    c1, c2 = st.columns(2)
    doc_name, doc_phone = c1.text_input("Regular doctor", value=data.get("doctor_name", "")), c2.text_input("Doctor phone", value=data.get("doctor_phone", ""))
    st.markdown("**Emergency contacts**")
    old = data.get("contacts", []) + [{}, {}]
    contacts = []
    for i in range(2):
        a, b, c = st.columns(3)
        n = a.text_input(f"Contact {i + 1} name", value=old[i].get("name", ""), key=f"cn{i}")
        r = b.text_input("Relation", value=old[i].get("relation", ""), key=f"cr{i}")
        p = c.text_input("Phone", value=old[i].get("phone", ""), key=f"cp{i}")
        contacts.append({"name": n, "relation": r, "phone": p})
    notes = st.text_area("Other notes for responders", value=data.get("notes", ""), height=70)
    public = st.toggle("Enable public link (anyone with the link can view this card)", value=bool((card or {}).get("public_enabled")))
    regen = st.checkbox("Generate a new link (old link stops working)") if card else False
    if st.form_submit_button("Save card", type="primary"):
        db.upsert_emergency_card(user["id"], {"blood_group": bg, "organ_donor": donor, "allergies": allergies, "conditions": conditions,
                                              "medications": meds, "doctor_name": doc_name, "doctor_phone": doc_phone,
                                              "contacts": contacts, "notes": notes}, public, regenerate_token=regen)
        st.success("Saved.")
        st.rerun()

card = db.get_emergency_card(user["id"])
if card:
    st.markdown("#### Preview")
    ui.render_emergency_card(card["data"], user["name"], public=card["public_enabled"])
    if card["public_enabled"]:
        base = st.text_input("Your app's public address", value=st.session_state.get("app_url", "http://localhost:8501"))
        st.session_state["app_url"] = base
        link = f"{base.rstrip('/')}/?card={card['token']}"
        st.code(link)
        try:
            import qrcode
            buf = io.BytesIO()
            qrcode.make(link).save(buf, format="PNG")
            st.image(buf.getvalue(), width=180, caption="Scan to open the card. Print it or set it as a phone lock-screen image.")
        except ImportError:
            st.caption("Install `qrcode[pil]` to show a QR code here.")
        st.warning("Anyone with this link can see the information above. Turn the toggle off to disable it at any time.")
    else:
        st.info("The public link is off. Turn it on above to share this card with responders or family.")
