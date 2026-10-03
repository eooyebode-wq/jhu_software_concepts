"""Answer the Grad Cafe analysis questions with raw SQL through psycopg."""

# This file and orm_queries.py print the same results in the same format on
# purpose, so the two can be compared side by side.
# pylint: disable=duplicate-code

from typing import NamedTuple

import psycopg
from psycopg import sql

from db_config import get_connection
from sql_utils import DEFAULT_LIMIT, clamp_limit

APPLICANTS = sql.Identifier("applicants")

ALLOWED_COLUMNS = frozenset({
    "p_id", "program", "comments", "date_added", "url", "status", "term",
    "us_or_international", "gpa", "gre", "gre_v", "gre_aw", "degree",
    "llm_generated_program", "llm_generated_university",
})

PHD_CS_UNIVERSITIES = (
    ("ILIKE", "%georgetown%"),
    ("ILIKE", "%massachusetts institute of technology%"),
    ("~*", r"\mmit\M"),
    ("ILIKE", "%stanford%"),
    ("ILIKE", "%carnegie mellon%"),
)


class Query(NamedTuple):
    """A composed statement and the values for its placeholders.

    The final LIMIT placeholder is not listed in params. The fetch helpers
    add it after clamping the limit.
    """

    stmt: sql.Composable
    params: tuple


def matching_count_stmt(column):
    """Build a statement that counts rows whose column matches a value.

    Args:
        column: Name of a column in ALLOWED_COLUMNS.

    Returns:
        A composed statement with one value placeholder and one LIMIT
        placeholder.

    Raises:
        ValueError: If column is not a column of the applicants table.
    """
    if column not in ALLOWED_COLUMNS:
        raise ValueError(f"Unknown column: {column!r}")
    return sql.SQL(
        "SELECT COUNT(*) FROM {table} WHERE {column} ILIKE %s LIMIT %s"
    ).format(table=APPLICANTS, column=sql.Identifier(column))


# Q2: percent international among entries with a usable nationality
Q2 = Query(
    sql.SQL(
        """
        SELECT ROUND(
            100.0 * COUNT(*) FILTER (WHERE {nationality} ILIKE %s)
            / NULLIF(COUNT(*), 0), 2)
        FROM {table}
        WHERE {nationality} IS NOT NULL
          AND TRIM({nationality}) <> ''
        LIMIT %s
        """
    ).format(table=APPLICANTS, nationality=sql.Identifier("us_or_international")),
    ("international",),
)

# Q3: average GPA and GRE scores, each over the applicants who report it
Q3 = Query(
    sql.SQL(
        """
        SELECT ROUND(AVG({gpa})::numeric, 2),
               ROUND(AVG({gre})::numeric, 2),
               ROUND(AVG({gre_v})::numeric, 2),
               ROUND(AVG({gre_aw})::numeric, 2)
        FROM {table}
        LIMIT %s
        """
    ).format(
        table=APPLICANTS,
        gpa=sql.Identifier("gpa"),
        gre=sql.Identifier("gre"),
        gre_v=sql.Identifier("gre_v"),
        gre_aw=sql.Identifier("gre_aw"),
    ),
    (),
)

# Q4: average GPA of American applicants for Fall 2026
Q4 = Query(
    sql.SQL(
        """
        SELECT ROUND(AVG({gpa})::numeric, 2)
        FROM {table}
        WHERE {term} ILIKE %s
          AND {nationality} ILIKE %s
          AND {gpa} IS NOT NULL
        LIMIT %s
        """
    ).format(
        table=APPLICANTS,
        gpa=sql.Identifier("gpa"),
        term=sql.Identifier("term"),
        nationality=sql.Identifier("us_or_international"),
    ),
    ("fall 2026", "american"),
)

# Q5: percent of Fall 2025 entries that are acceptances
Q5 = Query(
    sql.SQL(
        """
        SELECT ROUND(
            100.0 * COUNT(*) FILTER (WHERE {status} ILIKE %s)
            / NULLIF(COUNT(*), 0), 2)
        FROM {table}
        WHERE {term} ILIKE %s
        LIMIT %s
        """
    ).format(
        table=APPLICANTS,
        status=sql.Identifier("status"),
        term=sql.Identifier("term"),
    ),
    ("accepted", "fall 2025"),
)

# Q6: average GPA of accepted Fall 2026 applicants
Q6 = Query(
    sql.SQL(
        """
        SELECT ROUND(AVG({gpa})::numeric, 2)
        FROM {table}
        WHERE {term} ILIKE %s
          AND {status} ILIKE %s
          AND {gpa} IS NOT NULL
        LIMIT %s
        """
    ).format(
        table=APPLICANTS,
        gpa=sql.Identifier("gpa"),
        term=sql.Identifier("term"),
        status=sql.Identifier("status"),
    ),
    ("fall 2026", "accepted"),
)

# Q7: Johns Hopkins master's Computer Science entries (original fields)
Q7 = Query(
    sql.SQL(
        """
        SELECT COUNT(*)
        FROM {table}
        WHERE {program} ILIKE %s
          AND ({program} ILIKE %s
               OR {program} ILIKE %s
               OR {program} ILIKE %s)
          AND {degree} ILIKE %s
        LIMIT %s
        """
    ).format(
        table=APPLICANTS,
        program=sql.Identifier("program"),
        degree=sql.Identifier("degree"),
    ),
    (
        "%computer science%",
        "%johns hopkins%",
        "%john hopkins%",
        "%jhu%",
        "master%",
    ),
)


def phd_cs_acceptance_query(program_column, university_column):
    """Build the Q8 and Q9 query for the given program and university columns.

    Args:
        program_column: Column that holds the program text.
        university_column: Column that holds the university text.

    Returns:
        A Query for Fall 2026 PhD Computer Science acceptances at four schools.
    """
    university = sql.Identifier(university_column)
    university_match = sql.SQL(" OR ").join(
        sql.SQL("{column} {operator} %s").format(
            column=university, operator=sql.SQL(operator)
        )
        for operator, _pattern in PHD_CS_UNIVERSITIES
    )
    stmt = sql.SQL(
        """
        SELECT COUNT(*)
        FROM {table}
        WHERE {term} ILIKE %s
          AND {status} ILIKE %s
          AND {degree} ILIKE %s
          AND {program} ILIKE %s
          AND ({university_match})
        LIMIT %s
        """
    ).format(
        table=APPLICANTS,
        term=sql.Identifier("term"),
        status=sql.Identifier("status"),
        degree=sql.Identifier("degree"),
        program=sql.Identifier(program_column),
        university_match=university_match,
    )
    params = ("fall 2026", "accepted", "phd", "%computer science%")
    patterns = tuple(pattern for _operator, pattern in PHD_CS_UNIVERSITIES)
    return Query(stmt, params + patterns)


# Q8: Fall 2026 PhD Computer Science acceptances at four universities,
# using the original program field
Q8 = phd_cs_acceptance_query("program", "program")

# Q9: same as Q8, but using the LLM-generated program and university
Q9 = phd_cs_acceptance_query("llm_generated_program", "llm_generated_university")

# Q10 (my own): average GRE Quantitative for American vs International
Q10 = Query(
    sql.SQL(
        """
        SELECT {nationality},
               COUNT({gre}),
               ROUND(AVG({gre})::numeric, 2)
        FROM {table}
        WHERE ({nationality} ILIKE %s
               OR {nationality} ILIKE %s)
          AND {gre} IS NOT NULL
        GROUP BY {nationality}
        ORDER BY {nationality}
        LIMIT %s
        """
    ).format(
        table=APPLICANTS,
        nationality=sql.Identifier("us_or_international"),
        gre=sql.Identifier("gre"),
    ),
    ("american", "international"),
)

# Q11 (my own): average GPA of accepted vs rejected Fall 2026 applicants
Q11 = Query(
    sql.SQL(
        """
        SELECT {status},
               COUNT({gpa}),
               ROUND(AVG({gpa})::numeric, 2)
        FROM {table}
        WHERE {term} ILIKE %s
          AND ({status} ILIKE %s OR {status} ILIKE %s)
          AND {gpa} IS NOT NULL
        GROUP BY {status}
        ORDER BY {status}
        LIMIT %s
        """
    ).format(
        table=APPLICANTS,
        status=sql.Identifier("status"),
        gpa=sql.Identifier("gpa"),
        term=sql.Identifier("term"),
    ),
    ("fall 2026", "accepted", "rejected"),
)

ALL_QUERIES = [
    matching_count_stmt("term"),
    Q2.stmt, Q3.stmt, Q4.stmt, Q5.stmt, Q6.stmt, Q7.stmt,
    Q8.stmt, Q9.stmt, Q10.stmt, Q11.stmt,
]


def fetch_all(conn, stmt, params=(), limit=DEFAULT_LIMIT):
    """Run a composed statement and give back its rows.

    The statement must end with a LIMIT placeholder. The limit is clamped
    to 1 through MAX_LIMIT before it is bound.

    Args:
        conn: An open psycopg connection.
        stmt: A composed statement.
        params: Values for the statement's placeholders, without the limit.
        limit: The requested row limit.

    Returns:
        A list of row tuples.
    """
    values = (*params, clamp_limit(limit))
    with conn.cursor() as cur:
        cur.execute(stmt, values)
        return cur.fetchall()


def fetch_row(conn, stmt, params=()):
    """Run a statement that returns one row and give that row back."""
    return fetch_all(conn, stmt, params, 1)[0]


def fetch_value(conn, stmt, params=()):
    """Run a statement that returns a single value and give that value back."""
    return fetch_row(conn, stmt, params)[0]


def count_matching(conn, column, value):
    """Count the rows where a column matches a value, ignoring letter case.

    Args:
        conn: An open psycopg connection.
        column: Name of a column in ALLOWED_COLUMNS.
        value: The text to match. It is bound as a parameter, never joined
            into the SQL text.

    Returns:
        The number of matching rows.

    Raises:
        ValueError: If column is not a column of the applicants table.
    """
    return fetch_value(conn, matching_count_stmt(column), (value,))


def show_count(value):
    """Whole number with commas, like 19,290."""
    return f"{int(value):,}"


def show_percent(value):
    """Two decimals and a percent sign, like 50.09%."""
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def show_average(value):
    """Two decimals, like 3.79."""
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def main():  # pylint: disable=too-many-locals
    """Run every query and print the answers."""
    try:
        with get_connection() as conn:
            q1 = count_matching(conn, "term", "fall 2026")
            q2 = fetch_value(conn, *Q2)
            gpa, gre, gre_v, gre_aw = fetch_row(conn, *Q3)
            q4 = fetch_value(conn, *Q4)
            q5 = fetch_value(conn, *Q5)
            q6 = fetch_value(conn, *Q6)
            q7 = fetch_value(conn, *Q7)
            q8 = fetch_value(conn, *Q8)
            q9 = fetch_value(conn, *Q9)
            q10_rows = fetch_all(conn, *Q10)
            q11_rows = fetch_all(conn, *Q11)
    except psycopg.Error as err:
        print(f"Database error: {err}")
        return

    print(f"Q1. Fall 2026 applicant count: {show_count(q1)}")
    print(f"Q2. Percent international: {show_percent(q2)}")
    print("Q3. Averages for applicants who report each score")
    print(f"    Average GPA: {show_average(gpa)}")
    print(f"    Average GRE Quantitative: {show_average(gre)}")
    print(f"    Average GRE Verbal: {show_average(gre_v)}")
    print(f"    Average GRE Analytical Writing: {show_average(gre_aw)}")
    print(f"Q4. Average GPA of American applicants, Fall 2026: {show_average(q4)}")
    print(f"Q5. Fall 2025 acceptance percentage: {show_percent(q5)}")
    print(f"Q6. Average GPA of accepted applicants, Fall 2026: {show_average(q6)}")
    print(f"Q7. Johns Hopkins master's Computer Science entries: {show_count(q7)}")
    print("Q8/Q9. Fall 2026 PhD Computer Science acceptances at Georgetown,")
    print("       MIT, Stanford and Carnegie Mellon")
    print(f"    Original-field count: {show_count(q8)}")
    print(f"    LLM-field count: {show_count(q9)}")
    print(f"    Difference: {q9 - q8:+,}")

    print("Q10. Average GRE Quantitative by nationality")
    for group, how_many, average in q10_rows:
        print(f"    {group}: {show_average(average)} ({show_count(how_many)} applicants)")

    print("Q11. Average GPA by decision, Fall 2026")
    for decision, how_many, average in q11_rows:
        print(f"    {decision}: {show_average(average)} ({show_count(how_many)} applicants)")


if __name__ == "__main__":
    main()
