# -*- coding: utf-8 -*-
"""Structuring/cleaning helpers for raw Grad Cafe scrape output."""

from __future__ import annotations


def clean_data(raw_records):
    """Convert raw scraped records into the structured applicant_data.json schema.

    TODO (Phase 3): map each raw record to the full target field set, filling
    every field (None/""  for missing data, per README convention).
    """
    raise NotImplementedError


def save_data(records, path):
    """Save a list of record dicts to `path` as valid JSON.

    TODO (Phase 3).
    """
    raise NotImplementedError


def load_data(path):
    """Load a list of record dicts from a JSON file at `path`.

    TODO (Phase 3).
    """
    raise NotImplementedError


if __name__ == "__main__":
    pass
