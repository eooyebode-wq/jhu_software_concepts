# Module 3 - Grad Cafe Database, SQL Analysis and Flask App

## Name

Emmanuel Oyebode, JHED ID: eooyebod1

## What this project does

I took the cleaned Grad Cafe data from Module 2 and loaded it into a
PostgreSQL database. Then I answered questions about it two ways: with raw
SQL through `psycopg`, and with SQLAlchemy. The results are shown on a Flask
webpage that has a Pull Data button (gets newly posted entries from Grad Cafe)
and an Update Analysis button (refreshes the results).

## Files

| File | What it does |
|---|---|
| `load_data.py` | Creates the `applicants` table and loads the Module 2 data into it |
| `query_data.py` | Answers questions 1 to 11 with raw SQL and prints the results |
| `models.py` | SQLAlchemy `Applicant` model, plus the engine and session |
| `orm_queries.py` | The same kind of questions written with SQLAlchemy |
| `app.py` | Flask app, with `templates/` and `static/style.css` |
| `pull_data.py` | Fetches new Grad Cafe entries and adds them to the database |
| `db_config.py` | Reads the database settings from environment variables |
| `scrape.py`, `clean.py` | Module 2 scraper and cleaning code, reused by Pull Data |
| `llm_extend_applicant_data.json` | The cleaned Module 2 data that gets loaded |
| `query_results.pdf` | My write-up of all 11 SQL questions |
| `limitations.pdf` | My reflection on the limits of Grad Cafe data |

`llm_hosting/` and `applicant_data.json` are left over from Module 2. They
aren't needed to run anything in this module.

## Setup

1. Install PostgreSQL. I used Postgres.app (postgresapp.com), which is free.
   Open it and click Initialize so the server is running on port 5432.
2. Install the Python packages (Python 3.10 or newer):
   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Create the database:
   ```bash
   createdb gradcafe
   ```

### Database settings

The scripts read their connection settings from environment variables, so no
password or other secret is stored in the code. They all have defaults that
work with a normal local Postgres.app install, so on my computer I don't set
anything.

| Variable | Default |
|---|---|
| `DB_HOST` | `localhost` |
| `DB_PORT` | `5432` |
| `DB_NAME` | `gradcafe` |
| `DB_USER` | not set (uses your computer username) |
| `DB_PASSWORD` | not set |

For a different setup, set them before running, for example
`export DB_USER=myname`. They only last for that terminal window.

## Loading the data

```bash
python load_data.py
```

This creates the `applicants` table if it isn't there yet and inserts every
record from `llm_extend_applicant_data.json`. To load a different file, put
its name after the script. It prints how many records it read, how many were
new, and how many were already in the table.

It is safe to run more than once. `p_id` is the primary key (the number at the
end of each Grad Cafe entry link), and the insert uses
`ON CONFLICT (p_id) DO NOTHING`, so an entry that is already there is skipped
instead of duplicated.

### How I cleaned the data before loading it

My first averages were way off (GRE Quantitative came out around 21) because
Grad Cafe stores `0` when someone leaves a score blank, and those zeros got
averaged in. I fixed it in `load_data.py` so every query sees the same clean
data.

- A score of `0` is stored as `NULL`.
- Out-of-range scores are also stored as `NULL`: GPA above 4.0, GRE Verbal or
  Quantitative outside 130 to 170, and Analytical Writing above 6.0. Many
  people used old GRE scales or a 10-point GPA.
- Nationality `'0'` is stored as `NULL` too.
- The `program` column holds the program and the university together, like
  `Computer Science, Johns Hopkins University`.

`AVG` ignores `NULL`, so each average only counts applicants who gave that
score. An applicant with a GPA but no GRE still counts toward the GPA average.

## Running the SQL queries

```bash
python query_data.py
```

This prints the answers to questions 1 to 9 from the assignment plus my two
own questions (10 and 11). All the SQL is written out in the file. My
explanations of each query are in `query_results.pdf`.

Output follows the required formats: counts are whole numbers with commas
(`33,212`), percentages have 2 decimals and a `%` sign (`47.13%`), and
averages have 2 decimals (`3.76`).

My two questions:

- **Question 10:** Do international applicants report a higher average GRE
  Quantitative score than American applicants?
- **Question 11:** For Fall 2026, is the average GPA of accepted applicants
  higher than the average GPA of rejected applicants?

The numbers change a little whenever new entries are pulled in.
`query_results.pdf` shows the data after my first Pull Data run, which added 7
new entries to the original 40,000 (so 40,007 entries). The screenshots were
taken at that same point. Pulling more data will make the numbers on the page
a bit different from the PDF.

## Running the SQLAlchemy queries

```bash
python orm_queries.py
```

This repeats questions 1, 4, 5, 8, 9 and my question 11 using SQLAlchemy. The
`Applicant` model in `models.py` maps to the same `applicants` table that
`load_data.py` creates, so there is no second copy of the data and the
program never calls `create_all`. The answers match the raw SQL ones.

## SQL vs. SQLAlchemy: Question 4 (average GPA of American applicants, Fall 2026)

Raw SQL (`query_data.py`):

```sql
SELECT ROUND(AVG(gpa)::numeric, 2)
FROM applicants
WHERE term ILIKE 'fall 2026'
  AND us_or_international ILIKE 'american'
  AND gpa IS NOT NULL;
```

SQLAlchemy (`orm_queries.py`):

```python
stmt = select(rounded_avg(Applicant.gpa)).where(
    and_(
        Applicant.term.ilike("fall 2026"),
        Applicant.us_or_international.ilike("american"),
        Applicant.gpa.is_not(None),
    )
)
return session.execute(stmt).scalar_one()
```

The SQL version is shorter and reads almost like a sentence, and I could paste
it straight into psql to test it. The SQLAlchemy version needs more Python,
but it uses the `Applicant` model, so a typo in a column name like
`Applicant.gpaa` gives an error right away, and the same model can be reused
in the Flask app. It also let me write the Q8 and Q9 filters once in a
function and pass in different columns, where in SQL I had to copy the whole
query. On the other hand, with SQL I know exactly what is running on the
database, and with SQLAlchemy I had to print the compiled query to see what
was really being sent. Some things like the regex match for MIT also took
extra digging to figure out in SQLAlchemy. So I'd use plain SQL for quick
one-off questions and the ORM when the queries are part of a bigger Python
app.

`rounded_avg` is a small helper I wrote that does `ROUND(AVG(...)::numeric, 2)`
inside the query. At first I rounded in Python, and one average came out a
cent off from the SQL version because Python and PostgreSQL round exact halves
differently, so I moved the rounding into the query.

## Running the Flask app

```bash
python app.py
```

Then open http://127.0.0.1:8080. The page runs the SQLAlchemy queries every
time it loads and shows all 11 questions, with my two marked as "My question".

### Pull Data

Pull Data checks Grad Cafe for newly submitted application results and adds
new records to the database. It runs `pull_data.py` in a separate process, so
the page keeps working while it runs. Only one pull can run at a time. If you
click it again while one is running, the page tells you instead of starting
another. While a pull is running the page checks again every 10 seconds, and
shows a message when it finishes (how many entries were added, or what went
wrong).

How it works:

- It reuses the Module 2 code: `scrape.py` to get the pages, `clean.py` to
  clean the records, and `load_data.py` to insert them.
- It reads pages from newest to oldest and stops after the first page with
  nothing new. Entries already in the database are never changed.
- Chrome has to be open with remote debugging on port 9222 first, the same way
  as in Module 2 (see below). If it isn't, the page says so.
- Newly pulled entries have empty `llm_generated_program` and
  `llm_generated_university` columns, because the LLM step from Module 2 needs
  a large local model that isn't part of this project. Question 9 only counts
  entries that have those fields.

You can also run it without the webpage: `python pull_data.py`.

### Update Analysis

The Update Analysis button (top right) only reads the database again and shows
the newest results. It never starts a scrape. If a pull is running, it tells
you new data is being retrieved and leaves the pull alone.

Run the app as one process (`python app.py`). The check for a running pull is
kept in memory, so it wouldn't work with several copies of the app running.

## Chrome setup for the scraper

Chrome has to already be running before you use Pull Data:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="/tmp/gradcafe-chrome-profile" \
  --remote-allow-origins="*"
```

In that Chrome window, go to `https://www.thegradcafe.com/survey/` and get
past Cloudflare's check if it shows up. The Grad Cafe blocks browsers that
Selenium opens on its own and plain requests, so Selenium connects to this
Chrome window instead. Keep that window open while you use Pull Data. Use a
different terminal window for `python app.py`, because the Chrome command
keeps its window busy.

`scrape.py` checks `https://www.thegradcafe.com/robots.txt` before scraping.
I changed that check for this module. Python's built-in robots reader gets a
403 error from the site with its default user agent and treats that as
"everything is disallowed," so `_robots_allows()` now downloads the file with
the scraper's own user agent and gives the text to the parser. The `/survey/`
pages are allowed by the file. `screenshot.jpg` is the robots.txt screenshot
from Module 2.

## Screenshots

- `screenshots/SQL Console Output.png`: output of `python query_data.py`
- `screenshots/ORM Console Output.png`: output of `python orm_queries.py`
- `screenshots/Flask Page.png`: the running Flask page

## Known limitations

- Pulled entries don't have the LLM program and university fields (see above).
- Pull Data needs Chrome open and past the Cloudflare check.
- `limitations.pdf` explains why the results can't be treated as a picture of
  all applicants: the data is anonymous and self-reported, lots of values are
  missing, and the people who post aren't a random sample.
