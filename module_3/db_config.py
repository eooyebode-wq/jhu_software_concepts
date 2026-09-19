"""Database connection settings, read from environment variables."""

import os

import psycopg


def get_settings():
    """Return the connection settings as a dictionary.

    Host, port and database name have defaults that match a local
    Postgres.app install. User and password are only added if they are set,
    so nothing secret ever has to be written in the code.
    """
    settings = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": os.environ.get("DB_PORT", "5432"),
        "dbname": os.environ.get("DB_NAME", "gradcafe"),
    }

    user = os.environ.get("DB_USER")
    if user:
        settings["user"] = user

    password = os.environ.get("DB_PASSWORD")
    if password:
        settings["password"] = password

    return settings


def get_connection():
    """Open and return a psycopg connection to the database."""
    return psycopg.connect(**get_settings())
