Troubleshooting
=================

The analysis page says the database could not be reached
------------------------------------------------------------

Check that ``DATABASE_URL`` is set and that PostgreSQL is running and
accepting connections on that host and port.

Tests exit immediately with "Set DATABASE_URL to a test database first"
---------------------------------------------------------------------------

The test suite refuses to run without ``DATABASE_URL`` set. Export it before
running pytest.

Tests exit immediately about the database name needing "test"
------------------------------------------------------------------

Every test empties the ``applicants`` table, so the suite refuses to run
against a database whose name does not contain ``test``. Point
``DATABASE_URL`` at a separate database, for example ``gradcafe_test``, not
the one the app itself uses.

Coverage fails under 100%
---------------------------

``module_4/pytest.ini`` sets ``--cov-fail-under=100``. Run
``pytest --cov-report=term-missing`` to see exactly which lines in
``module_4/src`` were not hit, and add a test for that case.

Pull Data fails with a Chrome message
----------------------------------------

Pull Data needs Chrome open with remote debugging on port 9222, already past
the site's Cloudflare check. This only matters for a real pull; the test
suite never opens a browser.

CI fails on the Postgres service container
----------------------------------------------

The GitHub Actions workflow waits on the Postgres container's health check
before running the tests. If it still fails, check that
``DATABASE_URL`` in ``.github/workflows/tests.yml`` matches the service's
``POSTGRES_USER``, ``POSTGRES_PASSWORD`` and ``POSTGRES_DB`` values.
