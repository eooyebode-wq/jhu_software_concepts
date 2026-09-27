Testing Guide
==============

Running the tests
-------------------

From the repository root, with ``DATABASE_URL`` pointing at a database whose
name contains ``test``::

    pytest module_4 -m "web or buttons or analysis or db or integration"

This is the exact command CI runs, and it is required to hit 100% coverage
of ``module_4/src``, per ``module_4/pytest.ini``.

Markers
--------

Every test carries at least one of these markers, and every test file sets
one with a module-level ``pytestmark``:

.. list-table::
   :header-rows: 1

   * - Marker
     - Covers
   * - ``web``
     - Flask route and page rendering tests
   * - ``buttons``
     - Pull Data and Update Analysis behavior, including busy state
   * - ``analysis``
     - "Answer:" labels and two-decimal percentage formatting
   * - ``db``
     - Database schema, inserts, selects, and the ETL scripts
   * - ``integration``
     - End-to-end flows: pull, update, then render

Run one group on its own, for example ``pytest module_4 -m buttons``.

Selectors
----------

The two buttons on the analysis page carry stable test ids:

* ``data-testid="pull-data-btn"``
* ``data-testid="update-analysis-btn"``

Fixtures and test doubles
----------------------------

Shared fixtures live in ``module_4/tests/conftest.py``.

* ``app`` / ``client`` -- a Flask app and test client built on the test
  database, with a fake scraper already wired in.
* ``make_app`` -- builds an app with any combination of fake ``scraper``,
  ``loader`` or ``query_fn``, for tests that need a different fake.
* ``fake_scraper`` / ``fake_records`` -- seven raw Grad Cafe records, offline.
* ``recording_loader`` -- a fake loader that remembers what it was given and
  writes nothing.
* ``db_conn`` / ``seed_db`` -- a raw connection for assertions, and a helper
  that loads the fake records the same way a real pull does.
* ``clean_table`` -- runs automatically before every test and empties the
  ``applicants`` table.

Tests never touch the real Grad Cafe site, a real browser, or ``sleep()``.
Busy state is set directly on ``app.extensions["pull_state"].busy``, and
Chrome, the network, and subprocesses are replaced with fakes through
``monkeypatch``.
