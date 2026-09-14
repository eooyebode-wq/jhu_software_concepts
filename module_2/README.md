# Module 2 — Grad Cafe Web Scraper

## Approach

_TODO: fill in after Phases 1-5._

## Hybrid scraping workflow (urllib3 + Selenium-attach + BeautifulSoup)

GradCafe is behind Cloudflare, which blocks both a freshly-launched,
Selenium-controlled browser (bot-fingerprint detection) and plain
`urllib3`/`requests` calls (HTTP 403). The working pattern:

1. Launch Chrome manually with remote debugging enabled and complete
   Cloudflare's check once, as a human, in that window.
2. Selenium **attaches** to that already-open, already-verified browser via
   `debugger_address` (never launches its own browser instance).
3. `urllib3` constructs/inspects/validates target URLs before navigation.
4. Selenium's `driver.get()` navigates the trusted session to each page.
5. The rendered result data is extracted via an **in-session `fetch()`** of
   the same URL, not `driver.page_source` -- see below for why.
6. BeautifulSoup locates the `#app[data-page]` element on that fetched HTML;
   its `data-page` attribute is standard-library `json.loads()`'d directly
   into structured record dicts.
7. Records are cleaned/structured into the target JSON schema (`clean.py`).

**Why `fetch()` instead of `page_source` (a deliberate deviation from the
"extract via page_source" suggestion):** GradCafe is a Laravel + Inertia.js
single-page app. The *initial* HTML response for any `/survey...` URL embeds
the full page's data as JSON in a `data-page` attribute on `#app` -- but
after React hydrates the page client-side, it strips that attribute from the
live DOM. Tested directly: on the same loaded page, `driver.page_source`
(148KB) had no `data-page` attribute, while `driver.execute_script("return
fetch(window.location.href).then(r => r.text())")` (198KB, same trusted
session, same cookies, no bypass) did. Using `page_source` as suggested would
have forced fragile scraping of the rendered visible table instead of the
much more reliable structured JSON GradCafe already serves server-side, so
`fetch()`-from-session was used instead. Selenium is still doing the actual
page loading/navigation/session work -- this only changes *how the resulting
HTML is captured*, not the trust boundary.

**Pagination** is cursor-based, not `?page=N`: each page's JSON includes
`results.links.next`, a full URL with an opaque cursor token, which becomes
the next `driver.get()` target. Confirmed working across multiple consecutive
pages with no duplicate/skipped records.

## Browser / driver setup

Chrome + ChromeDriver, via Selenium's remote-debugging attach (not
Selenium-launch). Chrome must be started manually first:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/gradcafe-chrome-profile" \
  --remote-allow-origins=*
```

`--remote-allow-origins=*` is required on modern Chrome (111+); without it,
Chrome's DevTools Protocol rejects the WebSocket connection from ChromeDriver
with a "chrome not reachable" error even though the debugging port itself
responds to plain HTTP requests. `--user-data-dir` points at a dedicated,
disposable profile directory (not the user's real Chrome profile), so the
verified session persists across runs without touching personal data.

After completing Cloudflare's check (if shown) in that window, `scrape.py`
attaches via:

```python
options = Options()
options.debugger_address = "127.0.0.1:9222"
driver = webdriver.Chrome(options=options)
```

ChromeDriver itself is resolved automatically by Selenium Manager
(bundled with Selenium 4.6+) -- no separate driver download/pinning needed.

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

Every record in `applicant_data.json` has the same 15 keys; a value that
wasn't available in the source is always `null` (Python `None`) -- keys are
never omitted, and no other placeholder (e.g. empty string) is used.

| Key | Source (raw GradCafe field) | Notes |
|---|---|---|
| `program` | `program` | Raw/traceability field, never altered |
| `university` | `school` | Raw, never altered |
| `comments` | `notes` | HTML entities/tags stripped (`html.unescape` + tag regex); content otherwise untouched |
| `date_added` | `created_at` | Date the entry was added to GradCafe |
| `url` | built from `id` | Permalink, e.g. `https://www.thegradcafe.com/result/1020483` |
| `applicant_status` | `decision` | Normalized to one of `Accepted`/`Rejected`/`Wait listed`/`Interview`/`Other` |
| `acceptance_date` | `acceptedDate` | Only set when `applicant_status == "Accepted"` |
| `rejection_date` | `rejectedDate` | Only set when `applicant_status == "Rejected"` |
| `semester_year` | `season` | e.g. `"Spring 2027"` |
| `student_type` | `status` | International/American. Note: GradCafe's own `status` field means nationality, not decision -- renamed here to avoid that ambiguity |
| `gre_score` | `greq` | |
| `gre_v_score` | `grev` | |
| `gre_aw_score` | `grew` | |
| `degree_type` | `level` | Kept as GradCafe provides it (e.g. `"MFA"`, `"PhD"`), not force-bucketed into just Masters/PhD -- collapsing e.g. "MFA" into "Masters" would fabricate a categorization the source doesn't state |
| `gpa` | `ugpa` | |

**`program` and `university` are already separate fields at the source** --
GradCafe's site (a Laravel + Inertia SPA) never mixes them into one string the
way older/manual scraping approaches would need to split. Both schools and
programs appear to be selected from an autocomplete tied to internal IDs
(`school_id`, `program_id` in the raw data), so naming is likely more
consistent for recent entries than the classic "JHU vs Johns Hopkins vs John
Hopkins" variance the assignment's cleaning section describes -- though older
or unusual entries can still vary, which is exactly what the local-LLM
standardization pass (see below) is for. Real-world messiness is still
present, e.g. one observed entry's `school` was a joke/troll value
(`"University of Toronto (Pissmaster)"`) -- preserved as-is, since we don't
get to "fix" what a user actually typed.

## Cleaning pipeline / canonical list edits

_TODO (Phase 5): changes to `llm_hosting` canonical lists, post-processing
logic, known edge cases._

## Known bugs

_TODO._
