"""Load the cleaned Grad Cafe applicant data into PostgreSQL."""

import json
import sys

import psycopg

from db_config import get_connection

DEFAULT_DATA_FILE = "llm_extend_applicant_data.json"
BATCH_SIZE = 1000

INSERT_SQL = """
INSERT INTO applicants (
    p_id, program, comments, date_added, url, status, term,
    us_or_international, gpa, gre, gre_v, gre_aw, degree,
    llm_generated_program, llm_generated_university
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (p_id) DO NOTHING;
"""

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS applicants (
    p_id integer PRIMARY KEY,
    program text,
    comments text,
    date_added date,
    url text,
    status text,
    term text,
    us_or_international text,
    gpa float,
    gre float,
    gre_v float,
    gre_aw float,
    degree text,
    llm_generated_program text,
    llm_generated_university text
);
"""


def clean_text(value):
    """Return the text stripped of spaces, or None if it is missing or blank."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return text


def to_float(value):
    """Turn a value like "3.40" into a float, or None if it is not a number."""
    text = clean_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_score(value, low, high):
    """Like to_float, but zero and values outside low..high become None.

    The source uses 0 when a score was left blank, and some people enter
    scores on a different scale (old GRE scores, GPAs out of 10), so those
    are treated as missing instead of being averaged in.
    """
    number = to_float(value)
    if number is None or number == 0:
        return None
    if number < low or number > high:
        return None
    return number


def get_p_id(url):
    """Use the entry number at the end of the url as the id."""
    if not url:
        return None
    last_part = url.rstrip("/").split("/")[-1]
    if last_part.isdigit():
        return int(last_part)
    return None


def make_program(program, university):
    """Join program and university into one text value, program first."""
    parts = []
    for piece in (program, university):
        text = clean_text(piece)
        if text is not None:
            parts.append(text)
    if not parts:
        return None
    return ", ".join(parts)


def make_nationality(value):
    """The source uses "0" when there is no classification, so store NULL."""
    text = clean_text(value)
    if text is None or text == "0":
        return None
    return text


def make_row(record):
    """Build one database row (a tuple in column order) from a JSON record.

    Returns None if the record has no usable id.
    """
    p_id = get_p_id(record.get("url"))
    if p_id is None:
        return None

    return (
        p_id,
        make_program(record.get("program"), record.get("university")),
        clean_text(record.get("comments")),
        clean_text(record.get("date_added")),
        clean_text(record.get("url")),
        clean_text(record.get("applicant_status")),
        clean_text(record.get("semester_year")),
        make_nationality(record.get("student_type")),
        to_score(record.get("gpa"), 0, 4.0),
        to_score(record.get("gre_score"), 130, 170),
        to_score(record.get("gre_v_score"), 130, 170),
        to_score(record.get("gre_aw_score"), 0, 6.0),
        clean_text(record.get("degree_type")),
        clean_text(record.get("cleaned_program")),
        clean_text(record.get("cleaned_university")),
    )


def create_table(conn):
    """Create the applicants table if it is not already there."""
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()


def read_records(path):
    """Read the list of applicant records from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def insert_rows(conn, rows):
    """Insert rows into applicants and return how many were really added.

    A row whose p_id is already in the table is skipped, so running the
    loader again does not create duplicates.
    """
    added = 0
    with conn.cursor() as cur:
        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]
            cur.executemany(INSERT_SQL, batch)
            added += cur.rowcount
    conn.commit()
    return added


def main():
    path = DEFAULT_DATA_FILE
    if len(sys.argv) > 1:
        path = sys.argv[1]

    try:
        records = read_records(path)
    except (OSError, json.JSONDecodeError) as err:
        print(f"Could not read {path}: {err}")
        return

    rows = []
    skipped = 0
    for record in records:
        row = make_row(record)
        if row is None:
            skipped += 1
        else:
            rows.append(row)

    try:
        with get_connection() as conn:
            create_table(conn)
            added = insert_rows(conn, rows)
    except psycopg.Error as err:
        print(f"Database error: {err}")
        return

    print(f"Records read: {len(records):,}")
    print(f"Skipped (no usable id): {skipped:,}")
    print(f"Newly added: {added:,}")
    print(f"Already in the table: {len(rows) - added:,}")


if __name__ == "__main__":
    main()
