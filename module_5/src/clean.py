# -*- coding: utf-8 -*-
"""Structuring/cleaning helpers for raw Grad Cafe scrape output."""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import subprocess
import sys

from scrape import DEFAULT_RAW_PATH, _build_entry_url, _load_raw_records

LLM_HOSTING_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, "llm_hosting"
)
DEFAULT_LLM_WORK_DIR = "_llm_work"
DEFAULT_N_WORKERS = 2
DEFAULT_N_THREADS_PER_WORKER = 5

_TAG_RE = re.compile(r"<[^>]+>")

# Every applicant_status value the scraper can produce; anything else in the
# source's `decision` field falls back to "Other" rather than guessing.
_STATUS_MAP = {
    "accepted": "Accepted",
    "rejected": "Rejected",
    "wait listed": "Wait listed",
    "waitlisted": "Wait listed",
    "interview": "Interview",
}


def _normalize_status(decision) -> str:
    """Map a raw GradCafe `decision` value onto the applicant_status vocabulary."""
    key = (decision or "").strip().lower()
    return _STATUS_MAP.get(key, "Other")


def _clean_text(text):
    """Strip remnant HTML tags/entities from free text without altering its content."""
    if not text:
        return None
    text = html.unescape(text)
    text = _TAG_RE.sub("", text)
    return text.strip() or None


def _parse_entry(record: dict) -> dict:
    """Map one raw GradCafe result record onto the applicant_data.json schema.

    Every field is always present; None marks anything unavailable. Never
    alters applicant-provided text (program/university/comments) beyond
    HTML-entity/tag cleanup.
    """
    status = _normalize_status(record.get("decision"))

    return {
        "program": record.get("program") or None,
        "university": record.get("school") or None,
        "comments": _clean_text(record.get("notes")),
        "date_added": record.get("created_at") or None,
        "url": _build_entry_url(record["id"]) if record.get("id") else None,
        "applicant_status": status,
        "acceptance_date": record.get("acceptedDate") if status == "Accepted" else None,
        "rejection_date": record.get("rejectedDate") if status == "Rejected" else None,
        "semester_year": record.get("season") or None,
        "student_type": record.get("status") or None,
        "gre_score": record.get("greq"),
        "gre_v_score": record.get("grev"),
        "gre_aw_score": record.get("grew"),
        "degree_type": record.get("level") or None,
        "gpa": record.get("ugpa"),
    }


def clean_data(raw_records: list[dict]) -> list[dict]:
    """Convert raw scraped GradCafe records into the structured applicant_data.json schema."""
    return [_parse_entry(record) for record in raw_records]


def save_data(records: list[dict], path: str) -> None:
    """Save a list of record dicts to `path` as valid JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def load_data(path: str) -> list[dict]:
    """Load a list of record dicts from a JSON file at `path`."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _llm_input_text(record: dict) -> str:
    """Put program and university back into one "program, university" string,
    since that's the format app.py is built to read.
    """
    parts = [p for p in (record.get("program"), record.get("university")) if p]
    return ", ".join(parts)


def _post_process_name(value):
    """Turn app.py's "Unknown" or empty result into None, so missing values
    look the same everywhere in this project. app.py already does its own
    cleanup (fixing abbreviations, matching known names), so there's no need
    to redo that here.
    """
    value = (value or "").strip()
    if not value or value.lower() == "unknown":
        return None
    return value


def _start_llm_chunk_process(chunk_input_path: str, chunk_output_path: str, n_threads: int):
    """Run app.py on one chunk of records in the background.

    If chunk_output_path already has some rows in it from an earlier run
    that got interrupted, only the rows that are still missing get sent
    through, and they're added onto the existing file. Returns None if this
    chunk is already done.
    """
    with open(chunk_input_path, "r", encoding="utf-8") as f:
        all_rows = json.load(f)

    already_done = 0
    if os.path.exists(chunk_output_path):
        with open(chunk_output_path, "r", encoding="utf-8") as f:
            already_done = sum(1 for line in f if line.strip())

    remaining = all_rows[already_done:]
    if not remaining:
        return None

    remaining_path = chunk_input_path + ".remaining.json"
    with open(remaining_path, "w", encoding="utf-8") as f:
        json.dump(remaining, f)

    env = os.environ.copy()
    env["N_THREADS"] = str(n_threads)

    return subprocess.Popen(
        [
            sys.executable, "app.py",
            "--file", os.path.abspath(remaining_path),
            "--out", os.path.abspath(chunk_output_path),
            "--append",
        ],
        cwd=LLM_HOSTING_DIR,
        env=env,
    )


def standardize_names(
    records: list[dict],
    n_workers: int = DEFAULT_N_WORKERS,
    n_threads: int = DEFAULT_N_THREADS_PER_WORKER,
    work_dir: str = DEFAULT_LLM_WORK_DIR,
) -> list[dict]:
    """Run all the records through app.py, split across `n_workers` processes
    at once, and add cleaned_program/cleaned_university to each one without
    changing anything else. If you stop this partway through, rerun it with
    the same `n_workers` number so it can pick up where it left off.
    """
    os.makedirs(work_dir, exist_ok=True)
    chunk_size = math.ceil(len(records) / n_workers)

    chunks = []
    for i in range(n_workers):
        chunk_records = records[i * chunk_size : (i + 1) * chunk_size]
        if not chunk_records:
            continue
        input_path = os.path.join(work_dir, f"chunk_{i}_input.json")
        output_path = os.path.join(work_dir, f"chunk_{i}_output.jsonl")
        if not os.path.exists(input_path):
            llm_input = [{"program": _llm_input_text(r)} for r in chunk_records]
            with open(input_path, "w", encoding="utf-8") as f:
                json.dump(llm_input, f)
        chunks.append((input_path, output_path))

    running = []
    for input_path, output_path in chunks:
        proc = _start_llm_chunk_process(input_path, output_path, n_threads)
        print(f"{'Started' if proc else 'Already complete'}: {output_path}")
        if proc is not None:
            running.append((proc, output_path))

    for proc, output_path in running:
        if proc.wait() != 0:
            raise RuntimeError(f"LLM chunk process failed: {output_path}")

    llm_results = []
    for _, output_path in chunks:
        with open(output_path, "r", encoding="utf-8") as f:
            llm_results.extend(json.loads(line) for line in f if line.strip())

    if len(llm_results) != len(records):
        raise RuntimeError(
            f"Mismatch: {len(llm_results)} LLM results vs {len(records)} input records"
        )

    return [
        {
            **record,
            "cleaned_program": _post_process_name(llm_row.get("llm-generated-program")),
            "cleaned_university": _post_process_name(llm_row.get("llm-generated-university")),
        }
        for record, llm_row in zip(records, llm_results)
    ]


def main(argv=None):
    """Run the cleaning and LLM standardization steps from the command line.

    Args:
        argv: Optional list of command-line arguments. Uses sys.argv if None.
    """
    parser = argparse.ArgumentParser(
        description="Structure scrape.py's raw output, and/or run the local-LLM "
        "program/university standardization pass."
    )
    parser.add_argument("--raw-path", default=DEFAULT_RAW_PATH)
    parser.add_argument("--out-path", default="applicant_data.json")
    parser.add_argument(
        "--llm-extend",
        action="store_true",
        help="Also run the LLM standardization pass, reading --out-path (or "
        "--in-path) and writing --llm-out-path.",
    )
    parser.add_argument(
        "--in-path",
        default=None,
        help="For --llm-extend: input file (default: --out-path, i.e. chain "
        "off the structuring step just run).",
    )
    parser.add_argument("--llm-out-path", default="llm_extend_applicant_data.json")
    parser.add_argument("--n-workers", type=int, default=DEFAULT_N_WORKERS)
    parser.add_argument("--n-threads", type=int, default=DEFAULT_N_THREADS_PER_WORKER)
    parser.add_argument(
        "--skip-structuring",
        action="store_true",
        help="Skip the raw->applicant_data.json step and go straight to --llm-extend.",
    )
    args = parser.parse_args(argv)

    structured = None
    if not args.skip_structuring:
        raw_records = _load_raw_records(args.raw_path)
        print(f"Loaded {len(raw_records)} raw records from {args.raw_path}.")
        structured = clean_data(raw_records)
        save_data(structured, args.out_path)
        print(f"Saved {len(structured)} structured records to {args.out_path}.")

    if args.llm_extend:
        in_path = args.in_path or args.out_path
        if structured is None:
            structured = load_data(in_path)
            print(f"Loaded {len(structured)} records from {in_path}.")
        extended = standardize_names(structured, n_workers=args.n_workers, n_threads=args.n_threads)
        save_data(extended, args.llm_out_path)
        print(f"Saved {len(extended)} LLM-extended records to {args.llm_out_path}.")


if __name__ == "__main__":
    main()
