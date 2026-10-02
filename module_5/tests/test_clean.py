"""Tests for clean.py with the LLM subprocess replaced by fakes."""

import json
import runpy
import sys

import pytest

import clean

pytestmark = pytest.mark.db


class FakeProcess:  # pylint: disable=too-few-public-methods
    """Stands in for a subprocess that has already finished."""

    def __init__(self, exit_code=0):
        self.exit_code = exit_code

    def wait(self):
        """Return the exit code right away."""
        return self.exit_code


def fake_llm_starter(exit_code=0, missing=0):
    """A replacement for _start_llm_chunk_process that writes fake LLM output."""
    def start(input_path, output_path, n_threads):
        with open(input_path, "r", encoding="utf-8") as f:
            rows = json.load(f)
        with open(output_path, "a", encoding="utf-8") as f:
            for _ in rows[:len(rows) - missing]:
                line = {"llm-generated-program": "Computer Science",
                        "llm-generated-university": "Unknown"}
                f.write(json.dumps(line) + "\n")
        return FakeProcess(exit_code)
    return start


def write_json(path, data):
    """Write data as JSON and return the path as text."""
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def write_lines(path, records):
    """Write one JSON object per line and return the path as text."""
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize(
    "text, expected",
    [
        (None, None),
        ("", None),
        ("<br>", None),
        ("  <b>Fun</b> &amp; games ", "Fun & games"),
    ],
)
def test_clean_text_strips_tags_and_entities(text, expected):
    assert clean._clean_text(text) == expected


def test_save_data_and_load_data_round_trip(tmp_path):
    # Given records with a non-ASCII character
    records = [{"program": "Informatique", "university": "Universite de Montreal é"}]
    path = str(tmp_path / "records.json")
    # When we save and load them
    clean.save_data(records, path)
    # Then they come back unchanged
    assert clean.load_data(path) == records


def test_llm_input_text_joins_program_and_university():
    assert clean._llm_input_text({"program": "CS", "university": "MIT"}) == "CS, MIT"
    assert clean._llm_input_text({"program": "CS", "university": None}) == "CS"


@pytest.mark.parametrize(
    "value, expected",
    [(None, None), ("   ", None), ("Unknown", None), (" MIT ", "MIT")],
)
def test_post_process_name_turns_unknown_into_none(value, expected):
    assert clean._post_process_name(value) == expected


def test_chunk_that_is_already_done_is_not_started(tmp_path):
    # Given a chunk whose output already has a line for each input row
    input_path = write_json(tmp_path / "in.json", [{"program": "a"}, {"program": "b"}])
    output_path = write_lines(tmp_path / "out.jsonl", [{}, {}])
    # Then nothing is started
    assert clean._start_llm_chunk_process(input_path, output_path, 2) is None


def test_chunk_sends_only_the_missing_rows(monkeypatch, tmp_path):
    # Given three input rows and one already in the output
    input_path = write_json(tmp_path / "in.json", [{"program": "a"}, {"program": "b"},
                                                   {"program": "c"}])
    output_path = write_lines(tmp_path / "out.jsonl", [{}])
    started = {}

    def fake_popen(args, **kwargs):
        started["args"] = args
        started["kwargs"] = kwargs
        return "process"

    monkeypatch.setattr(clean.subprocess, "Popen", fake_popen)
    # When the chunk is started
    process = clean._start_llm_chunk_process(input_path, output_path, 3)
    # Then only the last two rows are sent, appended to the output
    assert process == "process"
    with open(input_path + ".remaining.json", "r", encoding="utf-8") as f:
        assert json.load(f) == [{"program": "b"}, {"program": "c"}]
    assert "--append" in started["args"]
    assert started["kwargs"]["env"]["N_THREADS"] == "3"
    assert started["kwargs"]["cwd"] == clean.LLM_HOSTING_DIR


def test_chunk_without_an_output_file_sends_every_row(monkeypatch, tmp_path):
    # Given three input rows and no output file yet
    rows = [{"program": "a"}, {"program": "b"}, {"program": "c"}]
    input_path = write_json(tmp_path / "in.json", rows)
    monkeypatch.setattr(clean.subprocess, "Popen", lambda args, **kwargs: "process")
    # When the chunk is started
    clean._start_llm_chunk_process(input_path, str(tmp_path / "out.jsonl"), 1)
    # Then all rows are sent
    with open(input_path + ".remaining.json", "r", encoding="utf-8") as f:
        assert json.load(f) == rows


def test_standardize_names_adds_cleaned_fields(monkeypatch, tmp_path):
    # Given three records, two workers and a fake LLM that answers Unknown for the school
    monkeypatch.setattr(clean, "_start_llm_chunk_process", fake_llm_starter())
    records = [{"program": "CS", "university": "MIT", "gpa": g} for g in (3.1, 3.2, 3.3)]
    # When the names are standardized
    result = clean.standardize_names(records, n_workers=2, work_dir=str(tmp_path / "work"))
    # Then order and old fields are kept, Unknown became None
    assert [r["gpa"] for r in result] == [3.1, 3.2, 3.3]
    assert {r["cleaned_program"] for r in result} == {"Computer Science"}
    assert {r["cleaned_university"] for r in result} == {None}


def test_standardize_names_skips_workers_with_no_records(monkeypatch, tmp_path):
    # Given more workers than records
    monkeypatch.setattr(clean, "_start_llm_chunk_process", fake_llm_starter())
    # When one record is standardized with two workers
    result = clean.standardize_names([{"program": "CS"}], n_workers=2,
                                     work_dir=str(tmp_path / "work"))
    # Then it still works
    assert len(result) == 1


def test_standardize_names_reuses_finished_chunks(monkeypatch, tmp_path):
    # Given a chunk whose output is already complete
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    write_lines(work_dir / "chunk_0_output.jsonl",
                [{"llm-generated-program": "Physics", "llm-generated-university": "Yale"}])
    monkeypatch.setattr(clean, "_start_llm_chunk_process", lambda *args: None)
    # When the names are standardized
    result = clean.standardize_names([{"program": "Physics"}], n_workers=1,
                                     work_dir=str(work_dir))
    # Then the saved output is used
    assert result[0]["cleaned_university"] == "Yale"


def test_standardize_names_fails_when_a_worker_fails(monkeypatch, tmp_path):
    # Given a worker that exits with an error
    monkeypatch.setattr(clean, "_start_llm_chunk_process", fake_llm_starter(exit_code=1))
    # Then standardizing raises
    with pytest.raises(RuntimeError, match="chunk process failed"):
        clean.standardize_names([{"program": "CS"}], n_workers=1,
                                work_dir=str(tmp_path / "work"))


def test_standardize_names_fails_when_results_are_missing(monkeypatch, tmp_path):
    # Given a worker that returns one row too few
    monkeypatch.setattr(clean, "_start_llm_chunk_process", fake_llm_starter(missing=1))
    # Then standardizing raises
    with pytest.raises(RuntimeError, match="Mismatch"):
        clean.standardize_names([{"program": "CS"}, {"program": "MIT"}], n_workers=1,
                                work_dir=str(tmp_path / "work"))


def test_main_structures_the_raw_records(tmp_path, fake_records):
    # Given a raw file
    raw = write_lines(tmp_path / "raw.jsonl", fake_records)
    out = tmp_path / "out.json"
    # When main runs with only the structuring step
    clean.main(["--raw-path", raw, "--out-path", str(out)])
    # Then the structured file has one record per raw record
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert len(saved) == len(fake_records)
    assert saved[0]["url"] == "https://www.thegradcafe.com/result/1001"


def test_main_runs_the_llm_step_after_structuring(monkeypatch, tmp_path, fake_records):
    # Given a fake LLM step that records its options
    seen = {}

    def fake_standardize(records, n_workers, n_threads):
        seen.update(count=len(records), workers=n_workers, threads=n_threads)
        return [{**r, "cleaned_program": "X"} for r in records]

    monkeypatch.setattr(clean, "standardize_names", fake_standardize)
    raw = write_lines(tmp_path / "raw.jsonl", fake_records)
    llm_out = tmp_path / "llm.json"
    # When main runs with --llm-extend
    clean.main(["--raw-path", raw, "--out-path", str(tmp_path / "out.json"),
                "--llm-extend", "--llm-out-path", str(llm_out),
                "--n-workers", "3", "--n-threads", "4"])
    # Then the LLM step got the structured records and its result was saved
    assert seen == {"count": 7, "workers": 3, "threads": 4}
    assert json.loads(llm_out.read_text(encoding="utf-8"))[0]["cleaned_program"] == "X"


def test_main_can_skip_structuring_and_load_a_file(monkeypatch, tmp_path):
    # Given a structured file and a fake LLM step
    in_path = write_json(tmp_path / "in.json", [{"program": "CS"}, {"program": "MIT"}])
    monkeypatch.setattr(clean, "standardize_names",
                        lambda records, n_workers, n_threads: records)
    llm_out = tmp_path / "llm.json"
    # When main skips structuring
    clean.main(["--skip-structuring", "--llm-extend", "--in-path", in_path,
                "--llm-out-path", str(llm_out)])
    # Then the file that was given is what gets standardized
    assert len(json.loads(llm_out.read_text(encoding="utf-8"))) == 2


def test_running_the_file_as_a_script_reads_the_command_line(monkeypatch, src_dir, capsys):
    # Given the script started with --help, which exits before doing any work
    monkeypatch.setattr(sys, "argv", ["clean.py", "--help"])
    # When it runs as __main__
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(src_dir / "clean.py"), run_name="__main__")
    # Then it printed its usage and exited normally
    assert exit_info.value.code == 0
    assert "--llm-extend" in capsys.readouterr().out
