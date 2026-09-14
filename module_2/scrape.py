# -*- coding: utf-8 -*-
"""Grad Cafe scraper: hybrid urllib3 (URL construction) + Selenium-attach (navigation)."""

from __future__ import annotations


def scrape_data():
    """Scrape applicant entries from The Grad Cafe via an attached Chrome session.

    TODO (Phase 2/3): attach to an already-verified Chrome session over the
    remote debugging port, paginate results, and hand each page's HTML to
    BeautifulSoup-based parsing helpers.
    """
    raise NotImplementedError


def _parse_entry(entry_html):
    """Parse a single result entry's HTML into a raw record dict.

    TODO (Phase 3): implement with BeautifulSoup/regex per the target schema.
    """
    raise NotImplementedError


if __name__ == "__main__":
    scrape_data()
