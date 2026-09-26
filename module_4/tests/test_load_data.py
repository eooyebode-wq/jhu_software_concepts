"""Tests for the cleaning helpers and the loader in load_data.py."""

import json
import sys

import psycopg
import pytest

import clean
import load_data

pytestmark = pytest.mark.db


def count_rows(conn):
    """How many rows are in the applicants table."""
    return conn.execute("SELECT COUNT(*) FROM applicants").fetchone()[0]


def write_records(path, fake_records):
    """Write cleaned records, plus one with no usable id, to a JSON file."""
    records = clean.clean_data(fake_records)
    records.append({"program": "No link", "url": None})
    path.write_text(json.dumps(records), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize(
    "value, expected",
    [(None, None), ("   ", None), (" text ", "text")],
)
def test_clean_text_returns_none_for_blank_values(value, expected):
    assert load_data.clean_text(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [("3.40", 3.4), ("abc", None), (None, None)],
)
def test_to_float_returns_none_when_not_a_number(value, expected):
    assert load_data.to_float(value) == expected


@pytest.mark.parametrize(
    "value, low, high, expected",
    [
        ("3.5", 0, 4.0, 3.5),
        ("0", 0, 4.0, None),
        ("11", 0, 4.0, None),
        ("120", 130, 170, None),
        (None, 130, 170, None),
    ],
)
def test_to_score_drops_zero_and_out_of_range_values(value, low, high, expected):
    assert load_data.to_score(value, low, high) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        (None, None),
        ("", None),
        ("https://www.thegradcafe.com/result/42", 42),
        ("https://www.thegradcafe.com/result/42/", 42),
        ("https://www.thegradcafe.com/result/abc", None),
    ],
)
def test_get_p_id_reads_the_number_at_the_end_of_the_url(url, expected):
    assert load_data.get_p_id(url) == expected


@pytest.mark.parametrize(
    "program, university, expected",
    [("CS", "MIT", "CS, MIT"), (None, "MIT", "MIT"), ("  ", None, None)],
)
def test_make_program_joins_the_parts_that_exist(program, university, expected):
    assert load_data.make_program(program, university) == expected


@pytest.mark.parametrize(
    "value, expected",
    [("0", None), ("", None), (None, None), ("American", "American")],
)
def test_make_nationality_stores_null_for_no_classification(value, expected):
    assert load_data.make_nationality(value) == expected


def test_make_row_builds_a_tuple_in_column_order(fake_records):
    # Given a cleaned record
    record = clean.clean_data(fake_records)[0]
    # When we build its row
    row = load_data.make_row(record)
    # Then the values are in column order
    assert row[0] == 1001
    assert row[1] == "Computer Science, Johns Hopkins University"
    assert row[5:9] == ("Accepted", "Fall 2026", "International", 3.8)
    assert row[9] == 165.0
    assert row[12] == "Masters"


def test_make_row_returns_none_without_a_usable_id():
    assert load_data.make_row({"program": "CS", "url": None}) is None


def test_read_records_reads_a_json_file(tmp_path):
    path = tmp_path / "records.json"
    path.write_text('[{"a": 1}]', encoding="utf-8")
    assert load_data.read_records(str(path)) == [{"a": 1}]


def test_insert_rows_adds_up_every_batch(monkeypatch, seed_db, db_conn, fake_records):
    # Given a batch size smaller than the number of rows
    monkeypatch.setattr(load_data, "BATCH_SIZE", 2)
    # When the rows are loaded
    added = seed_db()
    # Then the count covers every batch
    assert added == len(fake_records)
    assert count_rows(db_conn) == len(fake_records)


def test_main_loads_the_file_and_reports_counts(monkeypatch, tmp_path, capsys, db_conn,
                                                fake_records):
    # Given a file with seven usable records and one without an id
    path = write_records(tmp_path / "records.json", fake_records)
    monkeypatch.setattr(sys, "argv", ["load_data.py", path])
    # When main runs
    load_data.main()
    # Then it reports the counts and the rows are in the table
    output = capsys.readouterr().out
    assert "Records read: 8" in output
    assert "Skipped (no usable id): 1" in output
    assert "Newly added: 7" in output
    assert count_rows(db_conn) == 7


def test_main_run_twice_adds_nothing_new(monkeypatch, tmp_path, capsys, db_conn, fake_records):
    # Given a file that was already loaded once
    path = write_records(tmp_path / "records.json", fake_records)
    monkeypatch.setattr(sys, "argv", ["load_data.py", path])
    load_data.main()
    capsys.readouterr()
    # When main runs again
    load_data.main()
    # Then nothing new is added
    output = capsys.readouterr().out
    assert "Newly added: 0" in output
    assert "Already in the table: 7" in output
    assert count_rows(db_conn) == 7


def test_main_uses_the_default_file_when_none_is_given(monkeypatch, tmp_path, db_conn,
                                                       fake_records):
    # Given a default data file and no file on the command line
    path = write_records(tmp_path / "records.json", fake_records)
    monkeypatch.setattr(load_data, "DEFAULT_DATA_FILE", path)
    monkeypatch.setattr(sys, "argv", ["load_data.py"])
    # When main runs
    load_data.main()
    # Then the default file was loaded
    assert count_rows(db_conn) == 7


def test_main_reports_a_file_it_cannot_read(monkeypatch, tmp_path, capsys):
    # Given a path that does not exist
    monkeypatch.setattr(sys, "argv", ["load_data.py", str(tmp_path / "missing.json")])
    # When main runs
    load_data.main()
    # Then it says so instead of crashing
    assert "Could not read" in capsys.readouterr().out


def test_main_reports_a_database_error(monkeypatch, tmp_path, capsys, fake_records):
    # Given a valid file but a database that cannot be reached
    path = write_records(tmp_path / "records.json", fake_records)
    monkeypatch.setattr(sys, "argv", ["load_data.py", path])

    def refuse(*args, **kwargs):
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(load_data, "get_connection", refuse)
    # When main runs
    load_data.main()
    # Then it reports the database error
    assert "Database error: down" in capsys.readouterr().out
