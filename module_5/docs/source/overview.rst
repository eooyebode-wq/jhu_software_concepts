Overview & Setup
=================

What this is
-------------

Grad Cafe Analytics loads applicant data from `The Grad Cafe
<https://www.thegradcafe.com/>`_ into PostgreSQL and shows the analysis on a
Flask page. The page has a Pull Data button, which fetches newly posted
entries, and an Update Analysis button, which refreshes the results.

Environment variables
----------------------

The app reads five environment variables.

.. list-table::
   :header-rows: 1

   * - Variable
     - Purpose
   * - ``DB_HOST``
     - Database host, for example ``localhost``.
   * - ``DB_PORT``
     - Database port, for example ``5432``.
   * - ``DB_NAME``
     - Database name.
   * - ``DB_USER``
     - Database user, for example ``gradcafe_app``.
   * - ``DB_PASSWORD``
     - That user's password.

Setup
------

1. Install PostgreSQL and create a database, for example ``gradcafe``.
2. Create a virtual environment and install the packages::

       python3 -m venv venv
       source venv/bin/activate
       pip install -r requirements.txt

3. Copy ``.env.example`` to ``.env`` and fill in the five ``DB_*`` values for
   that database. ``.env`` is never committed.

Running the app
-----------------

From ``module_5/src``::

    python app.py

Then open http://127.0.0.1:8080/analysis.

Running the tests
-------------------

Tests run against a separate database, never the one the app itself uses,
because every test empties the ``applicants`` table. ``DB_NAME`` must
contain the word ``test``, or the test run refuses to
start.

From ``module_5``::

    export DB_NAME=gradcafe_test
    pytest -m "web or buttons or analysis or db or integration"

See :doc:`testing` for what the markers mean and how the fixtures work.
