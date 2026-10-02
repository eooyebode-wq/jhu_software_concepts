"""Tests for what gets written to PostgreSQL and how it is read back."""

import pytest

from app import build_analysis

pytestmark = pytest.mark.db

TABLE_COLUMNS = [
    "p_id", "program", "comments", "date_added", "url", "status", "term",
    "us_or_international", "gpa", "gre", "gre_v", "gre_aw", "degree",
    "llm_generated_program", "llm_generated_university",
]
REQUIRED_FIELDS = [
    "p_id", "program", "comments", "date_added", "url", "status", "term",
    "us_or_international", "gpa", "gre", "degree",
]


def count_rows(conn):
    """How many rows are in the applicants table."""
    return conn.execute("SELECT COUNT(*) FROM applicants").fetchone()[0]


def test_table_has_the_module_3_columns(db_conn):
    # Given the applicants table
    # When we read its column names
    rows = db_conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'applicants' ORDER BY ordinal_position"
    ).fetchall()
    # Then they are the Module 3 columns
    assert [row[0] for row in rows] == TABLE_COLUMNS


def test_table_is_empty_before_a_pull(db_conn):
    # Given a fresh test database
    # Then the table has no rows
    assert count_rows(db_conn) == 0


def test_pull_inserts_one_row_per_record(client, db_conn, fake_records):
    # Given an empty table
    # When we pull
    client.post("/pull-data")
    # Then one row exists per scraped record
    assert count_rows(db_conn) == len(fake_records)


def test_inserted_rows_have_required_fields(client, db_conn):
    # Given a completed pull
    client.post("/pull-data")
    # When we look for rows missing a required field
    missing = 0
    for field in REQUIRED_FIELDS:
        missing += db_conn.execute(
            f"SELECT COUNT(*) FROM applicants WHERE {field} IS NULL"
        ).fetchone()[0]
    # Then no required field is null
    assert missing == 0


def test_pulling_the_same_data_twice_creates_no_duplicates(client, db_conn, fake_records):
    # Given a completed pull
    client.post("/pull-data")
    # When the same data is pulled again
    client.post("/pull-data")
    # Then the row count has not changed
    assert count_rows(db_conn) == len(fake_records)


def test_p_id_is_unique_in_the_table(client, db_conn):
    # Given the same data pulled twice
    client.post("/pull-data")
    client.post("/pull-data")
    # When we count ids against distinct ids
    total, distinct = db_conn.execute(
        "SELECT COUNT(p_id), COUNT(DISTINCT p_id) FROM applicants"
    ).fetchone()
    # Then they match
    assert total == distinct


def test_query_function_returns_dict_with_expected_keys(seed_db, database_url):
    # Given a database with data
    seed_db()
    # When we run the query function
    analysis = build_analysis(database_url)
    # Then it returns a dict with a list of questions
    assert isinstance(analysis, dict)
    assert list(analysis) == ["questions"]
    assert len(analysis["questions"]) == 11


def test_each_question_has_the_keys_the_template_uses(seed_db, database_url):
    # Given a database with data
    seed_db()
    # When we look at every question
    questions = build_analysis(database_url)["questions"]
    # Then each has the keys index.html reads
    for item in questions:
        assert {"number", "question", "answers"} <= set(item)
