Architecture
=============

The application has three layers.

Web layer
----------

``app.py`` builds the Flask app through a :func:`create_app` factory. It
serves the analysis page and two JSON endpoints, ``/pull-data`` and
``/update-analysis``. It holds no data of its own; every request asks the
ETL/DB layer for the current analysis or asks it to run a pull.

ETL layer
----------

``scrape.py`` reads pages from The Grad Cafe through a Chrome window that is
already open and past the site's Cloudflare check. ``clean.py`` turns the raw
scraped records into the applicant_data schema. ``pull_data.py`` ties the two
together: it finds which entries are already stored, scrapes only the newer
ones, cleans them, and hands the rows to the DB layer.

DB layer
---------

``models.py`` defines the ``Applicant`` SQLAlchemy model and opens sessions
against ``DATABASE_URL``. ``load_data.py`` creates the ``applicants`` table
and inserts rows, skipping any whose ``p_id`` is already stored. ``query_data.py``
and ``orm_queries.py`` answer the analysis questions, in raw SQL and in
SQLAlchemy. ``app.py`` calls the SQLAlchemy versions to build the page.

Request flow
-------------

A Pull Data click runs, inside the request, in this order: scrape new
records, clean them, then load them in one transaction. If any step fails,
nothing is written and the busy flag is cleared. See
:doc:`operational_notes` for how the busy state and the uniqueness policy
work.
