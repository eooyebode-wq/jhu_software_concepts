"""Tests for how the database URL is read."""

import pytest

import db_config

pytestmark = pytest.mark.db


def test_get_database_url_reads_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db_test")
    assert db_config.get_database_url() == "postgresql://example/db_test"


@pytest.mark.parametrize("value", [None, ""])
def test_get_database_url_fails_when_it_is_not_set(monkeypatch, value):
    # Given DATABASE_URL is missing or empty
    if value is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", value)
    # Then asking for it raises a clear error
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        db_config.get_database_url()


def test_get_connection_uses_the_given_url_over_the_environment(monkeypatch, database_url):
    # Given a broken URL in the environment and a good one passed in
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:1/nope_test")
    # When we connect with the good one
    with db_config.get_connection(database_url) as conn:
        # Then the connection works
        assert conn.execute("SELECT 1").fetchone() == (1,)
