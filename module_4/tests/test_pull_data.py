"""Tests for pull_data.py with Chrome, sockets and the site replaced by fakes."""

import runpy
import socket
import sys

import psycopg
import pytest
from selenium.common.exceptions import WebDriverException

import pull_data

pytestmark = pytest.mark.db

NEXT_URL = "https://www.thegradcafe.com/survey/?page=2"


class FakeSocket:
    """Stands in for an open connection to Chrome's debugging port."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeDriver:
    """A browser that only counts how often it was closed."""

    def __init__(self):
        self.quit_calls = 0

    def quit(self):
        """Count the call."""
        self.quit_calls += 1


def make_page(records, next_url=None):
    """Build the JSON structure that the site puts in each page."""
    return {"props": {"results": {"data": records, "links": {"next": next_url}}}}


@pytest.fixture
def offline(monkeypatch):
    """Replace robots.txt, the browser and sleep so pulling runs offline."""
    driver = FakeDriver()
    monkeypatch.setattr(pull_data.scrape, "_robots_allows", lambda path: True)
    monkeypatch.setattr(pull_data.scrape, "_attach_driver", lambda: driver)
    monkeypatch.setattr(pull_data.time, "sleep", lambda seconds: None)
    return driver


def test_chrome_is_open_when_the_port_accepts_a_connection(monkeypatch):
    monkeypatch.setattr(pull_data.socket, "create_connection",
                        lambda address, timeout=None: FakeSocket())
    assert pull_data.chrome_is_open() is True


def test_chrome_is_not_open_when_the_connection_is_refused(monkeypatch):
    def refuse(address, timeout=None):
        raise OSError("refused")

    monkeypatch.setattr(pull_data.socket, "create_connection", refuse)
    assert pull_data.chrome_is_open() is False


def test_get_known_ids_returns_every_p_id(seed_db, db_conn, fake_records):
    # Given a database with data
    seed_db()
    # When we ask for the known ids
    known = pull_data.get_known_ids(db_conn)
    # Then they are the ids of the loaded records
    assert known == {record["id"] for record in fake_records}


def test_fetch_keeps_new_entries_and_stops_at_a_page_with_none(offline, monkeypatch, capsys):
    # Given a first page with one known and two new entries, then a page of known ones
    pages = {
        pull_data.scrape.SURVEY_URL: make_page([{"id": 1}, {"id": 2}, {"id": 3}], NEXT_URL),
        NEXT_URL: make_page([{"id": 2}], "https://www.thegradcafe.com/survey/?page=3"),
    }
    monkeypatch.setattr(pull_data.scrape, "_fetch_page_json", lambda driver, url: pages[url])
    # When we fetch with id 2 already known
    records = pull_data.fetch_new_raw_records({2})
    # Then only the new entries come back and the browser is closed
    assert [r["id"] for r in records] == [1, 3]
    assert offline.quit_calls == 1
    assert "Page 1: 2 new of 3" in capsys.readouterr().out


def test_fetch_follows_next_links_until_there_are_none(offline, monkeypatch):
    # Given two pages of new entries, the last with no next link
    pages = {
        pull_data.scrape.SURVEY_URL: make_page([{"id": 1}], NEXT_URL),
        NEXT_URL: make_page([{"id": 2}], None),
    }
    monkeypatch.setattr(pull_data.scrape, "_fetch_page_json", lambda driver, url: pages[url])
    # When we fetch
    records = pull_data.fetch_new_raw_records(set())
    # Then both pages are read
    assert [r["id"] for r in records] == [1, 2]


def test_fetch_refuses_when_robots_forbids(monkeypatch):
    # Given a robots.txt that forbids /survey/ and a browser that must not be used
    monkeypatch.setattr(pull_data.scrape, "_robots_allows", lambda path: False)

    def must_not_attach():
        raise AssertionError("the browser should not be opened")

    monkeypatch.setattr(pull_data.scrape, "_attach_driver", must_not_attach)
    # Then fetching raises before opening the browser
    with pytest.raises(RuntimeError, match="robots.txt"):
        pull_data.fetch_new_raw_records(set())


def test_fetch_refuses_an_off_site_link_and_closes_the_browser(offline, monkeypatch):
    # Given a first page that links to another site
    monkeypatch.setattr(pull_data.scrape, "_fetch_page_json",
                        lambda driver, url: make_page([{"id": 1}], "https://example.com/"))
    # Then fetching raises, and the browser is still closed
    with pytest.raises(RuntimeError, match="off-site"):
        pull_data.fetch_new_raw_records(set())
    assert offline.quit_calls == 1


def test_scrape_new_records_needs_chrome(monkeypatch):
    # Given Chrome is not open
    monkeypatch.setattr(pull_data, "chrome_is_open", lambda: False)
    # Then scraping says so
    with pytest.raises(RuntimeError, match="Chrome"):
        pull_data.scrape_new_records()


def test_scrape_new_records_skips_entries_already_stored(monkeypatch, seed_db, database_url,
                                                        fake_records):
    # Given stored entries and an open Chrome
    seed_db()
    monkeypatch.setattr(pull_data, "chrome_is_open", lambda: True)
    seen = {}

    def fake_fetch(known_ids):
        seen["known"] = known_ids
        return ["raw"]

    monkeypatch.setattr(pull_data, "fetch_new_raw_records", fake_fetch)
    # When we scrape
    result = pull_data.scrape_new_records(database_url)
    # Then the stored ids were passed on and the new records returned
    assert seen["known"] == {record["id"] for record in fake_records}
    assert result == ["raw"]


def test_run_pull_skips_records_without_an_id(fake_records, recording_loader):
    # Given a scraped record that has no id
    scraped = fake_records + [{"id": None, "program": "No id"}]
    # When the pull runs
    pull_data.run_pull(lambda: scraped, recording_loader)
    # Then the loader gets rows only for records with an id
    assert len(recording_loader.calls[0]) == len(fake_records)


def test_main_reports_how_many_entries_were_added(monkeypatch, capsys):
    monkeypatch.setattr(pull_data, "run_pull", lambda scraper, loader: 3)
    assert pull_data.main() == 0
    assert "DONE: added 3 new entries." in capsys.readouterr().out


@pytest.mark.parametrize(
    "error, expected",
    [
        (psycopg.OperationalError("down"), "database problem"),
        (WebDriverException("crash"), "could not connect to Chrome"),
        (ValueError("odd"), "ERROR: odd"),
    ],
)
def test_main_returns_1_and_says_what_went_wrong(monkeypatch, capsys, error, expected):
    # Given a pull that fails with each kind of error
    def fails(scraper, loader):
        raise error

    monkeypatch.setattr(pull_data, "run_pull", fails)
    # When main runs
    exit_code = pull_data.main()
    # Then it returns 1 and prints a message
    assert exit_code == 1
    assert expected in capsys.readouterr().out


def test_running_the_file_as_a_script_exits_with_the_result(monkeypatch, src_dir, capsys):
    # Given a Chrome port that refuses connections, so nothing is scraped
    def refuse(address, timeout=None):
        raise OSError("refused")

    monkeypatch.setattr(socket, "create_connection", refuse)
    # When the file runs as __main__
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(src_dir / "pull_data.py"), run_name="__main__")
    # Then it exits with 1 and says Chrome is not open
    assert exit_info.value.code == 1
    assert "Chrome" in capsys.readouterr().out
    assert sys.modules["pull_data"] is pull_data
