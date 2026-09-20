"""Flask page that shows the Grad Cafe analysis results."""

from flask import Flask, render_template
from sqlalchemy.exc import SQLAlchemyError

import orm_queries as oq
from models import Applicant, Session

app = Flask(__name__)


def build_questions():
    """Ask the database every question and return the answers as text."""
    with Session() as session:
        q1 = oq.fall_2026_count(session)
        q2 = oq.international_percent(session)
        gpa, gre, gre_v, gre_aw = oq.average_scores(session)
        q4 = oq.american_fall_2026_gpa(session)
        q5 = oq.fall_2025_acceptance_percent(session)
        q6 = oq.accepted_fall_2026_gpa(session)
        q7 = oq.jhu_masters_cs_count(session)
        q8 = oq.phd_cs_acceptance_count(session, Applicant.program, Applicant.program)
        q9 = oq.phd_cs_acceptance_count(
            session,
            Applicant.llm_generated_program,
            Applicant.llm_generated_university,
        )
        q10_rows = oq.gre_by_nationality(session)
        q11_rows = oq.gpa_by_decision(session)

    q10_answers = []
    for group, how_many, average in q10_rows:
        q10_answers.append(
            f"{group}: {oq.show_average(average)} ({oq.show_count(how_many)} applicants)"
        )

    q11_answers = []
    for decision, how_many, average in q11_rows:
        q11_answers.append(
            f"{decision}: {oq.show_average(average)} ({oq.show_count(how_many)} applicants)"
        )

    return [
        {
            "number": 1,
            "question": "How many entries are from applicants who applied for Fall 2026?",
            "answers": [f"Fall 2026 applicant count: {oq.show_count(q1)}"],
        },
        {
            "number": 2,
            "question": "Among entries that give a nationality, what percentage are international students?",
            "answers": [f"Percent international: {oq.show_percent(q2)}"],
        },
        {
            "number": 3,
            "question": "What are the average GPA and GRE scores of applicants who give each one?",
            "answers": [
                f"Average GPA: {oq.show_average(gpa)}",
                f"Average GRE Quantitative: {oq.show_average(gre)}",
                f"Average GRE Verbal: {oq.show_average(gre_v)}",
                f"Average GRE Analytical Writing: {oq.show_average(gre_aw)}",
            ],
        },
        {
            "number": 4,
            "question": "What is the average GPA of American applicants who applied for Fall 2026?",
            "answers": [f"Average GPA: {oq.show_average(q4)}"],
        },
        {
            "number": 5,
            "question": "What percentage of Fall 2025 entries are acceptances?",
            "answers": [f"Fall 2025 acceptance percentage: {oq.show_percent(q5)}"],
        },
        {
            "number": 6,
            "question": "What is the average GPA of accepted applicants who applied for Fall 2026?",
            "answers": [f"Average GPA: {oq.show_average(q6)}"],
        },
        {
            "number": 7,
            "question": "How many entries are Johns Hopkins University master's Computer Science applicants?",
            "answers": [f"Johns Hopkins master's Computer Science entries: {oq.show_count(q7)}"],
        },
        {
            "number": 8,
            "question": "How many Fall 2026 entries are acceptances for a PhD in Computer Science at Georgetown, MIT, Stanford or Carnegie Mellon?",
            "answers": [f"Original-field count: {oq.show_count(q8)}"],
        },
        {
            "number": 9,
            "question": "Repeat Question 8 using the LLM-generated program and university fields.",
            "answers": [
                f"Original-field count: {oq.show_count(q8)}",
                f"LLM-field count: {oq.show_count(q9)}",
                f"Difference: {q9 - q8:+,}",
            ],
        },
        {
            "number": 10,
            "question": "Do international applicants report a higher average GRE Quantitative score than American applicants?",
            "answers": q10_answers,
            "mine": True,
        },
        {
            "number": 11,
            "question": "For Fall 2026, is the average GPA of accepted applicants higher than that of rejected applicants?",
            "answers": q11_answers,
            "mine": True,
        },
    ]


@app.route("/")
def index():
    try:
        questions = build_questions()
        error = None
    except SQLAlchemyError:
        questions = []
        error = "The database could not be reached. Make sure PostgreSQL is running."
    return render_template("index.html", questions=questions, error=error)


if __name__ == "__main__":
    app.run(port=8080)
