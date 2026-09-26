"""Tests for the Pull Data and Update Analysis buttons, including busy state."""

import pytest

from load_data import load_rows

pytestmark = pytest.mark.buttons


def count_rows(conn):
    """How many rows are in the applicants table."""
    return conn.execute("SELECT COUNT(*) FROM applicants").fetchone()[0]


def test_pull_data_returns_ok_when_not_busy(client):
    # Given an app that is not busy
    # When we post to pull-data
    response = client.post("/pull-data")
    # Then we get 200 (or 202) with ok true
    assert response.status_code in (200, 202)
    assert response.get_json() == {"ok": True}


def test_pull_data_gives_loader_the_scraper_rows(make_app, fake_scraper, fake_records,
                                                 recording_loader):
    # Given a fake scraper and a fake loader
    client = make_app(scraper=fake_scraper, loader=recording_loader).test_client()
    # When we post to pull-data
    client.post("/pull-data")
    # Then the loader ran once, with one row per scraped record
    assert len(recording_loader.calls) == 1
    assert [row[0] for row in recording_loader.calls[0]] == [r["id"] for r in fake_records]


def test_pull_data_is_free_again_after_it_finishes(app, client):
    # Given a finished pull
    client.post("/pull-data")
    # Then the busy state is cleared
    assert app.extensions["pull_state"].busy is False


def test_update_analysis_returns_200_when_not_busy(client):
    # Given an app that is not busy
    # When we post to update-analysis
    response = client.post("/update-analysis")
    # Then we get 200 with ok true
    assert response.status_code == 200
    assert response.get_json() == {"ok": True}


def test_update_analysis_refreshes_the_analysis(make_app):
    # Given a query function that counts its calls
    calls = []

    def query():
        calls.append(1)
        return {"questions": []}

    client = make_app(query_fn=query).test_client()
    # When we post to update-analysis
    client.post("/update-analysis")
    # Then the analysis was queried once
    assert len(calls) == 1


def test_update_analysis_returns_409_when_busy(app, client):
    # Given a pull in progress
    app.extensions["pull_state"].busy = True
    # When we post to update-analysis
    response = client.post("/update-analysis")
    # Then we get 409 with busy true
    assert response.status_code == 409
    assert response.get_json() == {"busy": True}


def test_update_analysis_does_nothing_when_busy(make_app):
    # Given a pull in progress and a query function that counts its calls
    calls = []
    app = make_app(query_fn=lambda: calls.append(1))
    app.extensions["pull_state"].busy = True
    # When we post to update-analysis
    app.test_client().post("/update-analysis")
    # Then nothing was queried
    assert calls == []


def test_pull_data_returns_409_when_busy(app, client):
    # Given a pull in progress
    app.extensions["pull_state"].busy = True
    # When we post to pull-data
    response = client.post("/pull-data")
    # Then we get 409 with busy true
    assert response.status_code == 409
    assert response.get_json() == {"busy": True}


def test_pull_data_does_not_scrape_when_busy(make_app):
    # Given a pull in progress and a scraper that counts its calls
    calls = []
    app = make_app(scraper=lambda: calls.append(1) or [])
    app.extensions["pull_state"].busy = True
    # When we post to pull-data
    app.test_client().post("/pull-data")
    # Then nothing was scraped
    assert calls == []


def test_loader_failure_returns_non_200(make_app, fake_scraper):
    # Given a loader that fails
    def failing_loader(rows):
        raise ValueError("load failed")

    client = make_app(scraper=fake_scraper, loader=failing_loader).test_client()
    # When we post to pull-data
    response = client.post("/pull-data")
    # Then the response is not 200 and says what went wrong
    assert response.status_code != 200
    assert response.get_json() == {"ok": False, "error": "load failed"}


def test_loader_failure_clears_busy_state(make_app, fake_scraper):
    # Given a loader that fails
    def failing_loader(rows):
        raise ValueError("load failed")

    app = make_app(scraper=fake_scraper, loader=failing_loader)
    # When the pull fails
    app.test_client().post("/pull-data")
    # Then the app is not stuck busy
    assert app.extensions["pull_state"].busy is False


def test_loader_failure_leaves_no_partial_writes(make_app, fake_scraper, database_url,
                                                 db_conn):
    # Given a real loader that hits a bad row after the good ones
    def loader_with_bad_row(rows):
        bad_row = (None,) + rows[0][1:]
        return load_rows(rows + [bad_row], database_url)

    client = make_app(scraper=fake_scraper, loader=loader_with_bad_row).test_client()
    # When we post to pull-data
    response = client.post("/pull-data")
    # Then the pull fails and no rows were kept
    assert response.status_code != 200
    assert count_rows(db_conn) == 0


def test_update_analysis_returns_500_when_database_fails(make_app):
    # Given a query function that cannot reach the database
    def broken_query():
        raise RuntimeError("no database")

    client = make_app(query_fn=broken_query).test_client()
    # When we post to update-analysis
    response = client.post("/update-analysis")
    # Then the response is not 200
    assert response.status_code == 500
    assert response.get_json()["ok"] is False
