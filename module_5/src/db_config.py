"""Database connection settings, read from the DB_* environment variables."""

import os
from urllib.parse import quote

import psycopg
from dotenv import load_dotenv

REQUIRED_VARIABLES = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")


def get_database_url():
    """Build the database URL from the DB_* environment variables.

    A local .env file is read first. Variables already set in the
    environment win over the file.

    Returns:
        A URL such as postgresql://user:password@localhost:5432/gradcafe.

    Raises:
        RuntimeError: If any of the variables is missing or empty.
    """
    load_dotenv()
    values = {name: os.environ.get(name) for name in REQUIRED_VARIABLES}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError("Set these environment variables: " + ", ".join(missing))
    user = quote(values["DB_USER"], safe="")
    password = quote(values["DB_PASSWORD"], safe="")
    return (
        f"postgresql://{user}:{password}@{values['DB_HOST']}:{values['DB_PORT']}"
        f"/{values['DB_NAME']}"
    )


def get_connection(database_url=None):
    """Open and return a psycopg connection to the database.

    Args:
        database_url: Optional URL that replaces the DB_* variables, used by
            tests.

    Returns:
        An open psycopg connection.
    """
    return psycopg.connect(database_url or get_database_url())
