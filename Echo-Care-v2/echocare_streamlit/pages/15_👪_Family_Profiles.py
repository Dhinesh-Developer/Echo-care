import streamlit as st
from datetime import date

import auth, db, styles, ui

user = ui.page_setup("Family Profiles", "👪")
account = auth.account_user()
styles.hero("Family Profiles", "Track a parent, partner or child under your login. Each profile has its own story, tracker, "
            "vitals, reports, medicines and appointments.", eyebrow="Family")

members = db.get_members(account["id"])
active = auth.current_user()
st.markdown(f"Currently viewing: **{active['name']}**" + (f" ({active.get('relation')})" if active.get("is_member") else " (you)"))

cols = st.columns(3)
with cols[0]:
    st.markdown(f'<div class="ec-card"><b>{account["name"]}</b><br><span style="color:var(--muted);">You</span></div>', unsafe_allow_html=True)
    if st.button("View my profile", key="sw_me", disabled=not active.get("is_member"), use_container_width=True):
        auth.set_active_profile(None); st.rerun()
for i, m in enumerate(members, 1):
    with cols[i % 3]:
        age = f" · {date.today().year - int(m['dob'][:4])} yrs" if m.get("dob") else ""
        st.markdown(f'<div class="ec-card"><b>{m["name"]}</b><br><span style="color:var(--muted);">{m["relation"]}{age}</span></div>', unsafe_allow_html=True)
        if st.button("View profile", key=f"sw_{m['id']}", disabled=(active["id"] == m["id"]), use_container_width=True):
            auth.set_active_profile(m["id"]); st.rerun()

st.divider()
st.markdown("#### Add a family member")
if len(members) >= 10:
    st.info("Profile limit reached (10).")
else:
    with st.form("member_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Name")
        relation = c2.selectbox("Relation", ["Mother", "Father", "Spouse", "Son", "Daughter", "Sibling", "Grandparent", "Other"])
        dob = c3.date_input("Date of birth", value=None, min_value=date(1920, 1, 1), max_value=date.today())
        if st.form_submit_button("Add member", type="primary"):
            if name.strip():
                new_id = db.create_member(account["id"], name.strip(), relation, dob.isoformat() if dob else None)
                auth.set_active_profile(new_id)
                st.success(f"Added {name}. Now viewing their profile.")
                st.rerun()
            else:
                st.error("Enter a name.")

if members:
    st.divider()
    with st.expander("Remove a family member"):
        target = st.selectbox("Member", [m["id"] for m in members], format_func=lambda i: next(m["name"] for m in members if m["id"] == i))
        ok = st.checkbox("I understand this permanently deletes all of their data")
        if st.button("Delete profile", disabled=not ok):
            db.delete_member(account["id"], target)
            if active["id"] == target:
                auth.set_active_profile(None)
            st.rerun()
