Operational Notes
===================

Busy-state policy
-------------------

Only one pull may run at a time. The state lives on a :class:`PullState`
object at ``app.extensions["pull_state"]``, not in a timer or a ``sleep()``
loop:

* ``POST /pull-data`` while a pull is running returns ``409`` with
  ``{"busy": true}`` and starts nothing.
* ``POST /update-analysis`` while a pull is running also returns ``409``
  with ``{"busy": true}`` and reads nothing.
* The flag is set the moment a pull starts and cleared as soon as it ends,
  including when it fails.

Idempotency
------------

A pull always scrapes, cleans and loads in one pass through
:func:`pull_data.run_pull`. Running it twice with the same source data is
safe: :func:`load_data.load_rows` inserts every row, or none, in a single
transaction, so a failure partway through leaves nothing behind.

Uniqueness key
----------------

The ``applicants`` table uses ``p_id`` (the id at the end of each Grad Cafe
entry's URL) as its primary key. Inserts use
``ON CONFLICT (p_id) DO NOTHING``, so an entry that is already stored is
skipped instead of duplicated, however many times it is pulled.
