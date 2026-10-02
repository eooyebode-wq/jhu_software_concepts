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

The app reads one environment variable.

.. list-table::
   :header-rows: 1

   * - Variable
     - Purpose
   * - ``DATABASE_URL``
     - A PostgreSQL connection URL, for example
       ``postgresql://localhost:5432/gradcafe``.

Setup
------

1. Install PostgreSQL and create a database, for example ``gradcafe``.
2. Create a virtual environment and install the packages::

       python3 -m venv venv
       source venv/bin/activate
       pip install -r requirements.txt

3. Set ``DATABASE_URL`` to point at that database::

       export DATABASE_URL="postgresql://localhost:5432/gradcafe"

Running the app
-----------------

From ``module_4/src``::

    python app.py

Then open http://127.0.0.1:8080/analysis.

Running the tests
-------------------

Tests run against a separate database, never the one the app itself uses,
because every test empties the ``applicants`` table. The database name in
``DATABASE_URL`` must contain the word ``test``, or the test run refuses to
start.

From the repository root::

    export DATABASE_URL="postgresql://localhost:5432/gradcafe_test"
    pytest module_4 -m "web or buttons or analysis or db or integration"

See :doc:`testing` for what the markers mean and how the fixtures work.
