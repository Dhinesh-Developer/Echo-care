import io
import pandas as pd
import plotly.express as px
import streamlit as st

import auth, db, styles, ui, doctors_data as dd

user = ui.page_setup("Admin", "🔐")
styles.hero("Admin Dashboard", "Usage statistics, feedback, and the doctor directory. Health content is never shown here.", eyebrow="Admin")

if not auth.is_admin():
    st.error("This page is for administrators only.")
    st.caption("Set `ADMIN_EMAILS = \"you@example.com\"` in Streamlit secrets. If unset, the first registered account is the admin.")
    st.stop()

tab_over, tab_fb, tab_dir, tab_acc = st.tabs(["📈 Overview", "⭐ Feedback", "🏥 Doctor directory", "👥 Accounts"])

with tab_over:
    s = db.get_admin_stats()
    keys = ["Accounts", "Family profiles", "Story entries", "Tracker check-ins", "Vitals readings", "Reports", "Insights",
            "Chat messages", "Medicines", "Appointments"]
    for row in (keys[:5], keys[5:]):
        for col, k in zip(st.columns(5), row):
            styles.stat_card(col, s[k], k)
        st.write("")
    left, right = st.columns(2)
    with left:
        st.markdown("##### Activity by module")
        fig = px.bar(x=keys[2:], y=[s[k] for k in keys[2:]], labels={"x": "", "y": "records"}, color_discrete_sequence=["#2563EB"])
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.markdown("##### New accounts per day")
        if s["signups_by_day"]:
            fig = px.line(pd.DataFrame(s["signups_by_day"]), x="d", y="c", markers=True, labels={"d": "", "c": "signups"}, color_discrete_sequence=["#2563EB"])
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No signups yet.")

with tab_fb:
    fb = db.list_feedback()
    s = db.get_admin_stats()
    st.metric("Average rating", f"{s['avg_rating']:.2f} / 5" if s["avg_rating"] else "n/a")
    if fb:
        st.dataframe([{"When": f["created_at"][:16].replace("T", " "), "Who": f["user_name"], "About": f["context"], "Rating": f["rating"], "Comment": f["outcome"]} for f in fb],
                     use_container_width=True, hide_index=True)
    else:
        st.caption("No feedback yet.")

with tab_dir:
    directory = dd.get_directory()
    src = dd.directory_source(directory)
    st.markdown(f"Current directory: **{'demo (generated)' if src == 'demo' else 'imported real data'}**, {len(directory)} doctors.")
    st.download_button("⬇️ Download CSV template", dd.template_csv(), "doctor_directory_template.csv", "text/csv")
    st.caption("Required columns: name, specialty, district, hospital. Optional: lat, lon, rating, years_experience, consultation_fee_inr, phone. "
               "Missing coordinates are placed near the district centre when the district is a known one.")
    up = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if up:
        try:
            df = pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up)
            rows, errors, warns = dd.parse_directory_upload(df)
            st.write(f"**{len(rows)}** valid row(s), **{len(errors)}** skipped, **{len(warns)}** warning(s).")
            for msg in errors[:8]: st.error(msg)
            for msg in warns[:5]: st.warning(msg)
            if rows:
                st.dataframe(rows[:10], use_container_width=True, hide_index=True)
                if st.button("Import and replace the current directory", type="primary"):
                    db.replace_imported_doctors(rows)
                    st.success(f"Imported {len(rows)} doctors. Find Doctors now uses this directory.")
                    st.rerun()
        except Exception as e:
            st.error(f"Couldn't read that file: {e}")
    if src == "imported" and st.button("Reset to the demo directory"):
        db.clear_imported_doctors()
        st.rerun()

with tab_acc:
    st.caption("Names and sign-up dates only. No health data is shown.")
    st.dataframe([{"ID": a["id"], "Name": a["name"], "Email": a["email"], "Joined": a["created_at"][:10]} for a in db.list_accounts()],
                 use_container_width=True, hide_index=True)
