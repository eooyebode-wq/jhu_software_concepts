Troubleshooting
=================

The analysis page says the database could not be reached
------------------------------------------------------------

Check that ``DB_HOST``, ``DB_PORT``, ``DB_NAME``, ``DB_USER`` and
``DB_PASSWORD`` are set and correct, and that PostgreSQL is running and
accepting connections on that host and port.

Tests exit immediately with "Set these environment variables"
---------------------------------------------------------------------------

The test suite refuses to run unless all five ``DB_*`` variables are set.
Export them before running pytest. The message names the missing ones.

Tests exit immediately about the database name needing "test"
------------------------------------------------------------------

Every test empties the ``applicants`` table, so the suite refuses to run
against a database whose name does not contain ``test``. Point
``DB_NAME`` at a separate database, for example ``gradcafe_test``, not
the one the app itself uses.

Coverage fails under 100%
---------------------------

``pytest.ini`` sets ``--cov-fail-under=100``. Run
``pytest --cov-report=term-missing`` to see exactly which lines in
``src`` were not hit, and add a test for that case.

Pull Data fails with a Chrome message
----------------------------------------

Pull Data needs Chrome open with remote debugging on port 9222, already past
the site's Cloudflare check. This only matters for a real pull; the test
suite never opens a browser.

CI fails on the Postgres service container
----------------------------------------------

The GitHub Actions workflow waits on the Postgres container's health check
before running the tests. If it still fails, check that
the ``DB_*`` variables in ``.github/workflows/ci.yml`` match the service's
``POSTGRES_USER``, ``POSTGRES_PASSWORD`` and ``POSTGRES_DB`` values.
