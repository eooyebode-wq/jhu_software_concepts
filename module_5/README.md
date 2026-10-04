# Module 5 - Software Assurance and Security

## Name

Emmanuel Oyebode, JHED ID: eooyebod1

## What this project does

This is Module 4's Grad Cafe database, SQL analysis and Flask app, hardened
against SQL injection and set up so it can be installed and checked the same
way on any machine. It adds safe SQL composition with a row limit on every
query, database credentials from environment variables, a least-privilege
database user, Pylint at 10/10, a dependency graph, a Snyk scan, and a GitHub
Actions workflow that runs all of it.

## Layout

```
module_5/
  src/                    application code (Flask app, ETL, database, queries)
  tests/                  the whole pytest suite, including SQL injection tests
  db/                     schema.sql and least_privilege.sql
  docs/                   Sphinx project (source)
  llm_hosting/            local LLM server used by the cleaning step
  dependency.svg          dependency graph made with pydeps
  snyk-analysis.png       screenshot of snyk test
  snyk-code-analysis.txt  output of snyk code test
  pylint_report.txt       final Pylint output (10.00/10)
  coverage_summary.txt    output of the last test run
  module_5_report.pdf     written report
  .env.example            names of the environment variables
  pytest.ini
  requirements.txt
  setup.py
```

The workflow file is `.github/workflows/ci.yml` at the repository root.

## Fresh Install

Run these from the `module_5` folder. `requirements.txt` lists every package
with an exact version, so both methods build the same environment. The
`pip install -e .` step uses `setup.py` to install the project's modules, so
imports work from any folder.

### With pip and venv

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### With uv

Install uv first if you do not have it (`pip install uv`, or see
https://docs.astral.sh/uv/getting-started/installation/). Then:

```bash
uv venv
source .venv/bin/activate
uv pip sync requirements.txt
uv pip install -e .
```

`uv pip sync` makes the environment match `requirements.txt` exactly, and
removes anything not listed. `uv pip install -r requirements.txt` also works
if you only want to add the listed packages.

## Database setup

1. Install PostgreSQL and create a database, for example `gradcafe`.
2. As an admin account, create the table and the restricted user:

   ```bash
   psql -d gradcafe -f db/schema.sql
   psql -d gradcafe -f db/least_privilege.sql
   ```

3. In `psql`, set the user's password so it never lands in a file:

   ```
   \password gradcafe_app
   ```

`gradcafe_app` can connect, read `applicants` and add rows to it. It is not
a superuser and cannot update, delete, create, drop or alter anything. The
app does not create tables, so step 2 must be done first.

## Environment variables

The app and the tests read the database settings from five environment
variables. No credentials are stored in the code.

| Variable | Meaning |
| --- | --- |
| `DB_HOST` | database host, for example `localhost` |
| `DB_PORT` | database port, for example `5432` |
| `DB_NAME` | database name |
| `DB_USER` | database user, for example `gradcafe_app` |
| `DB_PASSWORD` | that user's password |

Copy `.env.example` to `.env` and fill in the values. The app reads `.env`
automatically. Variables already set in the shell take priority over the
file. `.env` is listed in `.gitignore` and must never be committed.

## Running the app

From `module_5/src`, with `.env` filled in:

```bash
python app.py
```

Then open http://127.0.0.1:8080/analysis.

## Running the tests

The tests use a **separate** database from the one the app runs against,
because every test starts by emptying the `applicants` table. `DB_NAME` must
contain the word `test`, or the test run refuses to start. The test user
needs to own the test database, so use your own admin account there, not
`gradcafe_app`.

From `module_5/`:

```bash
export DB_HOST=localhost DB_PORT=5432 DB_NAME=gradcafe_test
export DB_USER=your_admin_user DB_PASSWORD=your_password
pytest -m "web or buttons or analysis or db or integration"
```

`pytest.ini` requires 100% coverage of `src`. The output of the last run is
saved in `coverage_summary.txt`. The SQL injection tests are in
`tests/test_sql_injection.py`.

## SQL safety

- Table and column names are added with `sql.Identifier`.
- Values are passed as `%s` parameters, never joined into the SQL text.
- Each statement is built first and run separately with
  `cursor.execute(stmt, params)`.
- Every query has a `LIMIT`. `clamp_limit` in `src/sql_utils.py` keeps any
  requested limit between 1 and 100.

## Security tools

### Pylint

Run from `module_5/`. Only `src` is checked:

```bash
pylint src
```

The final result is saved in `pylint_report.txt`: 10.00/10. CI runs
`pylint src --fail-under=10`.

### Dependency graph

Graphviz must be installed (`brew install graphviz` on a Mac). From
`module_5/`:

```bash
pydeps src/app.py --noshow -T svg -o dependency.svg
```

### Snyk

Install the Snyk CLI (`brew tap snyk/tap && brew install snyk-cli`) and run
`snyk auth` once. From `module_5/`, with the virtual environment active:

```bash
snyk test --file=requirements.txt --package-manager=pip
snyk code test src
```

`snyk test` found no vulnerable dependencies (`snyk-analysis.png`).
`snyk code test` found three low-severity path findings from command-line
arguments, saved in `snyk-code-analysis.txt`.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request with four
jobs: Pylint, dependency graph, Snyk and Pytest. The Snyk job needs a
repository secret named `SNYK_TOKEN`.

## Documentation

Full documentation, including setup, architecture, the API reference, and
the testing guide, is built with Sphinx and published on Read the Docs:

https://eooyebode-jhu-software-concepts.readthedocs.io/en/latest/

To build the Module 5 copy locally, from `module_5/`:

```bash
cd docs
sphinx-build -b html source build/html
```
