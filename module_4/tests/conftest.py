"""Shared fixtures for the Grad Cafe tests."""

import copy
import os
import sys
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# pylint: disable=wrong-import-position
from app import create_app
from load_data import create_table, load_rows
from pull_data import run_pull

REQUIRED_MARKERS = {"web", "buttons", "analysis", "db", "integration"}


def pytest_collection_modifyitems(items):
    """Fail the run if any test has none of the required markers."""
    unmarked = [
        item.nodeid
        for item in items
        if not REQUIRED_MARKERS & {mark.name for mark in item.iter_markers()}
    ]
    if unmarked:
        raise pytest.UsageError("Tests without a marker: " + ", ".join(unmarked))


def make_record(entry_id, program, school, level, decision, season, student, gpa, gre):
    """Build one raw Grad Cafe record like the scraper returns."""
    return {
        "id": entry_id,
        "program": program,
        "school": school,
        "level": level,
        "decision": decision,
        "season": season,
        "status": student,
        "ugpa": gpa,
        "greq": gre,
        "created_at": "2026-01-15",
        "notes": "test entry",
    }


FAKE_RECORDS = [
    make_record(1001, "Computer Science", "Johns Hopkins University", "Masters",
                "Accepted", "Fall 2026", "International", "3.80", "165"),
    make_record(1002, "Computer Science", "MIT", "PhD",
                "Accepted", "Fall 2026", "American", "3.90", "168"),
    make_record(1003, "Computer Science", "Stanford", "PhD",
                "Rejected", "Fall 2026", "International", "3.50", "160"),
    make_record(1004, "Biology", "Duke", "Masters",
                "Accepted", "Fall 2025", "American", "3.70", "158"),
    make_record(1005, "Physics", "Yale", "PhD",
                "Rejected", "Fall 2025", "American", "3.60", "159"),
    make_record(1006, "Chemistry", "Rice", "Masters",
                "Rejected", "Fall 2025", "International", "3.40", "157"),
    make_record(1007, "History", "Brown", "Masters",
                "Interview", "Fall 2026", "American", "3.20", "150"),
]


@pytest.fixture(scope="session")
def database_url():
    """The test database URL. Stops the run if it could hit real data."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.exit("Set DATABASE_URL to a test database first.", returncode=2)
    if "test" not in (make_url(url).database or ""):
        pytest.exit(
            "The database name in DATABASE_URL must contain 'test', because "
            "every test empties the applicants table.",
            returncode=2,
        )
    return url


@pytest.fixture(autouse=True)
def clean_table(database_url):
    """Give every test an empty applicants table."""
    with psycopg.connect(database_url) as conn:
        create_table(conn)
        conn.execute("TRUNCATE applicants")


@pytest.fixture
def db_conn(database_url):
    """A separate connection for checking what is in the database."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        yield conn


@pytest.fixture
def fake_records():
    """Seven raw records, four for Fall 2026 and three for Fall 2025."""
    return copy.deepcopy(FAKE_RECORDS)


@pytest.fixture
def fake_scraper(fake_records):
    """A scraper that returns the fake records without touching the internet."""
    return lambda: copy.deepcopy(fake_records)


class RecordingLoader:  # pylint: disable=too-few-public-methods
    """A loader that remembers what it was given and writes nothing."""

    def __init__(self):
        self.calls = []

    def __call__(self, rows):
        self.calls.append(rows)
        return len(rows)


@pytest.fixture
def recording_loader():
    """A fake loader that records its calls."""
    return RecordingLoader()


@pytest.fixture
def make_app(database_url):
    """Build an app on the test database, with optional fakes."""
    def build(**overrides):
        config = {"TESTING": True, "DATABASE_URL": database_url}
        return create_app(config=config, **overrides)
    return build


@pytest.fixture
def app(make_app, fake_scraper):
    """An app with the fake scraper and the real loader."""
    return make_app(scraper=fake_scraper)


@pytest.fixture
def client(app):
    """Flask's test client for the app."""
    return app.test_client()


@pytest.fixture
def seed_db(database_url, fake_records):
    """Load records into the test database the same way a pull does."""
    def seed(records=None):
        chosen = fake_records if records is None else records
        return run_pull(lambda: chosen, lambda rows: load_rows(rows, database_url))
    return seed
