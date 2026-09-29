"""Single place to read API keys / settings: environment first, then Streamlit secrets.

Reading st.secrets when NO secrets.toml exists makes Streamlit paint a red 'No secrets found' box
on the page, so we only touch st.secrets after confirming a secrets file is actually present."""
import os
import streamlit as st


def _secrets_present() -> bool:
    loader = getattr(st.secrets, "load_if_toml_exists", None)
    if loader:
        try:
            return bool(loader())
        except Exception:
            return False
    return any(os.path.exists(p) for p in (os.path.expanduser("~/.streamlit/secrets.toml"), ".streamlit/secrets.toml"))


def get_secret(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value:
        return value
    try:
        if _secrets_present() and name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return default
