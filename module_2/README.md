# Module 2 — Grad Cafe Web Scraper

## Approach

_TODO: fill in after Phases 1-5._

## Hybrid scraping workflow (urllib3 + Selenium-attach + BeautifulSoup)

_TODO (Phase 2): why Cloudflare requires attaching to an already-verified Chrome
session rather than launching Selenium directly, and how urllib3 is used for
URL construction/validation alongside it._

## Browser / driver setup

_TODO (Phase 2): Chrome + remote debugging attach instructions._

## robots.txt compliance

Before any scraping, `scrape.py` checks `https://www.thegradcafe.com/robots.txt`
via `_robots_allows()` and refuses to proceed if it's disallowed. This is a
**deliberate, scoped exception** to the "use urllib3 everywhere" rule: `urllib3`
has no robots.txt parser, and adding a third-party one (e.g. `protego`) wasn't
worth the added dependency risk this close to the deadline, so the check uses
the standard library's `urllib.robotparser` instead. Everything else
(URL construction/inspection/management) still uses `urllib3`.

`screenshot.jpg` (in this folder) is a screenshot of
`https://www.thegradcafe.com/robots.txt`, captured directly in a browser as
evidence the file was read before scraping began.

**What the file says:** under `User-agent: *`, the relevant block is
`Allow: /` with only a handful of auth-related paths disallowed
(`/signin`, `/register`, `/forgot-password`, `/reset-password`,
`/confirm-password`, `/verify-email`, `/profile`). The applicant-search pages
this scraper targets (`/survey/...`) are not disallowed for a generic
user-agent, and `_robots_allows()` confirms this programmatically before any
request is made.

The file also has explicit `Disallow: /` entries for a list of named AI
crawlers, including `ClaudeBot` (Anthropic's own crawler), plus a
`Content-Signal: ai-train=no` directive. Those rules are scoped to automated
crawlers that self-identify with those specific user-agent strings; this
scraper identifies honestly as
`jhu-software-concepts-module2-scraper` (see `USER_AGENT` in `scrape.py`) and
is driven through a human-verified Chrome session, not an automated AI
crawler, so it correctly falls back to the `User-agent: *` rules rather than
those entries. It never spoofs another bot's or browser's identity to route
around a rule.

**Known limitation, verified as harmless here:** GradCafe's robots.txt
actually contains *two* separate `User-agent: *` blocks -- the one above, and
a second, later block holding the `/signin`, `/register`, etc. disallow list.
Python's stdlib `urllib.robotparser` has a known quirk where it only parses
the first block for a given user-agent and silently drops the second, so
`rp.can_fetch('*', '/signin')` incorrectly returns `True` even though the raw
file disallows it. This was caught by inspecting `rp.entries` directly rather
than trusting `can_fetch()` blindly. It does not affect this project: the
scraper never requests `/signin` or any of the other paths in that dropped
block, only `/survey/...`, which is correctly allowed under both blocks.

## Setup & run instructions

_TODO: reproduce `applicant_data.json` and `llm_extend_applicant_data.json`
from scratch._

## Data schema

_TODO: field list and the `None`/`""` convention for missing data._

## Cleaning pipeline / canonical list edits

_TODO (Phase 5): changes to `llm_hosting` canonical lists, post-processing
logic, known edge cases._

## Known bugs

_TODO._
