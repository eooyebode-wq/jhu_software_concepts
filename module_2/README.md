# Module 2 — Grad Cafe Web Scraper

## Approach

For this project I scraped admissions results from The Grad Cafe, turned
them into a clean JSON file, and then ran them through a small local AI
model to standardize the school and program names.

There are two main scripts:

- **`scrape.py`** — gets the data from The Grad Cafe and saves it.
- **`clean.py`** — takes what was scraped, puts it into a consistent format
  (`applicant_data.json`), and runs the local AI model on it to produce
  `llm_extend_applicant_data.json`.

Both scripts can be run from the command line and pick up where they left
off if they get interrupted, so nothing has to restart from scratch. I
didn't hardcode any file paths that only work on my own computer.

The sections below explain the trickier parts: why I couldn't just scrape
the site normally, how I checked robots.txt, how to run everything, and
what I found while cleaning the data.

## Hybrid scraping workflow (urllib3 + Selenium-attach + BeautifulSoup)

The Grad Cafe is protected by Cloudflare, which blocks two things I tried
at first: a Selenium browser that launches itself (Cloudflare can tell it's
a bot), and plain `urllib3` requests (these just get a 403 error).

The workaround that actually works:

1. I open Chrome myself, with remote debugging turned on, and pass
   Cloudflare's check once, like a normal person visiting the site.
2. Selenium then **connects to that already-open browser** instead of
   opening its own. Since Cloudflare already trusts this browser window,
   Selenium gets to use that trust too.
3. `urllib3` is used to build and check the page URLs before visiting them.
4. Selenium tells the browser to go to each page.
5. To grab the page's data, I don't use Selenium's normal
   `driver.page_source` — I explain why below.
6. BeautifulSoup finds the spot in the page's HTML where the data lives,
   and Python's built-in `json` module reads it.
7. `clean.py` turns that into the final format.

**Why not `driver.page_source`?** The Grad Cafe website loads its results
as a chunk of JSON text hidden inside the page's HTML. But once the page
finishes loading in the browser, the site's own JavaScript code removes
that JSON from the page. So if I ask Selenium for the current page HTML
(`page_source`), the data is already gone by the time I look — I checked,
and it was missing. Instead, I have the browser re-fetch the same page's
raw HTML using `fetch()`, which still has the JSON in it. This is still
going through the same trusted, already-logged-in browser — I'm just
grabbing the page a different way.

**Pagination** works through a "cursor" link instead of page numbers —
each page tells me the web address of the next page. I just keep following
that link until I have enough records.

## Browser / driver setup

I used Chrome with ChromeDriver, connected through Selenium's "attach to an
existing browser" feature instead of having Selenium open its own browser.
Chrome has to already be running before you start the scraper:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/gradcafe-chrome-profile" \
  --remote-allow-origins="*"
```

The `--remote-allow-origins` flag is needed on newer versions of Chrome, or
it refuses the connection from Selenium. `--user-data-dir` just points
Chrome to a separate, temporary profile folder so it doesn't touch your
normal Chrome data.

Once Chrome is open and past any Cloudflare check, `scrape.py` connects to
it like this:

```python
options = Options()
options.debugger_address = "127.0.0.1:9222"
driver = webdriver.Chrome(options=options)
```

ChromeDriver itself gets downloaded automatically by Selenium — no need to
install or match a driver version by hand.

## robots.txt compliance

Before scraping anything, `scrape.py` checks
`https://www.thegradcafe.com/robots.txt` (function `_robots_allows()`) and
stops if scraping isn't allowed. I used Python's built-in
`urllib.robotparser` for this one check instead of `urllib3`, since
`urllib3` doesn't have a robots.txt reader built in and I didn't want to
add an extra library just for that. Everything else still uses `urllib3`.

`screenshot.jpg` in this folder is a screenshot of the robots.txt page,
taken as proof I actually looked at it before scraping.

The file allows scraping for general visitors (`Allow: /`) and only blocks
a few login/account pages, which I never touch. The search-result pages I
actually scrape are allowed.

One thing worth mentioning: while testing, I found that Python's
robots.txt reader silently ignores a second set of rules further down in
the file (a bug in the library itself, not something I did). It doesn't
end up mattering here, since the pages I scrape are allowed either way —
but I only know that because I double-checked by hand instead of trusting
the library's answer.

## Setup & run instructions

1. Create a virtual environment and install everything:
   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Open Chrome with remote debugging on (see command above), go to
   `https://www.thegradcafe.com/survey/`, and get past Cloudflare's check
   if it shows up.
3. Run the scraper:
   ```bash
   python scrape.py --max-records 40000
   ```
   If this gets interrupted, running the same command again picks up
   where it left off instead of starting over.
4. Turn the raw data into the final format:
   ```bash
   python clean.py --out-path applicant_data.json
   ```
5. Run the local AI cleaning pass:
   ```bash
   python clean.py --skip-structuring --llm-extend \
     --in-path applicant_data.json \
     --llm-out-path llm_extend_applicant_data.json
   ```

I didn't parallelize the scraping step itself — each page's address only
becomes known after loading the page before it, so there's no clean way to
split the work across multiple workers anyway. The AI cleaning step (next
section) is where parallelizing actually helps, since that part doesn't
depend on the website at all.

## Data schema

Every record in `applicant_data.json` has the same 15 fields. If a value
wasn't available, it's set to `null` — fields are never left out.

| Field | Where it comes from | Notes |
|---|---|---|
| `program` | Grad Cafe's program field | Kept exactly as-is |
| `university` | Grad Cafe's school field | Kept exactly as-is |
| `comments` | Grad Cafe's notes field | Cleaned up stray HTML, nothing else changed |
| `date_added` | When the entry was posted | |
| `url` | Built from the entry's ID | Link to the entry on The Grad Cafe |
| `applicant_status` | Accepted / Rejected / Wait listed / Interview / Other | |
| `acceptance_date` | Only filled in if accepted | |
| `rejection_date` | Only filled in if rejected | |
| `semester_year` | e.g. "Spring 2027" | |
| `student_type` | International / American | |
| `gre_score` | | |
| `gre_v_score` | | |
| `gre_aw_score` | | |
| `degree_type` | e.g. "PhD", "MFA" | Kept as Grad Cafe wrote it, not squeezed into just "Masters"/"PhD" |
| `gpa` | | |

Good news: Grad Cafe already lists the program and university as two
separate fields, so I didn't have to split one messy combined string like
older versions of this assignment expected. That made this part easier and
less error-prone.

## Cleaning pipeline / canonical list edits

To standardize program and university names, I fed each record's
program/university into `llm_hosting/app.py` (the small local AI model
provided for this assignment) using its command-line mode, exactly as it
was given to me — I didn't change how it works internally. It already does
its own cleanup (fixing abbreviations, matching against a list of known
university/program names), so I didn't build a second cleanup step on top
of it.

Since running the AI model on 40,000 rows one at a time would take way too
long, I ran it as two processes at the same time, splitting the work in
half. I tested a few different setups first (more workers wasn't always
faster — the model already uses most of the computer's processing power on
its own), and two workers turned out to be the fastest option. The full run
took about 5.5 hours.

**A mistake I found and fixed:** while checking the results, I noticed
several records where "University of Michigan" had been incorrectly
relabeled as "University of Milan" — a completely different school. This
happened because the list of official university names
(`canon_universities.txt`) only had "University of Michigan, Ann Arbor,"
not the plain "University of Michigan," so the matching step picked the
closest name it *did* have — and "Milan" happened to be a closer text
match than "Michigan, Ann Arbor," even though it's obviously the wrong
answer. I added "University of Michigan" to the list of official names,
which fixed all 377 records that had this problem.

I also tried a bigger fix — automatically comparing every cleaned result
against the original text and "fixing" anything that looked too different.
This caught a couple more real mistakes, but it also broke things that were
actually correct, like changing "New York University" back into "Nyu." A
name that's supposed to be expanded (like an abbreviation) is *supposed* to
look different from the original, so that approach wasn't reliable. I
undid this change and only kept the specific, confirmed fix above.

Some imperfect results are still in the data and I didn't try to fix them
by hand, since there are too many to check one by one:

- The AI model sometimes introduces small typos of its own, like turning
  "Religion" into "Religiion."
- It sometimes drops part of a longer name, like shortening "Civil,
  Construction, Environmental Engineering" down to just "Civil."
- Other name-matching mistakes similar to the Michigan/Milan one probably
  exist elsewhere in the data, since the list of official names is over
  1,000 entries long and I could only check a sample by hand.

## Known bugs

- While running the full scrape, the Chrome tab crashed 5 separate times
  over the course of the run (not because the website blocked me — just
  Chrome itself becoming unstable after hours of continuous use). I added
  code so that if this happens, the scraper automatically reopens a
  connection to Chrome and keeps going from where it stopped, instead of
  needing to be restarted by hand. This worked without any problems for
  the rest of the run.
