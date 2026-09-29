import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import auth  # noqa: E402
import db  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Fresh SQLite file per test; no Gemini/Tavily keys unless a test sets them."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    for k in ("GOOGLE_API_KEY", "TAVILY_API_KEY", "ADMIN_EMAILS", "GEMINI_MODEL"):
        monkeypatch.delenv(k, raising=False)
    db.init_db()


@pytest.fixture
def user():
    uid = db.create_user("Test Patient", "patient@test.com", auth.hash_password("password123"))
    return {"id": uid, "name": "Test Patient", "email": "patient@test.com"}


def run_page(path, user, timeout=60, **state):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(path, default_timeout=timeout)
    at.session_state["user"] = user
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()
