# -*- coding: utf-8 -*-
"""Grad Cafe scraper: hybrid urllib3 (URL construction) + Selenium-attach (navigation)."""

from __future__ import annotations

import json
import os
import time
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

# Identify honestly. Never spoof a browser UA or another crawler's name
# (e.g. ClaudeBot, which robots.txt explicitly disallows) to route around a
# rule aimed at that identity -- can_fetch() falls back to the "User-agent: *"
# group for any name not otherwise listed, so this is matched correctly.
USER_AGENT = "jhu-software-concepts-module2-scraper"


def _robots_allows(path: str, user_agent: str = USER_AGENT) -> bool:
    """Check thegradcafe.com/robots.txt before fetching `path`.

    Scoped exception: uses the standard-library urllib.robotparser rather
    than urllib3, which has no robots.txt parser of its own (see README).
    """
    rp = robotparser.RobotFileParser()
    rp.set_url(ROBOTS_URL)
    rp.read()
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
    """Attach Selenium to an already-open, human-verified Chrome session.

    Never launches a new browser instance -- Cloudflare blocks a freshly
    launched, Selenium-controlled browser outright. Chrome must already be
    running with --remote-debugging-port and --remote-allow-origins=* (see
    README) and have passed Cloudflare's check in that window.
    """
    options = Options()
    options.debugger_address = debugger_address
    return webdriver.Chrome(options=options)


def _fetch_page_json(driver: webdriver.Chrome, url: str) -> dict:
    """Navigate the trusted session to `url` and return its embedded page data.

    Uses an in-session fetch() rather than driver.page_source: GradCafe is an
    Inertia.js SPA whose initial HTML embeds the page's data as JSON in
    #app[data-page], but React strips that attribute from the live DOM after
    hydration (confirmed: page_source lacked it, an in-session fetch() of the
    same URL did not). BeautifulSoup locates the element; json.loads parses
    the already-extracted attribute string -- no HTML search tool beyond
    BeautifulSoup/stdlib json is used.
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
    """Scrape raw applicant entries from The Grad Cafe via an attached Chrome session.

    Returns a list of raw GradCafe result dicts (one per applicant entry),
    following cursor-based pagination until `max_records` is reached or the
    site stops returning a next page. Stops immediately (no retry) if a page
    fetch fails, treating that as a possible block/rate-limit.

    Resumable: progress is persisted to `raw_path` (one JSON record per line)
    and `state_path` (last-seen pagination cursor) after every page, so if the
    process is rate-limited or Chrome is closed partway through, rerunning
    this function picks up where it left off instead of restarting. Both
    paths are relative by default -- no machine-specific hardcoding.

    A crashed Chrome tab/session (observed in practice during long runs) is
    recovered automatically: a fresh session is re-attached and the same page
    retried, up to MAX_CONSECUTIVE_DRIVER_RETRIES in a row, before giving up.
    This only recovers from Chrome's own instability, not from a site
    block/rate-limit -- any other fetch failure still stops immediately.
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
