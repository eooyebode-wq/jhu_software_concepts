"""Answer the Grad Cafe analysis questions with raw SQL through psycopg."""

import psycopg

from db_config import get_connection

# Q1: Fall 2026 applicants
Q1_SQL = r"""
SELECT COUNT(*)
FROM applicants
WHERE term ILIKE 'fall 2026';
"""

# Q2: percent international among entries with a usable nationality
Q2_SQL = r"""
SELECT ROUND(
    100.0 * COUNT(*) FILTER (WHERE us_or_international ILIKE 'international')
    / COUNT(*), 2)
FROM applicants
WHERE us_or_international IS NOT NULL
  AND TRIM(us_or_international) <> '';
"""

# Q3: average GPA and GRE scores, each over the applicants who report it
Q3_SQL = r"""
SELECT ROUND(AVG(gpa)::numeric, 2),
       ROUND(AVG(gre)::numeric, 2),
       ROUND(AVG(gre_v)::numeric, 2),
       ROUND(AVG(gre_aw)::numeric, 2)
FROM applicants;
"""

# Q4: average GPA of American applicants for Fall 2026
Q4_SQL = r"""
SELECT ROUND(AVG(gpa)::numeric, 2)
FROM applicants
WHERE term ILIKE 'fall 2026'
  AND us_or_international ILIKE 'american'
  AND gpa IS NOT NULL;
"""

# Q5: percent of Fall 2025 entries that are acceptances
Q5_SQL = r"""
SELECT ROUND(
    100.0 * COUNT(*) FILTER (WHERE status ILIKE 'accepted') / COUNT(*), 2)
FROM applicants
WHERE term ILIKE 'fall 2025';
"""

# Q6: average GPA of accepted Fall 2026 applicants
Q6_SQL = r"""
SELECT ROUND(AVG(gpa)::numeric, 2)
FROM applicants
WHERE term ILIKE 'fall 2026'
  AND status ILIKE 'accepted'
  AND gpa IS NOT NULL;
"""

# Q7: Johns Hopkins master's Computer Science entries (original fields)
Q7_SQL = r"""
SELECT COUNT(*)
FROM applicants
WHERE program ILIKE '%computer science%'
  AND (program ILIKE '%johns hopkins%'
       OR program ILIKE '%john hopkins%'
       OR program ILIKE '%jhu%')
  AND degree ILIKE 'master%';
"""

# Q8: Fall 2026 PhD Computer Science acceptances at four universities,
# using the original program field
Q8_SQL = r"""
SELECT COUNT(*)
FROM applicants
WHERE term ILIKE 'fall 2026'
  AND status ILIKE 'accepted'
  AND degree ILIKE 'phd'
  AND program ILIKE '%computer science%'
  AND (program ILIKE '%georgetown%'
       OR program ILIKE '%massachusetts institute of technology%'
       OR program ~* '\mmit\M'
       OR program ILIKE '%stanford%'
       OR program ILIKE '%carnegie mellon%');
"""

# Q9: same as Q8, but using the LLM-generated program and university
Q9_SQL = r"""
SELECT COUNT(*)
FROM applicants
WHERE term ILIKE 'fall 2026'
  AND status ILIKE 'accepted'
  AND degree ILIKE 'phd'
  AND llm_generated_program ILIKE '%computer science%'
  AND (llm_generated_university ILIKE '%georgetown%'
       OR llm_generated_university ILIKE '%massachusetts institute of technology%'
       OR llm_generated_university ~* '\mmit\M'
       OR llm_generated_university ILIKE '%stanford%'
       OR llm_generated_university ILIKE '%carnegie mellon%');
"""


def fetch_row(conn, sql):
    """Run a query that returns one row and give that row back."""
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()


def fetch_value(conn, sql):
    """Run a query that returns a single value and give that value back."""
    return fetch_row(conn, sql)[0]


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


def main():
    try:
        with get_connection() as conn:
            q1 = fetch_value(conn, Q1_SQL)
            q2 = fetch_value(conn, Q2_SQL)
            gpa, gre, gre_v, gre_aw = fetch_row(conn, Q3_SQL)
            q4 = fetch_value(conn, Q4_SQL)
            q5 = fetch_value(conn, Q5_SQL)
            q6 = fetch_value(conn, Q6_SQL)
            q7 = fetch_value(conn, Q7_SQL)
            q8 = fetch_value(conn, Q8_SQL)
            q9 = fetch_value(conn, Q9_SQL)
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


if __name__ == "__main__":
    main()
