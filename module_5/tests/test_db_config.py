"""Tests for how the database settings are read."""

import pytest
from dotenv import load_dotenv

import db_config

pytestmark = pytest.mark.db

SETTINGS = {
    "DB_HOST": "example",
    "DB_PORT": "5432",
    "DB_NAME": "db_test",
    "DB_USER": "app_user",
    "DB_PASSWORD": "pass word@1",
}


@pytest.fixture(autouse=True)
def ignore_env_file(monkeypatch):
    """Keep a developer's real .env file out of these tests."""
    monkeypatch.setattr(db_config, "load_dotenv", lambda: False)


def set_all(monkeypatch):
    """Put the example settings in the environment."""
    for name, value in SETTINGS.items():
        monkeypatch.setenv(name, value)


def test_get_database_url_is_built_from_the_environment(monkeypatch):
    set_all(monkeypatch)
    url = db_config.get_database_url()
    # The password is percent-encoded so special characters cannot break the URL
    assert url == "postgresql://app_user:pass%20word%401@example:5432/db_test"


@pytest.mark.parametrize("name", db_config.REQUIRED_VARIABLES)
@pytest.mark.parametrize("value", [None, ""])
def test_get_database_url_fails_when_a_variable_is_missing(monkeypatch, name, value):
    # Given one variable is missing or empty
    set_all(monkeypatch)
    if value is None:
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, value)
    # Then asking for the URL raises an error that names it
    with pytest.raises(RuntimeError, match=name):
        db_config.get_database_url()


def test_get_database_url_reads_the_env_file(monkeypatch, tmp_path):
    # Given the variables exist only in a .env file
    for name in SETTINGS:
        # setenv first, so the variable is removed again after the test
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    env_file = tmp_path / ".env"
    env_file.write_text("".join(f"{k}={v}\n" for k, v in SETTINGS.items()))
    monkeypatch.setattr(db_config, "load_dotenv", lambda: load_dotenv(env_file))
    # When the URL is built
    url = db_config.get_database_url()
    # Then the file's values are used
    assert url.endswith("@example:5432/db_test")


def test_get_connection_uses_the_given_url_over_the_environment(monkeypatch, database_url):
    # Given a broken setting in the environment and a good URL passed in
    set_all(monkeypatch)
    monkeypatch.setenv("DB_PORT", "1")
    # When we connect with the good one
    with db_config.get_connection(database_url) as conn:
        # Then the connection works
        assert conn.execute("SELECT 1").fetchone() == (1,)
