"""
Auth + active-profile handling.

session_state["user"]              -> the logged-in ACCOUNT
session_state["active_profile_id"] -> optional family member being viewed
current_user()                     -> the active profile (what data pages read/write)
account_user()                     -> always the logged-in account
"""
import bcrypt
import streamlit as st
import db
from config import get_secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def register_user(name: str, email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if not name.strip() or "@" not in email:
        return False, "Please enter your name and a valid email."
    if db.get_user_by_email(email):
        return False, "An account with this email already exists."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    user_id = db.create_user(name.strip(), email, hash_password(password))
    st.session_state["user"] = {"id": user_id, "name": name.strip(), "email": email}
    st.session_state.pop("active_profile_id", None)
    return True, "Account created."


def login_user(email: str, password: str) -> tuple[bool, str]:
    user = db.get_user_by_email(email.strip().lower())
    if not user or user.get("owner_id") or not verify_password(password, user["password_hash"]):
        return False, "Incorrect email or password."
    st.session_state["user"] = {"id": user["id"], "name": user["name"], "email": user["email"]}
    st.session_state.pop("active_profile_id", None)
    return True, "Welcome back."


def logout_user():
    for k in ("user", "active_profile_id"):
        st.session_state.pop(k, None)


def account_user() -> dict | None:
    return st.session_state.get("user")


def current_user() -> dict | None:
    """The profile whose data is being viewed (account itself, or a family member)."""
    account = account_user()
    if not account:
        return None
    pid = st.session_state.get("active_profile_id")
    if pid and pid != account["id"]:
        member = db.get_user_by_id(pid)
        if member and member.get("owner_id") == account["id"]:
            return {"id": member["id"], "name": member["name"], "email": member["email"],
                    "is_member": True, "relation": member.get("relation")}
        st.session_state.pop("active_profile_id", None)
    return account


def set_active_profile(profile_id: int | None):
    if profile_id is None:
        st.session_state.pop("active_profile_id", None)
    else:
        st.session_state["active_profile_id"] = profile_id


def _secret(name: str) -> str:
    return get_secret(name)


def is_admin() -> bool:
    """Admin = email listed in ADMIN_EMAILS secret; if none configured, the first registered account."""
    account = account_user()
    if not account:
        return False
    configured = [e.strip().lower() for e in _secret("ADMIN_EMAILS").split(",") if e.strip()]
    if configured:
        return account["email"].lower() in configured
    return db.first_account_id() == account["id"]


def require_login():
    if not account_user():
        st.warning("Please log in from the Home page to access EchoCare.")
        st.stop()
