# -*- coding: utf-8 -*-
"""Grad Cafe scraper: hybrid urllib3 (URL construction) + Selenium-attach (navigation)."""

from __future__ import annotations

import urllib.robotparser as robotparser

BASE_URL = "https://www.thegradcafe.com"
ROBOTS_URL = f"{BASE_URL}/robots.txt"

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


def scrape_data():
    """Scrape applicant entries from The Grad Cafe via an attached Chrome session.

    TODO (Phase 2/3): attach to an already-verified Chrome session over the
    remote debugging port, paginate results, and hand each page's HTML to
    BeautifulSoup-based parsing helpers.
    """
    if not _robots_allows("/survey/"):
        raise RuntimeError("robots.txt disallows /survey/ -- refusing to scrape.")
    raise NotImplementedError


def _parse_entry(entry_html):
    """Parse a single result entry's HTML into a raw record dict.

    TODO (Phase 3): implement with BeautifulSoup/regex per the target schema.
    """
    raise NotImplementedError


if __name__ == "__main__":
    scrape_data()
