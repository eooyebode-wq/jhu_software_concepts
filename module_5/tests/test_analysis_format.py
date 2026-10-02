"""Tests for the "Answer:" labels and the two-decimal percentages."""

import re
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup

import orm_queries as oq

pytestmark = pytest.mark.analysis

PERCENT_ANYWHERE = re.compile(r"\d[\d,]*(?:\.\d+)?%")
TWO_DECIMAL_PERCENT = re.compile(r"\d+\.\d{2}%")


def analysis_soup(client):
    """Fetch the analysis page and parse its HTML."""
    return BeautifulSoup(client.get("/analysis").get_data(as_text=True), "html.parser")


def test_every_answer_line_starts_with_answer_label(client, seed_db):
    # Given a database with data
    seed_db()
    # When we read every answer line on the page
    lines = [li.get_text(strip=True) for li in analysis_soup(client).select(".answers li")]
    # Then there are some, and each one starts with "Answer:"
    assert lines
    assert all(line.startswith("Answer:") for line in lines)


def test_every_percentage_has_two_decimals(client, seed_db):
    # Given a database with data
    seed_db()
    # When we find every percentage on the page
    percents = PERCENT_ANYWHERE.findall(analysis_soup(client).get_text())
    # Then there are some, and each has exactly two decimals
    assert percents
    assert all(TWO_DECIMAL_PERCENT.fullmatch(p) for p in percents)


def test_percentages_are_rounded_not_cut(client, seed_db):
    # Given 3 of 7 entries are international and 1 of 3 Fall 2025 entries is accepted
    seed_db()
    # When we read the page
    text = analysis_soup(client).get_text()
    # Then the percentages are rounded to two decimals
    assert "Answer: Percent international: 42.86%" in text
    assert "Answer: Fall 2025 acceptance percentage: 33.33%" in text


def test_whole_number_percentage_keeps_two_decimals(client, seed_db, fake_records):
    # Given only international entries, so exactly 100 percent
    seed_db([r for r in fake_records if r["status"] == "International"])
    # When we read the page
    text = analysis_soup(client).get_text()
    # Then the percentage shows 100.00%, not 100%
    assert "Answer: Percent international: 100.00%" in text


def test_empty_table_shows_na_for_percentages(client):
    # Given an empty table
    # When we read the page
    text = analysis_soup(client).get_text()
    # Then a percentage with no data shows N/A
    assert "Answer: Percent international: N/A" in text


def test_show_percent_uses_two_decimals():
    # Given a database value like the ones PostgreSQL returns
    # When it is formatted
    # Then it has two decimals and a percent sign
    assert oq.show_percent(Decimal("39.28")) == "39.28%"
    assert oq.show_percent(Decimal("50")) == "50.00%"


def test_show_percent_handles_missing_value():
    assert oq.show_percent(None) == "N/A"


def test_show_average_uses_two_decimals():
    assert oq.show_average(Decimal("3.5")) == "3.50"
    assert oq.show_average(None) == "N/A"


def test_show_count_adds_commas():
    assert oq.show_count(19290) == "19,290"
