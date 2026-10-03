"""Tests that injection-style input and bad limits cannot hurt the database."""

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import event

import orm_queries
import query_data
from app import build_analysis
from models import get_engine
from sql_utils import DEFAULT_LIMIT, MAX_LIMIT, clamp_limit

pytestmark = pytest.mark.db

ATTACKS = [
    "' or 1=1 --",
    "'; select true; --",
    "'; UPDATE applicants SET status = 'Accepted'; select true; --",
    "'; DROP TABLE applicants; --",
    "fall 2026' OR '1'='1",
]


@pytest.fixture
def conn(database_url):
    """A connection like the query script opens."""
    with psycopg.connect(database_url) as connection:
        yield connection


def table_snapshot(db_conn):
    """Every row of the applicants table, for before and after checks."""
    return db_conn.execute("SELECT * FROM applicants ORDER BY p_id").fetchall()


@pytest.mark.parametrize("attack", ATTACKS)
def test_attack_text_is_treated_as_a_plain_value(conn, db_conn, seed_db, attack):
    # Given seeded data
    seed_db()
    before = table_snapshot(db_conn)
    # When the attack text is used as the value to look for
    found = query_data.count_matching(conn, "term", attack)
    # Then nothing matches, nothing is returned for free, and nothing changed
    assert found == 0
    assert table_snapshot(db_conn) == before


@pytest.mark.parametrize("attack", ATTACKS)
def test_attack_text_in_the_column_name_is_refused(conn, db_conn, seed_db, attack):
    # Given seeded data
    seed_db()
    before = table_snapshot(db_conn)
    # When the attack text is used as the column name
    with pytest.raises(ValueError):
        query_data.count_matching(conn, attack, "fall 2026")
    # Then it is refused and the table is untouched
    assert table_snapshot(db_conn) == before


def test_a_normal_value_still_finds_its_rows(conn, seed_db):
    # Given the seven fake entries
    seed_db()
    # When we count Fall 2026 entries, in any letter case
    # Then the four real ones are found
    assert query_data.count_matching(conn, "term", "FALL 2026") == 4
    assert isinstance(query_data.count_matching(conn, "term", "fall 2026"), int)


@pytest.mark.parametrize(
    ("asked", "expected"),
    [
        (5, 5),
        ("7", 7),
        (1, 1),
        (MAX_LIMIT, MAX_LIMIT),
        (MAX_LIMIT + 1, MAX_LIMIT),
        (10**9, MAX_LIMIT),
        (0, 1),
        (-5, 1),
        ("abc", DEFAULT_LIMIT),
        ("1; DROP TABLE applicants", DEFAULT_LIMIT),
        (None, DEFAULT_LIMIT),
        (float("nan"), DEFAULT_LIMIT),
        (float("inf"), DEFAULT_LIMIT),
        ([3], DEFAULT_LIMIT),
    ],
)
def test_clamp_limit_keeps_every_input_between_one_and_the_maximum(asked, expected):
    assert clamp_limit(asked) == expected
    assert 1 <= clamp_limit(asked) <= MAX_LIMIT


@pytest.mark.parametrize("asked", [10**9, -1, 0, "abc", None])
def test_fetch_all_never_returns_more_than_the_maximum(conn, db_conn, asked):
    # Given more rows than the maximum
    db_conn.execute(
        "INSERT INTO applicants (p_id) SELECT g FROM generate_series(1, 250) AS g"
    )
    stmt = sql.SQL("SELECT p_id FROM {table} ORDER BY p_id LIMIT %s").format(
        table=sql.Identifier("applicants")
    )
    # When a caller asks for an odd number of rows
    rows = query_data.fetch_all(conn, stmt, (), asked)
    # Then between one row and the maximum come back
    assert 1 <= len(rows) <= MAX_LIMIT


def test_every_raw_query_has_a_limit(conn):
    for stmt in query_data.ALL_QUERIES:
        text = stmt.as_string(conn)
        assert "LIMIT" in text.upper()


def test_every_query_the_page_runs_has_a_limit(database_url, seed_db):
    # Given the ORM engine, with a listener that records every statement sent
    seed_db()
    sent = []
    engine = get_engine(database_url)

    def record(_conn, _cursor, statement, *_rest):
        sent.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        # When the analysis page builds its answers
        build_analysis(database_url)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    # Then each SELECT carries a LIMIT
    selects = [text for text in sent if text.lstrip().upper().startswith("SELECT")]
    assert selects
    assert all("LIMIT" in text.upper() for text in selects)


def test_orm_helpers_still_answer_with_a_limit(database_url, seed_db):
    # Given seeded data
    seed_db()
    # When the grouped ORM queries run
    with orm_queries.get_session(database_url) as session:
        by_nationality = orm_queries.gre_by_nationality(session)
        by_decision = orm_queries.gpa_by_decision(session)
    # Then they return their small result sets
    assert len(by_nationality) == 2
    assert len(by_decision) == 2
