"""Database connection settings, read from the DATABASE_URL variable."""

import os

import psycopg


def get_database_url():
    """Return the database URL from the DATABASE_URL environment variable.

    Returns:
        The URL, for example postgresql://user:password@localhost:5432/gradcafe.

    Raises:
        RuntimeError: If DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set.")
    return url


def get_connection(database_url=None):
    """Open and return a psycopg connection to the database.

    Args:
        database_url: Optional URL that replaces DATABASE_URL, used by tests.

    Returns:
        An open psycopg connection.
    """
    return psycopg.connect(database_url or get_database_url())
