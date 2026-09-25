"""Flask page that shows the Grad Cafe analysis results."""

import os
import subprocess
import sys
import threading

from flask import Flask, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

import orm_queries as oq
from models import Applicant, Session

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PULL_LOG = os.path.join(BASE_DIR, "pull_data.log")

# Only one pull may run at a time. The running process is remembered here in
# memory, so run the app as one process (python app.py).
pull_state = {"process": None, "result": None}
pull_lock = threading.Lock()

STATUS_MESSAGES = {
    "started": ("info", "Pull Data started. New entries are being retrieved. "
                        "This may take a while, and you can keep using this page."),
    "busy": ("warning", "A data pull is already running, so a new one was not started."),
    "updated": ("success", "Analysis updated with the latest data in the database."),
    "update_busy": ("warning", "New data is currently being retrieved. Update Analysis "
                               "did not interrupt it. Try again when the pull finishes."),
}


def build_questions():  # pylint: disable=too-many-locals
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


def read_pull_result(exit_code):
    """Turn the finished pull's log file into a message for the page."""
    try:
        with open(PULL_LOG, "r", encoding="utf-8") as log:
            lines = [line.strip() for line in log if line.strip()]
    except OSError:
        lines = []

    for line in reversed(lines):
        if exit_code == 0 and line.startswith("DONE:"):
            return {"kind": "success", "text": "Pull finished. " + line[5:].strip().capitalize()}
        if line.startswith("ERROR:"):
            reason = line[6:].strip()
            return {"kind": "error", "text": "Pull failed. " + reason[:1].upper() + reason[1:]}
    return {"kind": "error", "text": "The pull stopped unexpectedly. Check that Chrome is open."}


def pull_is_running():
    """True while a pull is running. Records the result once it has finished."""
    process = pull_state["process"]
    if process is None:
        return False
    exit_code = process.poll()
    if exit_code is None:
        return True
    pull_state["result"] = read_pull_result(exit_code)
    pull_state["process"] = None
    return False


@app.route("/")
def index():
    """Show the analysis page."""
    try:
        questions = build_questions()
        error = None
    except SQLAlchemyError:
        questions = []
        error = "The database could not be reached. Make sure PostgreSQL is running."

    running = pull_is_running()
    status = request.args.get("status")
    message = STATUS_MESSAGES.get(status)
    # These messages are about a pull that is in progress, so drop them once
    # it has finished.
    if not running and status in ("started", "busy", "update_busy"):
        message = None
    return render_template(
        "index.html",
        questions=questions,
        error=error,
        running=running,
        message=message,
        pull_result=pull_state["result"],
    )


@app.route("/pull", methods=["POST"])
def pull():
    """Start a pull in a separate process, unless one is already running."""
    with pull_lock:
        if pull_is_running():
            return redirect(url_for("index", status="busy"))
        pull_state["result"] = None
        with open(PULL_LOG, "w", encoding="utf-8") as log:
            # The pull has to keep running after this request ends, so no `with`.
            pull_state["process"] = subprocess.Popen(  # pylint: disable=consider-using-with
                [sys.executable, "pull_data.py"],
                cwd=BASE_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
    return redirect(url_for("index", status="started"))


@app.route("/update", methods=["POST"])
def update():
    """Reload the results. This never starts a scrape."""
    if pull_is_running():
        return redirect(url_for("index", status="update_busy"))
    return redirect(url_for("index", status="updated"))


if __name__ == "__main__":
    app.run(port=8080)
