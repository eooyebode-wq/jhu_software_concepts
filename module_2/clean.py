# -*- coding: utf-8 -*-
"""Structuring/cleaning helpers for raw Grad Cafe scrape output."""

from __future__ import annotations

import html
import json
import re

from scrape import DEFAULT_RAW_PATH, _build_entry_url, _load_raw_records

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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Structure scrape.py's raw output into applicant_data.json."
    )
    parser.add_argument("--raw-path", default=DEFAULT_RAW_PATH)
    parser.add_argument("--out-path", default="applicant_data.json")
    args = parser.parse_args()

    raw_records = _load_raw_records(args.raw_path)
    print(f"Loaded {len(raw_records)} raw records from {args.raw_path}.")

    structured = clean_data(raw_records)
    save_data(structured, args.out_path)
    print(f"Saved {len(structured)} structured records to {args.out_path}.")
