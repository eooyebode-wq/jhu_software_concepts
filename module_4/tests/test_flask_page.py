"""Tests for the Flask app factory and the analysis page."""

import runpy

import pytest
from bs4 import BeautifulSoup
from flask import Flask

pytestmark = pytest.mark.web


def test_running_app_as_a_script_starts_the_server_on_port_8080(monkeypatch, src_dir):
    # Given a Flask.run that records its arguments instead of starting a server
    started = {}
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: started.update(kwargs))
    # When app.py runs as __main__
    runpy.run_path(str(src_dir / "app.py"), run_name="__main__")
    # Then the server was asked to start on port 8080
    assert started == {"port": 8080}


def page_soup(client, path="/analysis"):
    """Fetch a page and parse its HTML."""
    return BeautifulSoup(client.get(path).get_data(as_text=True), "html.parser")


def test_create_app_returns_flask_app(app):
    # Given an app built by the factory
    # Then it is a Flask app in testing mode
    assert isinstance(app, Flask)
    assert app.config["TESTING"] is True


@pytest.mark.parametrize(
    "path, method",
    [
        ("/", "GET"),
        ("/analysis", "GET"),
        ("/pull-data", "POST"),
        ("/update-analysis", "POST"),
    ],
)
def test_required_route_is_registered(app, path, method):
    # Given an app built by the factory
    # When we list the methods registered for a path
    methods = {
        m for rule in app.url_map.iter_rules() if rule.rule == path for m in rule.methods
    }
    # Then the required method is there
    assert method in methods


def test_get_analysis_returns_200(client):
    # Given a running app
    # When we load the analysis page
    response = client.get("/analysis")
    # Then the status is 200
    assert response.status_code == 200


def test_root_shows_the_same_page(client):
    # Given a running app
    # When we load "/"
    response = client.get("/")
    # Then it also shows the analysis page
    assert response.status_code == 200
    assert "Analysis" in response.get_data(as_text=True)


def test_page_has_pull_data_button(client):
    # Given the analysis page
    soup = page_soup(client)
    # When we look for the Pull Data button by its test id
    button = soup.select_one('[data-testid="pull-data-btn"]')
    # Then it exists and says Pull Data
    assert button is not None
    assert button.get_text(strip=True) == "Pull Data"


def test_page_has_update_analysis_button(client):
    # Given the analysis page
    soup = page_soup(client)
    # When we look for the Update Analysis button by its test id
    button = soup.select_one('[data-testid="update-analysis-btn"]')
    # Then it exists and says Update Analysis
    assert button is not None
    assert button.get_text(strip=True) == "Update Analysis"


def test_page_text_includes_analysis(client):
    # Given the analysis page
    # When we read its text
    text = page_soup(client).get_text()
    # Then it mentions Analysis
    assert "Analysis" in text


def test_page_text_includes_answer_label(client):
    # Given the analysis page on an empty table
    # When we read its text
    text = page_soup(client).get_text()
    # Then at least one Answer: label is shown
    assert "Answer:" in text


def test_page_shows_message_when_database_fails(make_app):
    # Given a query function that cannot reach the database
    def broken_query():
        raise RuntimeError("no database")

    client = make_app(query_fn=broken_query).test_client()
    # When we load the page
    response = client.get("/analysis")
    # Then the page still loads and explains the problem
    assert response.status_code == 200
    assert "could not be reached" in response.get_data(as_text=True)


def test_page_disables_pull_button_while_busy(app, client):
    # Given a pull in progress
    app.extensions["pull_state"].busy = True
    # When we load the page
    button = page_soup(client).select_one('[data-testid="pull-data-btn"]')
    # Then the Pull Data button is disabled
    assert button.has_attr("disabled")
