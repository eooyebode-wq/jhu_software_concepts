# -*- coding: utf-8 -*-
"""Grad Cafe scraper: hybrid urllib3 (URL construction) + Selenium-attach (navigation)."""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.robotparser as robotparser

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.util import Url, parse_url

BASE_URL = "https://www.thegradcafe.com"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
SURVEY_URL = f"{BASE_URL}/survey/"
DEBUGGER_ADDRESS = "127.0.0.1:9222"

# A made-up but honest name for this scraper. I'm not pretending to be a
# browser or a different bot here.
USER_AGENT = "jhu-software-concepts-module2-scraper"


def _robots_allows(path: str, user_agent: str = USER_AGENT) -> bool:
    """Check thegradcafe.com/robots.txt before fetching `path`.

    Uses Python's built-in robotparser here instead of urllib3, since
    urllib3 doesn't have a robots.txt reader (see README).
    """
    rp = robotparser.RobotFileParser()
    # rp.read() sends Python's default user agent, which the site answers with
    # a 403, and robotparser treats a 403 as "everything is disallowed". So the
    # file is fetched here with this scraper's own user agent and passed in.
    request = urllib.request.Request(ROBOTS_URL, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=15) as response:
        rp.parse(response.read().decode("utf-8").splitlines())
    url = path if path.startswith("http") else BASE_URL + path
    return rp.can_fetch(user_agent, url)


def _build_entry_url(entry_id: int) -> str:
    """Construct the public permalink for a single applicant entry via urllib3."""
    return Url(scheme="https", host="www.thegradcafe.com", path=f"/result/{entry_id}").url


def _is_same_site(url: str) -> bool:
    """Inspect a URL (e.g. a pagination cursor link) via urllib3 before following it."""
    parsed = parse_url(url)
    return parsed.host == "www.thegradcafe.com" and parsed.scheme in (None, "https")


def _attach_driver(debugger_address: str = DEBUGGER_ADDRESS) -> webdriver.Chrome:
    """Connect Selenium to a Chrome window that's already open and already
    past Cloudflare's check, instead of opening a new browser (Chrome has to
    already be running with --remote-debugging-port, see README).
    """
    options = Options()
    options.debugger_address = debugger_address
    return webdriver.Chrome(options=options)


def _fetch_page_json(driver: webdriver.Chrome, url: str) -> dict:
    """Go to `url` and pull out the page's data.

    The site hides its results as JSON text inside the page's HTML, but that
    JSON disappears once the page finishes loading in the browser (I checked
    with driver.page_source and it was gone). So instead I have the browser
    re-fetch the same page's raw HTML, which still has the JSON in it, and
    read it from there with BeautifulSoup + json.loads.
    """
    driver.get(url)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "app")))

    raw_html = driver.execute_script(
        "return fetch(window.location.href).then(r => r.text());"
    )
    soup = BeautifulSoup(raw_html, "html.parser")
    app_div = soup.find(id="app")
    if app_div is None or not app_div.has_attr("data-page"):
        raise RuntimeError(f"Could not find #app[data-page] at {url}")
    return json.loads(app_div["data-page"])


POLITE_DELAY_SECONDS = 1.5
DEFAULT_TARGET_RECORDS = 40_000
DEFAULT_RAW_PATH = "raw_scrape_progress.jsonl"
DEFAULT_STATE_PATH = "raw_scrape_state.json"
MAX_CONSECUTIVE_DRIVER_RETRIES = 5


def _load_raw_records(raw_path: str) -> list[dict]:
    """Load whatever raw records have been persisted so far (possibly none)."""
    if not os.path.exists(raw_path):
        return []
    with open(raw_path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _append_raw_records(raw_path: str, records: list[dict]) -> None:
    """Append newly fetched records to the raw progress file, one JSON object per line."""
    with open(raw_path, "a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_state(state_path: str) -> dict | None:
    if not os.path.exists(state_path):
        return None
    with open(state_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(state_path: str, next_url: str | None, record_count: int) -> None:
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump({"next_url": next_url, "record_count": record_count}, f)


def scrape_data(
    max_records: int = DEFAULT_TARGET_RECORDS,
    start_url: str = SURVEY_URL,
    raw_path: str = DEFAULT_RAW_PATH,
    state_path: str = DEFAULT_STATE_PATH,
    debugger_address: str = DEBUGGER_ADDRESS,
) -> list[dict]:
    """Scrape applicant entries from The Grad Cafe, one page at a time, until
    `max_records` is reached or the site stops sending a next page.

    Saves progress to `raw_path` and `state_path` after every page, so if
    this gets interrupted (rate limit, Chrome closing, etc.), running it
    again continues from where it stopped instead of starting over. If the
    Chrome tab itself crashes, it reconnects and tries again automatically
    (up to MAX_CONSECUTIVE_DRIVER_RETRIES times) before giving up. Any other
    kind of failure stops the scraper right away instead of retrying.
    """
    if not _robots_allows("/survey/"):
        raise RuntimeError("robots.txt disallows /survey/ -- refusing to scrape.")

    existing = _load_raw_records(raw_path)
    if len(existing) >= max_records:
        print(f"Already have {len(existing)} records (>= target {max_records}); nothing to do.")
        return existing[:max_records]

    state = _load_state(state_path)
    url = state["next_url"] if state else start_url
    total = len(existing)
    print(f"Resuming from {total} saved records." if total else "Starting fresh scrape.")

    driver = _attach_driver(debugger_address)
    consecutive_retries = 0

    try:
        while url and total < max_records:
            if not _is_same_site(url):
                raise RuntimeError(f"Refusing to follow off-site URL: {url}")

            try:
                data = _fetch_page_json(driver, url)
            except WebDriverException as exc:
                consecutive_retries += 1
                if consecutive_retries > MAX_CONSECUTIVE_DRIVER_RETRIES:
                    print(f"Stopping: {consecutive_retries} consecutive Chrome session failures "
                          f"at {url} ({exc}). Progress saved -- rerun to resume.")
                    break
                print(f"Chrome session error at {url} ({exc}); "
                      f"re-attaching (retry {consecutive_retries}/{MAX_CONSECUTIVE_DRIVER_RETRIES}).")
                try:
                    driver.quit()
                except Exception:
                    pass
                time.sleep(POLITE_DELAY_SECONDS)
                driver = _attach_driver(debugger_address)
                continue
            except Exception as exc:
                print(f"Stopping: page fetch failed for {url} ({exc}). Progress saved -- rerun to resume.")
                break

            consecutive_retries = 0
            page_records = data["props"]["results"]["data"]
            _append_raw_records(raw_path, page_records)
            total += len(page_records)
            url = data["props"]["results"]["links"]["next"]
            _save_state(state_path, url, total)
            print(f"Fetched {len(page_records)} records (total: {total}).")

            if total >= max_records or not url:
                break
            time.sleep(POLITE_DELAY_SECONDS)
    finally:
        driver.quit()

    return _load_raw_records(raw_path)[:max_records]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape applicant entries from The Grad Cafe.")
    parser.add_argument("--max-records", type=int, default=DEFAULT_TARGET_RECORDS)
    parser.add_argument("--debugger-address", default=DEBUGGER_ADDRESS)
    parser.add_argument("--raw-path", default=DEFAULT_RAW_PATH)
    parser.add_argument("--state-path", default=DEFAULT_STATE_PATH)
    args = parser.parse_args()

    scrape_data(
        max_records=args.max_records,
        raw_path=args.raw_path,
        state_path=args.state_path,
        debugger_address=args.debugger_address,
    )
