"""Tests for scrape.py with the network and the browser replaced by fakes."""

import runpy
import sys

import pytest
from selenium.common.exceptions import WebDriverException

import scrape

pytestmark = pytest.mark.db

NEXT_URL = "https://www.thegradcafe.com/survey/?page=2"


class FakeResponse:
    """Stands in for the object urlopen returns."""

    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.text.encode("utf-8")


class FakeWait:  # pylint: disable=too-few-public-methods
    """Stands in for WebDriverWait, which would wait on a real page."""

    def __init__(self, driver, timeout):
        self.driver = driver
        self.timeout = timeout

    def until(self, condition):
        """Pretend the page is ready."""
        return condition is not None


class FakePageDriver:
    """A browser that returns a fixed HTML string."""

    def __init__(self, html):
        self.html = html
        self.visited = []

    def get(self, url):
        """Remember the visited url."""
        self.visited.append(url)

    def execute_script(self, script):
        """Return the fixed HTML instead of running the script."""
        return self.html


class FakeScrapeDriver:
    """A browser that only counts how often it was closed."""

    def __init__(self, fail_first_quit=False):
        self.quit_calls = 0
        self.fail_first_quit = fail_first_quit

    def quit(self):
        """Count the call, and fail the first time if asked to."""
        self.quit_calls += 1
        if self.fail_first_quit and self.quit_calls == 1:
            raise WebDriverException("already closed")


def make_page(records, next_url=None):
    """Build the JSON structure that the site puts in each page."""
    return {"props": {"results": {"data": records, "links": {"next": next_url}}}}


@pytest.fixture
def offline(monkeypatch):
    """Replace robots.txt, the browser and sleep so scrape_data runs offline."""
    driver = FakeScrapeDriver()
    monkeypatch.setattr(scrape, "robots_allows", lambda path: True)
    monkeypatch.setattr(scrape, "attach_driver", lambda address=None: driver)
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: None)
    return driver


def scrape_paths(tmp_path):
    """Where a test run keeps its progress files."""
    return {
        "raw_path": str(tmp_path / "raw.jsonl"),
        "state_path": str(tmp_path / "state.json"),
    }


def test_robots_allows_a_path_the_file_permits(monkeypatch):
    # Given a robots.txt that blocks only /private/
    monkeypatch.setattr(
        scrape.urllib.request, "urlopen",
        lambda request, timeout=None: FakeResponse("User-agent: *\nDisallow: /private/"),
    )
    # Then /survey/ is allowed
    assert scrape.robots_allows("/survey/") is True


def test_robots_blocks_a_path_the_file_forbids(monkeypatch):
    # Given a robots.txt that blocks /survey/
    monkeypatch.setattr(
        scrape.urllib.request, "urlopen",
        lambda request, timeout=None: FakeResponse("User-agent: *\nDisallow: /survey/"),
    )
    # Then /survey/ is not allowed, even when given as a full url
    assert scrape.robots_allows("https://www.thegradcafe.com/survey/") is False


@pytest.mark.parametrize(
    "url, expected",
    [
        (NEXT_URL, True),
        ("https://example.com/survey/", False),
        ("http://www.thegradcafe.com/survey/", False),
    ],
)
def test_only_https_links_on_the_site_are_followed(url, expected):
    assert scrape.is_same_site(url) is expected


def test_attach_driver_uses_the_given_debugger_address(monkeypatch):
    # Given a fake Chrome that remembers its options
    seen = {}

    def fake_chrome(options):
        seen["address"] = options.debugger_address
        return "driver"

    monkeypatch.setattr(scrape, "Chrome", fake_chrome)
    # When we attach
    driver = scrape.attach_driver("127.0.0.1:9999")
    # Then it connects to that address
    assert driver == "driver"
    assert seen["address"] == "127.0.0.1:9999"


def test_fetch_page_json_reads_the_data_page_attribute(monkeypatch):
    # Given a page whose #app div holds the JSON
    monkeypatch.setattr(scrape, "WebDriverWait", FakeWait)
    driver = FakePageDriver("<div id='app' data-page='{\"props\": {\"n\": 1}}'></div>")
    # When we fetch it
    data = scrape.fetch_page_json(driver, "https://www.thegradcafe.com/survey/")
    # Then the JSON is returned
    assert data == {"props": {"n": 1}}
    assert driver.visited == ["https://www.thegradcafe.com/survey/"]


def test_fetch_page_json_fails_when_the_data_is_missing(monkeypatch):
    # Given a page with no #app div
    monkeypatch.setattr(scrape, "WebDriverWait", FakeWait)
    driver = FakePageDriver("<html></html>")
    # Then fetching it raises a clear error
    with pytest.raises(RuntimeError, match="Could not find"):
        scrape.fetch_page_json(driver, "https://www.thegradcafe.com/survey/")


def test_raw_records_are_appended_and_read_back(tmp_path):
    # Given no file yet
    path = str(tmp_path / "raw.jsonl")
    assert scrape._load_raw_records(path) == []
    # When records are appended twice
    scrape._append_raw_records(path, [{"id": 1}, {"id": 2}])
    scrape._append_raw_records(path, [{"id": 3}])
    # Then all three are read back in order
    assert [r["id"] for r in scrape._load_raw_records(path)] == [1, 2, 3]


def test_state_is_saved_and_read_back(tmp_path):
    # Given no state file yet
    path = str(tmp_path / "state.json")
    assert scrape._load_state(path) is None
    # When the state is saved
    scrape._save_state(path, NEXT_URL, 5)
    # Then it is read back unchanged
    assert scrape._load_state(path) == {"next_url": NEXT_URL, "record_count": 5}


def test_scrape_data_refuses_when_robots_forbids(monkeypatch, tmp_path):
    # Given a robots.txt that forbids /survey/
    monkeypatch.setattr(scrape, "robots_allows", lambda path: False)
    # Then scraping stops before doing anything
    with pytest.raises(RuntimeError, match="robots.txt"):
        scrape.scrape_data(**scrape_paths(tmp_path))


def test_scrape_data_saves_each_page_until_there_is_no_next(offline, monkeypatch, tmp_path):
    # Given two pages, the second with no next link
    pages = {
        scrape.SURVEY_URL: make_page([{"id": 1}, {"id": 2}], NEXT_URL),
        NEXT_URL: make_page([{"id": 3}], None),
    }
    monkeypatch.setattr(scrape, "fetch_page_json", lambda driver, url: pages[url])
    paths = scrape_paths(tmp_path)
    # When we scrape
    records = scrape.scrape_data(max_records=10, **paths)
    # Then all records are returned, progress is saved and the browser is closed
    assert [r["id"] for r in records] == [1, 2, 3]
    assert scrape._load_state(paths["state_path"]) == {"next_url": None, "record_count": 3}
    assert offline.quit_calls == 1


def test_scrape_data_stops_at_max_records(offline, monkeypatch, tmp_path):
    # Given a first page that already reaches the limit
    requested = []

    def fake_fetch(driver, url):
        requested.append(url)
        return make_page([{"id": 1}, {"id": 2}], NEXT_URL)

    monkeypatch.setattr(scrape, "fetch_page_json", fake_fetch)
    # When we scrape with max_records 2
    records = scrape.scrape_data(max_records=2, **scrape_paths(tmp_path))
    # Then the second page is never requested
    assert len(records) == 2
    assert requested == [scrape.SURVEY_URL]


def test_scrape_data_returns_saved_records_without_a_browser(offline, tmp_path):
    # Given three records already saved
    paths = scrape_paths(tmp_path)
    scrape._append_raw_records(paths["raw_path"], [{"id": 1}, {"id": 2}, {"id": 3}])
    # When the target is only two
    records = scrape.scrape_data(max_records=2, **paths)
    # Then the first two are returned and no browser was opened
    assert [r["id"] for r in records] == [1, 2]
    assert offline.quit_calls == 0


def test_scrape_data_resumes_from_the_saved_state(offline, monkeypatch, tmp_path):
    # Given one saved record and a saved next link
    paths = scrape_paths(tmp_path)
    scrape._append_raw_records(paths["raw_path"], [{"id": 1}])
    scrape._save_state(paths["state_path"], NEXT_URL, 1)
    requested = []

    def fake_fetch(driver, url):
        requested.append(url)
        return make_page([{"id": 2}], None)

    monkeypatch.setattr(scrape, "fetch_page_json", fake_fetch)
    # When we scrape again
    records = scrape.scrape_data(max_records=10, **paths)
    # Then it starts at the saved link and keeps the old record
    assert requested == [NEXT_URL]
    assert [r["id"] for r in records] == [1, 2]


def test_scrape_data_refuses_to_follow_an_off_site_link(offline, tmp_path):
    # Given a start url on another site
    # Then scraping raises, and the browser is still closed
    with pytest.raises(RuntimeError, match="off-site"):
        scrape.scrape_data(start_url="https://example.com/", **scrape_paths(tmp_path))
    assert offline.quit_calls == 1


def test_scrape_data_reattaches_after_a_chrome_error(monkeypatch, tmp_path):
    # Given a browser whose first close fails, and one page that fails once
    driver = FakeScrapeDriver(fail_first_quit=True)
    attached = []
    monkeypatch.setattr(scrape, "robots_allows", lambda path: True)
    monkeypatch.setattr(scrape, "attach_driver",
                        lambda address=None: attached.append(1) or driver)
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: None)
    attempts = []

    def flaky_fetch(_driver, url):
        attempts.append(url)
        if len(attempts) == 1:
            raise WebDriverException("tab crashed")
        return make_page([{"id": 1}], None)

    monkeypatch.setattr(scrape, "fetch_page_json", flaky_fetch)
    # When we scrape
    records = scrape.scrape_data(max_records=10, **scrape_paths(tmp_path))
    # Then it attached a second time and still got the record
    assert len(attached) == 2
    assert [r["id"] for r in records] == [1]


def test_scrape_data_gives_up_after_too_many_chrome_errors(offline, monkeypatch, tmp_path,
                                                           capsys):
    # Given a page that always crashes the tab
    def always_crashes(driver, url):
        raise WebDriverException("tab crashed")

    monkeypatch.setattr(scrape, "fetch_page_json", always_crashes)
    # When we scrape
    records = scrape.scrape_data(max_records=10, **scrape_paths(tmp_path))
    # Then it stops with a message and returns what it has
    assert records == []
    assert "Stopping" in capsys.readouterr().out


def test_scrape_data_stops_on_any_other_error(offline, monkeypatch, tmp_path, capsys):
    # Given a page that fails with an unexpected error
    def fails(driver, url):
        raise ValueError("bad page")

    monkeypatch.setattr(scrape, "fetch_page_json", fails)
    # When we scrape
    records = scrape.scrape_data(max_records=10, **scrape_paths(tmp_path))
    # Then it stops right away and says why
    assert records == []
    assert "page fetch failed" in capsys.readouterr().out


def test_main_passes_the_command_line_options(monkeypatch):
    # Given a scrape_data that records its arguments
    seen = {}
    monkeypatch.setattr(scrape, "scrape_data", lambda **kwargs: seen.update(kwargs))
    # When main runs with every option
    scrape.main(["--max-records", "5", "--debugger-address", "host:1",
                 "--raw-path", "r.jsonl", "--state-path", "s.json"])
    # Then scrape_data got them
    assert seen == {"max_records": 5, "debugger_address": "host:1",
                    "raw_path": "r.jsonl", "state_path": "s.json"}


def test_main_uses_defaults_without_options(monkeypatch):
    # Given a scrape_data that records its arguments
    seen = {}
    monkeypatch.setattr(scrape, "scrape_data", lambda **kwargs: seen.update(kwargs))
    # When main runs with no options
    scrape.main([])
    # Then the defaults are used
    assert seen["max_records"] == scrape.DEFAULT_TARGET_RECORDS
    assert seen["debugger_address"] == scrape.DEBUGGER_ADDRESS


def test_running_the_file_as_a_script_reads_the_command_line(monkeypatch, src_dir, capsys):
    # Given the script started with --help, which exits before any scraping
    monkeypatch.setattr(sys, "argv", ["scrape.py", "--help"])
    # When it runs as __main__
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(src_dir / "scrape.py"), run_name="__main__")
    # Then it printed its usage and exited normally
    assert exit_info.value.code == 0
    assert "--max-records" in capsys.readouterr().out
