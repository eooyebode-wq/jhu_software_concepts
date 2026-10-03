# Module 4 - Testing and Documentation

## Name

Emmanuel Oyebode, JHED ID: eooyebod1

## What this project does

This is Module 3's Grad Cafe database, SQL analysis and Flask app, now with a
pytest suite, 100% test coverage, a GitHub Actions workflow, and Sphinx
documentation published on Read the Docs.

## Layout

```
module_4/
  src/      application code (Flask app, ETL, database, queries)
  tests/    the whole pytest suite
  docs/     Sphinx project (source and build)
  pytest.ini
  requirements.txt
```

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

## Setup

1. Install PostgreSQL and create a database, for example `gradcafe`.
2. Create a virtual environment and install the packages:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### Configuring PostgreSQL and DATABASE_URL

The app and the tests both read one environment variable, `DATABASE_URL`, a
standard PostgreSQL connection URL:

```bash
export DATABASE_URL="postgresql://localhost:5432/gradcafe"
```

No password or other secret is stored in the code.

## Running the app

From `module_4/src`:

```bash
python app.py
```

Then open http://127.0.0.1:8080/analysis.

## Running the tests

The tests use a **separate** database from the one the app runs against,
because every test starts by emptying the `applicants` table. The database
name in `DATABASE_URL` must contain the word `test`, or the test run refuses
to start.

From the repository root:

```bash
export DATABASE_URL="postgresql://localhost:5432/gradcafe_test"
pytest module_4 -m "web or buttons or analysis or db or integration"
```

That command is what `module_4/pytest.ini` is built for, and what
`.github/workflows/tests.yml` runs in CI. It requires 100% coverage of
`module_4/src`; the terminal output from the last run is saved at
`module_4/coverage_summary.txt`.

## Documentation

Full documentation, including setup, architecture, the API reference, and
the testing guide, is built with Sphinx and published on Read the Docs:

https://eooyebode-jhu-software-concepts.readthedocs.io/en/latest/

The built HTML also lives in this repo at `module_4/docs/build/html`. To
rebuild it locally:

```bash
cd module_4/docs
../venv/bin/sphinx-build -b html source build/html
```
