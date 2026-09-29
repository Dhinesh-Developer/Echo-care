import html
import streamlit as st

import db, styles, ui, i18n, agent, llm

user = ui.page_setup("Echo Companion", "💬")
styles.hero(i18n.t("chat_title"), "Checks safety first, asks what's missing, grounds answers in your own evidence, "
            "and searches the web only when needed.", eyebrow="Agent")
st.caption(f"{i18n.t('not_a_doctor')} {i18n.t('emergency_note')}")
if not llm.gemini_configured():
    st.warning("Gemini isn't configured (`GOOGLE_API_KEY` missing). Echo can still ask follow-up questions and run the safety check, but can't write answers.")

history = db.get_chat_history(user["id"])
box = st.container(height=440)
with box:
    if not history:
        st.markdown('<div class="ec-chat-bot">Hi, I\'m Echo. Tell me what\'s bothering you, or ask about your tracker, reports or medicines.</div>', unsafe_allow_html=True)
    for m in history:
        cls = "ec-chat-user" if m["role"] == "user" else "ec-chat-bot"
        if m.get("is_emergency"):
            cls += " ec-chat-emergency"
        content = m["content"]
        if content == ("Echo can't generate a reply right now because the Gemini API key isn't configured or couldn't "
                       "be reached. Your message is saved."):
            content = ("This is a saved error from an earlier run. Send a new message to see the current Gemini "
                       "error details. Your earlier message is saved.")
        st.markdown(f'<div class="{cls}">{html.escape(content).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

prompt = st.chat_input(i18n.t("chat_placeholder"))
if prompt:
    prior = [{"role": m["role"], "content": m["content"], "kind": m.get("kind")} for m in history]
    db.insert_chat_message(user["id"], "user", prompt)
    with st.spinner("Echo is thinking..."):
        result = agent.run_agent(user["id"], prompt, prior)
    db.insert_chat_message(user["id"], "assistant", result["content"], result["is_emergency"], result.get("kind"))
    st.session_state["last_agent"] = result
    st.rerun()

last = st.session_state.get("last_agent")
if last:
    if last["is_emergency"]:
        st.error("This may be an emergency:")
        for name, contact in last.get("resources", []):
            st.write(f"**{name}:** {contact}")
    with st.expander("🔧 Tools the agent used on the last turn"):
        st.write(" → ".join(last["tools_used"]))
        for s in last.get("web_sources", []):
            st.markdown(f"- [{s['title']}]({s['url']})")
        if last.get("rag_chunk_ids"):
            st.caption(f"Grounded in {len(last['rag_chunk_ids'])} of your own evidence entries.")
