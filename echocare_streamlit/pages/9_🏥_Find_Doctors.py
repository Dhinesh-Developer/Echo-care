import streamlit as st
import folium
from streamlit_folium import st_folium

import db, auth, styles, doctors_data as dd, llm
from department_classifier import predict_department
from specialties import ALL_SPECIALTIES

st.set_page_config(page_title="Find Doctors — EchoCare", page_icon="🏥", layout="wide")
auth.require_login()
styles.inject()
user = auth.current_user()

styles.hero("Find Doctors, District by District",
            "Alg. 5 suggests a specialty from your evidence; Alg. 6 ranks doctors by rating, "
            "experience, and proximity across a demo directory of 117 doctors in 10 Tamil Nadu districts.")

st.markdown(
    styles.badge("Demo directory — replace with a real hospital/Places dataset for production", "demo"),
    unsafe_allow_html=True,
)

# ---------------- Alg. 5: department suggestion from evidence ----------------
chunks = db.get_evidence_chunks(user["id"])
symptom_text = " ".join(c["text"] for c in chunks if c["source_type"] in ("narrative", "survey"))
suggested_specialty = None
if symptom_text.strip():
    with st.expander("💡 Suggested specialty based on your evidence", expanded=True):
        pred = predict_department(symptom_text)
        suggested_specialty = pred["top_department"]
        st.markdown(f"**{suggested_specialty}** ({round(pred['confidence']*100)}% match, {pred['model_used']})")
        for alt in pred["ranked"][1:]:
            st.caption(f"Also consider: {alt['department']} ({round(alt['score']*100)}%)")
        st.caption("This is a suggested starting point, not a diagnosis.")

st.divider()

# ---------------- Filters ----------------
c1, c2, c3 = st.columns(3)
with c1:
    district = st.selectbox("District", ["All districts"] + sorted(dd.DISTRICTS.keys()))
with c2:
    default_idx = (["All specialties"] + ALL_SPECIALTIES).index(suggested_specialty) if suggested_specialty else 0
    specialty = st.selectbox("Specialty", ["All specialties"] + ALL_SPECIALTIES, index=default_idx)
with c3:
    sort_by = st.selectbox("Sort by", ["Best match", "Highest rated", "Most experienced"])

matches = dd.find_doctors(district=district, specialty=specialty)
center = dd.DISTRICTS.get(district, (11.0, 78.5)) if district != "All districts" else (11.0, 78.5)
ranked = dd.rank_doctors(matches, center[0], center[1])

if sort_by == "Highest rated":
    ranked.sort(key=lambda x: x["rating"], reverse=True)
elif sort_by == "Most experienced":
    ranked.sort(key=lambda x: x["years_experience"], reverse=True)

st.markdown(f"**{len(ranked)} doctor(s) found**")

# ---------------- Map ----------------
zoom = 11 if district != "All districts" else 7
# Standard OpenStreetMap tiles: the only free, no-API-key tile provider left
# after CartoDB/Stamen started requiring keys — keeps this app to Gemini +
# Tavily as its only two external services, per project constraints.
fmap = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")
for doc in ranked[:60]:
    popup = (f"<b>{doc['name']}</b><br>{doc['specialty']}<br>{doc['hospital']}<br>"
             f"★ {doc['rating']} · {doc['years_experience']}y exp<br>₹{doc['consultation_fee_inr']} consult")
    folium.CircleMarker(
        location=[doc["lat"], doc["lon"]], radius=7,
        color="#FF8C1A", fill=True, fill_color="#FF8C1A", fill_opacity=0.85,
        popup=folium.Popup(popup, max_width=250),
    ).add_to(fmap)
st_folium(fmap, height=420, use_container_width=True, returned_objects=[])

# ---------------- Doctor cards ----------------
st.markdown("### Ranked results")
for doc in ranked[:20]:
    dist_str = f" · {doc['distance_km']} km away" if doc.get("distance_km") is not None else ""
    st.markdown(f"""
        <div class="tuf-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <strong>{doc['name']}</strong> — {doc['specialty']}<br/>
                    <span style="color:var(--muted);font-size:.85rem;">{doc['hospital']}, {doc['district']}{dist_str}</span>
                </div>
                {styles.badge(f"★ {doc['rating']}", "high" if doc['rating']>=4.3 else "moderate")}
            </div>
            <div style="margin-top:8px;color:var(--muted);font-size:.82rem;">
                {doc['years_experience']} yrs experience · ₹{doc['consultation_fee_inr']} consultation · {doc['phone']}
            </div>
        </div>
    """, unsafe_allow_html=True)

if not ranked:
    st.info("No doctors match this filter combination. Try a different district or specialty.")

# ---------------- Grounded department info (Tavily) ----------------
if suggested_specialty:
    st.divider()
    st.markdown(f"### What does {suggested_specialty} treat?")
    if llm.tavily_configured():
        with st.spinner("Fetching grounded background..."):
            result = llm.tavily_search(f"what does a {suggested_specialty} specialist treat, when to see one")
        if result["ok"]:
            for r in result["results"][:2]:
                st.markdown(f"**[{r['title']}]({r['url']})**")
                st.caption((r["content"] or "")[:280])
        else:
            st.warning(f"Web grounding unavailable: {result.get('reason') or 'unknown Tavily error'}")
    else:
        st.caption("Set `TAVILY_API_KEY` in secrets to show grounded background here.")
