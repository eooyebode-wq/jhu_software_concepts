# -*- coding: utf-8 -*-
"""Grad Cafe scraper: hybrid urllib3 (URL construction) + Selenium-attach (navigation)."""

from __future__ import annotations

import json
import urllib.robotparser as robotparser

from bs4 import BeautifulSoup
from selenium import webdriver
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


def scrape_data():
    """Scrape applicant entries from The Grad Cafe via an attached Chrome session.

    TODO (Phase 3): loop pages via _fetch_page_json()/next cursor, hand each
    record to _parse_entry(), persist progress for resumability, stop
    politely once the target count is reached or the site blocks/rate-limits.
    """
    if not _robots_allows("/survey/"):
        raise RuntimeError("robots.txt disallows /survey/ -- refusing to scrape.")
    raise NotImplementedError


def _parse_entry(record: dict) -> dict:
    """Map one raw GradCafe result record onto the target applicant_data.json schema.

    TODO (Phase 3): field-by-field mapping (program/university/status/dates/
    GRE/GPA/etc.), preserving the raw `program` text untouched.
    """
    raise NotImplementedError


if __name__ == "__main__":
    scrape_data()
