"""Shared test setup. Every test gets its own empty database, so the real one is never touched."""
import pytest

from database import db


@pytest.fixture(autouse=True)
def temporary_database(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_ANALYZER_DB", str(tmp_path / "test.db"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    db.init_db()
