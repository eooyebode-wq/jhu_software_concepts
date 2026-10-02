"""Fetch newly posted Grad Cafe entries and add them to the database.

Run from the command line (or from the Flask page with the Pull Data button).
Chrome must already be open with remote debugging on port 9222, the same
setup as the Module 2 scraper.
"""

import socket
import sys
import time

import psycopg
from selenium.common.exceptions import WebDriverException

import scrape
from clean import clean_data
from db_config import get_connection
from load_data import create_table, load_rows, make_row

# The Module 2 scraper helpers start with an underscore, but they are reused
# here on purpose instead of copying them.
# pylint: disable=protected-access

# Safety limit so a pull can never run forever.
MAX_PAGES = 200

CHROME_MESSAGE = (
    "could not connect to Chrome. Open Chrome with remote debugging on "
    "port 9222 and try again."
)


def chrome_is_open():
    """Check that something is listening on Chrome's debugging port.

    Without this, a missing Chrome takes about a minute to be noticed.

    Returns:
        True if the port accepts a connection, otherwise False.
    """
    host, port = scrape.DEBUGGER_ADDRESS.split(":")
    try:
        with socket.create_connection((host, int(port)), timeout=3):
            return True
    except OSError:
        return False


def get_known_ids(conn):
    """Return the set of p_id values already in the database."""
    with conn.cursor() as cur:
        cur.execute("SELECT p_id FROM applicants")
        return {row[0] for row in cur.fetchall()}


def fetch_new_raw_records(known_ids):
    """Read survey pages newest first and keep the entries we do not have.

    Stops after the first page that has nothing new, since everything after
    it is older.

    Args:
        known_ids: The p_id values already in the database.

    Returns:
        A list of raw Grad Cafe records.

    Raises:
        RuntimeError: If robots.txt forbids scraping or a link leaves the site.
    """
    if not scrape._robots_allows("/survey/"):
        raise RuntimeError("robots.txt does not allow scraping /survey/.")

    driver = scrape._attach_driver()
    new_records = []
    url = scrape.SURVEY_URL
    pages = 0

    try:
        while url and pages < MAX_PAGES:
            if not scrape._is_same_site(url):
                raise RuntimeError(f"Refusing to follow off-site link: {url}")

            data = scrape._fetch_page_json(driver, url)
            page_records = data["props"]["results"]["data"]
            fresh = [r for r in page_records if r.get("id") not in known_ids]
            new_records.extend(fresh)
            pages += 1
            print(f"Page {pages}: {len(fresh)} new of {len(page_records)}", flush=True)

            if not fresh:
                break
            url = data["props"]["results"]["links"]["next"]
            time.sleep(scrape.POLITE_DELAY_SECONDS)
    finally:
        driver.quit()

    return new_records


def scrape_new_records(database_url=None):
    """Scrape the entries that are not in the database yet.

    This is the default scraper used by the Pull Data button.

    Args:
        database_url: Optional URL that replaces DATABASE_URL.

    Returns:
        A list of raw Grad Cafe records.

    Raises:
        RuntimeError: If Chrome is not open on the debugging port.
    """
    if not chrome_is_open():
        raise RuntimeError(CHROME_MESSAGE)

    with get_connection(database_url) as conn:
        create_table(conn)
        known_ids = get_known_ids(conn)
    print(f"Database has {len(known_ids):,} entries.", flush=True)
    return fetch_new_raw_records(known_ids)


def run_pull(scraper, loader):
    """Scrape, clean and load new entries.

    Args:
        scraper: Function with no arguments that returns raw records.
        loader: Function that takes a list of row tuples and returns how many
            were added.

    Returns:
        How many rows the loader added.
    """
    rows = []
    for record in clean_data(scraper()):
        row = make_row(record)
        if row is not None:
            rows.append(row)
    return loader(rows)


def main():
    """Pull new entries. Returns 0 on success and 1 if something went wrong."""
    try:
        added = run_pull(scrape_new_records, load_rows)
    except psycopg.Error as err:
        print(f"ERROR: database problem: {err}")
        return 1
    except WebDriverException:
        print(f"ERROR: {CHROME_MESSAGE}")
        return 1
    except Exception as err:  # pylint: disable=broad-except
        print(f"ERROR: {err}")
        return 1

    print(f"DONE: added {added:,} new entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
