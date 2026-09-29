import html
import streamlit as st
import plotly.graph_objects as go

import db, styles, ui, i18n, llm, doctors_data as dd
from department_classifier import predict_department

user = ui.page_setup("Find Doctors", "🏥")
directory = dd.get_directory()
source = dd.directory_source(directory)
styles.hero(i18n.t("doctors_title"), "Alg. 5 suggests a specialty from your evidence; Alg. 6 ranks doctors by rating, "
            "experience and distance. Tap Navigate to open directions.", eyebrow="Care finder")
st.markdown(styles.badge(f"Demo directory ({len(directory)} doctors): an admin can import a real one" if source == "demo"
                         else f"Imported real directory · {len(directory)} doctors", "demo" if source == "demo" else "high"),
            unsafe_allow_html=True)

chunks = db.get_evidence_chunks(user["id"])
text = " ".join(c["text"] for c in chunks if c["source_type"] in ("narrative", "survey", "photo"))
suggested = None
if text.strip():
    pred = predict_department(text)
    suggested = pred["top_department"]
    with st.expander("💡 Suggested specialty based on your evidence", expanded=True):
        st.markdown(f"**{suggested}** · {round(pred['confidence'] * 100)}% match ({pred['model_used']})")
        for alt in pred["ranked"][1:]:
            st.caption(f"Also consider: {alt['department']} ({round(alt['score'] * 100)}%)")
        st.caption("A suggested starting point, not a diagnosis.")

tab_dir, tab_live = st.tabs(["🗺️ Directory & map", "🔎 Live search (Tavily)"])

with tab_dir:
    districts = dd.directory_districts(directory)
    specialties = ["All specialties"] + dd.directory_specialties(directory)
    c1, c2, c3 = st.columns(3)
    district = c1.selectbox(i18n.t("district"), ["All districts"] + list(districts))
    spec = c2.selectbox(i18n.t("specialty"), specialties, index=specialties.index(suggested) if suggested in specialties else 0)
    sort_by = c3.selectbox("Sort by", ["Best match", "Highest rated", "Most experienced", "Lowest fee"])

    matches = dd.find_doctors(district, spec, directory)
    if district != "All districts":
        center, zoom = districts[district], 11
    else:
        allp = [(d["lat"], d["lon"]) for d in directory] or [(11.0, 78.5)]
        center, zoom = (sum(p[0] for p in allp) / len(allp), sum(p[1] for p in allp) / len(allp)), 7
    ranked = dd.rank_doctors(matches, center[0], center[1])
    if sort_by == "Highest rated": ranked.sort(key=lambda x: -x["rating"])
    elif sort_by == "Most experienced": ranked.sort(key=lambda x: -x["years_experience"])
    elif sort_by == "Lowest fee": ranked.sort(key=lambda x: x["consultation_fee_inr"])
    st.markdown(f"**{len(ranked)} doctor(s) found**")

    # A plain longitude/latitude scatter plot rather than a live tile map: every tile-based mapping
    # option we evaluated (streamlit-folium, st.map, Plotly's tile-based scatter_map) depends on an
    # external tile/token service and breaks in offline dev machines, campus networks, or version
    # mismatches — unacceptable for a project that must "just run". This schematic view needs no
    # network call at all. Real turn-by-turn navigation still works via the "Navigate" button below,
    # which opens Google Maps directly and needs no API key.
    if ranked:
        fig = go.Figure()
        by_spec: dict[str, list] = {}
        for doc in ranked[:80]:
            by_spec.setdefault(doc["specialty"], []).append(doc)
        palette = ["#2563EB", "#DC2626", "#16A34A", "#D97706", "#7C3AED", "#DB2777", "#0891B2", "#65A30D", "#EA580C", "#4F46E5"]
        for i, (spec, docs) in enumerate(sorted(by_spec.items())):
            fig.add_trace(go.Scatter(
                x=[d["lon"] for d in docs], y=[d["lat"] for d in docs], mode="markers", name=spec,
                marker=dict(size=13, color=palette[i % len(palette)], line=dict(width=1, color="white")),
                text=[f"{d['name']}<br>{d['hospital']}<br>★ {d['rating']} · {d['years_experience']}y" for d in docs],
                hovertemplate="%{text}<extra>" + spec + "</extra>"))
        if district != "All districts":
            fig.add_trace(go.Scatter(x=[center[1]], y=[center[0]], mode="markers", name=district,
                                     marker=dict(size=18, color="#0F172A", symbol="star"),
                                     hovertemplate=f"{district} centre<extra></extra>"))
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white",
                          legend=dict(orientation="h", y=1.15, font=dict(size=10)),
                          xaxis=dict(title="Longitude", showgrid=True, gridcolor="#F1F5F9"),
                          yaxis=dict(title="Latitude", showgrid=True, gridcolor="#F1F5F9", scaleanchor="x"),
                          plot_bgcolor="#F8FAFC")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Schematic positions, not street-level tiles — tap 🧭 Navigate on any doctor below for real turn-by-turn directions.")

    st.markdown("#### Ranked results")
    for doc in ranked[:15]:
        dist = f" · {doc['distance_km']} km from {district if district != 'All districts' else 'region centre'}" if doc.get("distance_km") is not None else ""
        st.markdown(f"""<div class="ec-card" style="margin-bottom:.4rem;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <div><b>{html.escape(doc['name'])}</b> · {html.escape(doc['specialty'])}<br>
              <span style="color:var(--muted);font-size:.85rem;">{html.escape(doc['hospital'])}, {html.escape(doc['district'])}{dist}</span></div>
              {styles.badge(f"★ {doc['rating']}", 'high' if doc['rating'] >= 4.3 else 'moderate')}</div>
            <div style="color:var(--muted);font-size:.82rem;margin-top:6px;">{doc['years_experience']} yrs · ₹{doc['consultation_fee_inr']} · {html.escape(doc['phone'] or 'no phone listed')}</div></div>""",
                    unsafe_allow_html=True)
        b1, b2, _ = st.columns([1, 1, 4])
        b1.link_button("🧭 Navigate", dd.navigate_url(doc["lat"], doc["lon"]))
        if b2.button("📅 Book", key=f"book_{doc.get('id', doc['name'])}_{doc['name']}"):
            st.session_state["book_doctor"] = doc
            st.switch_page("pages/14_📅_Appointments.py")
    if not ranked:
        st.info("No doctors match these filters.")

with tab_live:
    st.caption("Searches the live web with Tavily for hospitals and doctors, useful where the directory has no coverage.")
    c1, c2 = st.columns(2)
    place = c1.text_input("City / district", value="Chennai")
    lspec = c2.selectbox("Specialty", dd.directory_specialties(directory), index=0, key="live_spec")
    if st.button("Search the web", type="primary"):
        if not llm.tavily_configured():
            st.warning("Set `TAVILY_API_KEY` to enable live search.")
        else:
            with st.spinner("Searching..."):
                res = llm.tavily_search(f"best {lspec} doctors hospitals in {place}", max_results=5)
            st.session_state["live_results"] = (place, lspec, res)
    if st.session_state.get("live_results"):
        p, s, res = st.session_state["live_results"]
        st.link_button(f"🗺️ Open '{s} near {p}' in Google Maps", dd.maps_search_url(f"{s} hospital {p}"))
        if not res["ok"] or not res["results"]:
            st.caption("No web results right now.")
        else:
            if llm.gemini_configured():
                ctx = "\n".join(f"- {r['title']}: {(r['content'] or '')[:350]}" for r in res["results"])
                summ = llm.gemini_generate(f"From ONLY these search results, list up to 5 hospitals or doctors for {s} in {p} (name and area if given). "
                                           f"If the results don't name any, say so.\n{ctx}")
                if summ["ok"]:
                    st.markdown(f'<div class="ec-card">{summ["text"]}</div>', unsafe_allow_html=True)
            for r in res["results"]:
                st.markdown(f"**[{r['title']}]({r['url']})**  \n<span style='color:var(--muted);font-size:.85rem;'>{(r['content'] or '')[:240]}</span>", unsafe_allow_html=True)
            st.caption("Web results are unverified. Confirm availability and credentials before visiting.")
