"""
Lightweight auth for the single-process Streamlit app: bcrypt-hashed passwords
in SQLite, session identity kept in st.session_state (Streamlit re-runs the
whole script on every interaction, but session_state persists across reruns
within one browser session/tab).
"""
import bcrypt
import streamlit as st
import db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def register_user(name: str, email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if db.get_user_by_email(email):
        return False, "An account with this email already exists."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    user_id = db.create_user(name.strip(), email, hash_password(password))
    st.session_state["user"] = {"id": user_id, "name": name.strip(), "email": email}
    return True, "Account created."


def login_user(email: str, password: str) -> tuple[bool, str]:
    user = db.get_user_by_email(email.strip().lower())
    if not user or not verify_password(password, user["password_hash"]):
        return False, "Incorrect email or password."
    st.session_state["user"] = {"id": user["id"], "name": user["name"], "email": user["email"]}
    return True, "Welcome back."


def logout_user():
    st.session_state.pop("user", None)


def current_user() -> dict | None:
    return st.session_state.get("user")


def require_login():
    """Call at the top of every protected page. Stops the page render if not logged in."""
    if not current_user():
        st.warning("Please log in from the Home page to access EchoCare.")
        st.stop()
