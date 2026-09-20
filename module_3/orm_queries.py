"""Answer some of the analysis questions again, using SQLAlchemy instead of SQL."""

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from models import Applicant, Session


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


def fall_2026_count(session):
    """Q1: how many entries are for Fall 2026."""
    stmt = (
        select(func.count())
        .select_from(Applicant)
        .where(Applicant.term.ilike("fall 2026"))
    )
    return session.execute(stmt).scalar_one()


def american_fall_2026_gpa(session):
    """Q4: average GPA of American applicants for Fall 2026."""
    stmt = select(func.avg(Applicant.gpa)).where(
        and_(
            Applicant.term.ilike("fall 2026"),
            Applicant.us_or_international.ilike("american"),
            Applicant.gpa.is_not(None),
        )
    )
    return session.execute(stmt).scalar_one()


def fall_2025_acceptance_percent(session):
    """Q5: percent of Fall 2025 entries that are acceptances."""
    accepted = func.count().filter(Applicant.status.ilike("accepted"))
    stmt = select(100.0 * accepted / func.nullif(func.count(), 0)).where(
        Applicant.term.ilike("fall 2025")
    )
    return session.execute(stmt).scalar_one()


def phd_cs_acceptance_count(session, program_column, university_column):
    """Q8 and Q9: Fall 2026 PhD Computer Science acceptances at four schools.

    The program and university columns are passed in, so the same function
    works for the original fields (Q8) and the LLM-generated fields (Q9).
    """
    university_match = or_(
        university_column.ilike("%georgetown%"),
        university_column.ilike("%massachusetts institute of technology%"),
        university_column.regexp_match(r"\mmit\M", flags="i"),
        university_column.ilike("%stanford%"),
        university_column.ilike("%carnegie mellon%"),
    )
    stmt = (
        select(func.count())
        .select_from(Applicant)
        .where(
            and_(
                Applicant.term.ilike("fall 2026"),
                Applicant.status.ilike("accepted"),
                Applicant.degree.ilike("phd"),
                program_column.ilike("%computer science%"),
                university_match,
            )
        )
    )
    return session.execute(stmt).scalar_one()


def gpa_by_decision(session):
    """Q11: average GPA of accepted vs rejected Fall 2026 applicants."""
    stmt = (
        select(Applicant.status, func.count(Applicant.gpa), func.avg(Applicant.gpa))
        .where(
            and_(
                Applicant.term.ilike("fall 2026"),
                or_(
                    Applicant.status.ilike("accepted"),
                    Applicant.status.ilike("rejected"),
                ),
                Applicant.gpa.is_not(None),
            )
        )
        .group_by(Applicant.status)
        .order_by(Applicant.status)
    )
    return session.execute(stmt).all()


def main():
    try:
        with Session() as session:
            q1 = fall_2026_count(session)
            q4 = american_fall_2026_gpa(session)
            q5 = fall_2025_acceptance_percent(session)
            q8 = phd_cs_acceptance_count(
                session, Applicant.program, Applicant.program
            )
            q9 = phd_cs_acceptance_count(
                session,
                Applicant.llm_generated_program,
                Applicant.llm_generated_university,
            )
            q11_rows = gpa_by_decision(session)
    except SQLAlchemyError as err:
        print(f"Database error: {err}")
        return

    print("SQLAlchemy results")
    print(f"Q1. Fall 2026 applicant count: {show_count(q1)}")
    print(f"Q4. Average GPA of American applicants, Fall 2026: {show_average(q4)}")
    print(f"Q5. Fall 2025 acceptance percentage: {show_percent(q5)}")
    print("Q8/Q9. Fall 2026 PhD Computer Science acceptances at Georgetown,")
    print("       MIT, Stanford and Carnegie Mellon")
    print(f"    Original-field count: {show_count(q8)}")
    print(f"    LLM-field count: {show_count(q9)}")
    print(f"    Difference: {q9 - q8:+,}")
    print("Q11. Average GPA by decision, Fall 2026")
    for decision, how_many, average in q11_rows:
        print(f"    {decision}: {show_average(average)} ({show_count(how_many)} applicants)")


if __name__ == "__main__":
    main()
