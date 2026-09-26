"""Tests for the command-line query scripts (raw SQL and SQLAlchemy)."""

import runpy
import sys

import psycopg
import pytest
from sqlalchemy.exc import SQLAlchemyError

import orm_queries
import query_data

pytestmark = pytest.mark.db


def printed_lines(capsys):
    """The lines a script printed since the last check."""
    return capsys.readouterr().out.splitlines()


def test_sql_script_prints_every_answer_in_the_required_format(seed_db, capsys):
    # Given a database with the seven fake entries
    seed_db()
    # When the SQL script runs
    query_data.main()
    lines = printed_lines(capsys)
    # Then each answer is printed with the required formatting
    assert "Q1. Fall 2026 applicant count: 4" in lines
    assert "Q2. Percent international: 42.86%" in lines
    assert "Q5. Fall 2025 acceptance percentage: 33.33%" in lines
    assert "Q7. Johns Hopkins master's Computer Science entries: 1" in lines
    assert "    Original-field count: 1" in lines
    assert "    American: 158.75 (4 applicants)" in lines
    assert "    International: 160.67 (3 applicants)" in lines
    assert "    Accepted: 3.85 (2 applicants)" in lines
    assert "    Rejected: 3.50 (1 applicants)" in lines


def test_sql_script_shows_na_on_an_empty_table(capsys):
    # Given an empty table
    # When the SQL script runs
    query_data.main()
    # Then answers with no data show N/A
    assert "Q2. Percent international: N/A" in printed_lines(capsys)


def test_orm_script_prints_the_same_lines_as_the_sql_script(seed_db, capsys):
    # Given a database with data
    seed_db()
    query_data.main()
    sql_lines = printed_lines(capsys)
    # When the SQLAlchemy script runs
    orm_queries.main()
    orm_lines = [line for line in printed_lines(capsys) if line != "SQLAlchemy results"]
    # Then every line it prints is also printed by the SQL script
    assert orm_lines
    assert set(orm_lines) <= set(sql_lines)


def test_sql_script_reports_a_database_error(monkeypatch, capsys):
    def refuse():
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(query_data, "get_connection", refuse)
    query_data.main()
    assert "Database error: down" in capsys.readouterr().out


def test_orm_script_reports_a_database_error(monkeypatch, capsys):
    def refuse():
        raise SQLAlchemyError("down")

    monkeypatch.setattr(orm_queries, "get_session", refuse)
    orm_queries.main()
    assert "Database error: down" in capsys.readouterr().out


@pytest.mark.parametrize("script", ["query_data.py", "orm_queries.py", "load_data.py"])
def test_running_a_script_file_calls_its_main(monkeypatch, src_dir, tmp_path, capsys, script):
    # Given a load_data argument that points at a missing file, so nothing is loaded
    monkeypatch.setattr(sys, "argv", [script, str(tmp_path / "missing.json")])
    # When the file runs as __main__
    runpy.run_path(str(src_dir / script), run_name="__main__")
    # Then its main function ran and printed something
    assert capsys.readouterr().out
