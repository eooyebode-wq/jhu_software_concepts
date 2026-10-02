"""End-to-end tests: pull, update, then render."""

import pytest
from bs4 import BeautifulSoup

pytestmark = pytest.mark.integration


def count_rows(conn):
    """How many rows are in the applicants table."""
    return conn.execute("SELECT COUNT(*) FROM applicants").fetchone()[0]


def page_text(client):
    """The visible text of the analysis page."""
    html = client.get("/analysis").get_data(as_text=True)
    return BeautifulSoup(html, "html.parser").get_text()


def test_pull_then_update_then_render(client, db_conn, fake_records):
    # Given a fake scraper that returns several records
    # When we pull
    pull = client.post("/pull-data")
    # Then the pull succeeds and the rows are in the database
    assert pull.status_code == 200
    assert count_rows(db_conn) == len(fake_records)

    # When we update the analysis
    update = client.post("/update-analysis")
    # Then the update succeeds
    assert update.status_code == 200

    # When we load the page
    text = page_text(client)
    # Then it shows the new values, correctly formatted
    assert "Answer: Fall 2026 applicant count: 4" in text
    assert "Answer: Percent international: 42.86%" in text
    assert "Answer: Fall 2025 acceptance percentage: 33.33%" in text
    assert "Answer: Original-field count: 1" in text


def test_page_changes_after_a_pull(client):
    # Given a page shown before any pull
    before = page_text(client)
    # When we pull and load the page again
    client.post("/pull-data")
    after = page_text(client)
    # Then the analysis is different
    assert "Answer: Fall 2026 applicant count: 0" in before
    assert "Answer: Fall 2026 applicant count: 4" in after


def test_overlapping_pulls_stay_consistent(make_app, db_conn, fake_records):
    # Given two pulls whose records overlap on ids 1004 and 1005
    batches = [fake_records[:5], fake_records[3:]]
    client = make_app(scraper=lambda: batches.pop(0)).test_client()
    # When we pull twice
    client.post("/pull-data")
    client.post("/pull-data")
    # Then every record is stored exactly once
    ids = [row[0] for row in db_conn.execute("SELECT p_id FROM applicants ORDER BY p_id")]
    assert ids == [record["id"] for record in fake_records]
