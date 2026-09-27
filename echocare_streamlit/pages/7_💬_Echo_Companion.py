import streamlit as st
import db, auth, styles, agent, llm

st.set_page_config(page_title="Echo Companion — EchoCare", page_icon="💬", layout="wide")
auth.require_login()
styles.inject()
user = auth.current_user()

styles.hero("Echo — Your AI Companion", "A tool-using agent: checks for emergencies first, "
                                        "grounds answers in your own evidence, and reaches for "
                                        "web search only when a question needs it.")

if not llm.gemini_configured():
    st.warning("Gemini isn't configured (`GOOGLE_API_KEY` missing) — Echo will save your message "
               "but can't generate a reply yet.")

history = db.get_chat_history(user["id"])
chat_box = st.container(height=420)
with chat_box:
    for m in history:
        css_class = "tuf-chat-user" if m["role"] == "user" else "tuf-chat-bot"
        emergency_class = " tuf-chat-emergency" if m.get("is_emergency") else ""
        st.markdown(f'<div class="{css_class}{emergency_class}">{m["content"]}</div>', unsafe_allow_html=True)

prompt = st.chat_input("Ask Echo about your symptoms, tracker trends, or reports...")
if prompt:
    db.insert_chat_message(user["id"], "user", prompt)
    with st.spinner("Echo is thinking (checking safety → your evidence → web grounding if needed)..."):
        result = agent.run_agent(user["id"], prompt)
    db.insert_chat_message(user["id"], "assistant", result["content"], result["is_emergency"])

    if result["is_emergency"]:
        st.error(result["content"])
        for name, contact in result.get("resources", []):
            st.write(f"**{name}:** {contact}")
    else:
        with st.expander("🔧 Tools used by the agent this turn"):
            st.write(", ".join(result["tools_used"]))
            if result["web_sources"]:
                st.caption("Web sources consulted:")
                for s in result["web_sources"]:
                    st.write(f"- [{s['title']}]({s['url']})")
    st.rerun()

st.caption("Echo is not a doctor and cannot diagnose you. In India, emergency services: 112.")
