"""Flask app that shows the Grad Cafe analysis results."""

import threading

from flask import Flask, jsonify, render_template
from sqlalchemy.exc import SQLAlchemyError

import orm_queries as oq
from load_data import load_rows
from models import Applicant, get_session
from pull_data import run_pull, scrape_new_records

DB_ERROR_MESSAGE = (
    "The database could not be reached. Check DATABASE_URL and make sure "
    "PostgreSQL is running."
)


class PullState:
    """Remembers whether a data pull is running.

    Tests can read or set `busy` directly instead of waiting on timing.
    """

    def __init__(self):
        self.busy = False
        self._lock = threading.Lock()

    def try_start(self):
        """Mark a pull as running unless one already is.

        Returns:
            True if this caller started the pull, False if one was running.
        """
        with self._lock:
            if self.busy:
                return False
            self.busy = True
            return True

    def finish(self):
        """Mark the pull as finished."""
        with self._lock:
            self.busy = False


def build_analysis(database_url=None):  # pylint: disable=too-many-locals
    """Ask the database every question and return the answers as text.

    Args:
        database_url: Optional URL that replaces DATABASE_URL.

    Returns:
        A dict with one key, "questions": a list of dicts with the keys
        "number", "question" and "answers" (plus "mine" for my own
        questions). Every answer starts with "Answer: ".
    """
    with get_session(database_url) as session:
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

    questions = [
        {
            "number": 1,
            "question": "How many entries are from applicants who applied for Fall 2026?",
            "answers": [f"Fall 2026 applicant count: {oq.show_count(q1)}"],
        },
        {
            "number": 2,
            "question": (
                "Among entries that give a nationality, what percentage are "
                "international students?"
            ),
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
            "question": (
                "How many entries are Johns Hopkins University master's "
                "Computer Science applicants?"
            ),
            "answers": [
                f"Johns Hopkins master's Computer Science entries: {oq.show_count(q7)}"
            ],
        },
        {
            "number": 8,
            "question": (
                "How many Fall 2026 entries are acceptances for a PhD in Computer "
                "Science at Georgetown, MIT, Stanford or Carnegie Mellon?"
            ),
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
            "question": (
                "Do international applicants report a higher average GRE "
                "Quantitative score than American applicants?"
            ),
            "answers": q10_answers,
            "mine": True,
        },
        {
            "number": 11,
            "question": (
                "For Fall 2026, is the average GPA of accepted applicants higher "
                "than that of rejected applicants?"
            ),
            "answers": q11_answers,
            "mine": True,
        },
    ]

    for item in questions:
        item["answers"] = [f"Answer: {line}" for line in item["answers"]]
    return {"questions": questions}


def create_app(config=None, scraper=None, loader=None, query_fn=None):
    """Build the Flask app.

    Every argument is optional. Tests pass fakes so nothing touches the
    internet, and a test database URL through `config`.

    Args:
        config: Dict merged into app.config. Set "DATABASE_URL" here to use
            a different database than the DATABASE_URL environment variable.
        scraper: Function with no arguments that returns raw records.
        loader: Function that takes a list of row tuples and returns how many
            were added.
        query_fn: Function with no arguments that returns the dict made by
            build_analysis.

    Returns:
        The configured Flask app. Its busy state is available as
        app.extensions["pull_state"].
    """
    app = Flask(__name__)
    if config:
        app.config.update(config)

    state = PullState()
    app.extensions["pull_state"] = state

    def database_url():
        return app.config.get("DATABASE_URL")

    scraper = scraper or (lambda: scrape_new_records(database_url()))
    loader = loader or (lambda rows: load_rows(rows, database_url()))
    query_fn = query_fn or (lambda: build_analysis(database_url()))

    @app.route("/")
    @app.route("/analysis")
    def index():
        """Show the analysis page."""
        try:
            questions = query_fn()["questions"]
            error = None
        except (SQLAlchemyError, RuntimeError):
            questions = []
            error = DB_ERROR_MESSAGE
        return render_template(
            "index.html", questions=questions, error=error, running=state.busy
        )

    @app.route("/pull-data", methods=["POST"])
    def pull():
        """Run a pull, unless one is already running."""
        if not state.try_start():
            return jsonify(busy=True), 409
        try:
            run_pull(scraper, loader)
        except Exception as err:  # pylint: disable=broad-except
            return jsonify(ok=False, error=str(err)), 500
        finally:
            state.finish()
        return jsonify(ok=True)

    @app.route("/update-analysis", methods=["POST"])
    def update():
        """Refresh the analysis. Does nothing while a pull is running."""
        if state.busy:
            return jsonify(busy=True), 409
        try:
            query_fn()
        except (SQLAlchemyError, RuntimeError):
            return jsonify(ok=False, error=DB_ERROR_MESSAGE), 500
        return jsonify(ok=True)

    return app


if __name__ == "__main__":
    create_app().run(port=8080)
