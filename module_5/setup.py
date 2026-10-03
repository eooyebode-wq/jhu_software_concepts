"""Packaging for the Grad Cafe analysis project."""

from pathlib import Path

from setuptools import setup

SRC_DIR = Path(__file__).resolve().parent / "src"

setup(
    name="gradcafe-analysis",
    version="0.1.0",
    description="Flask app and SQL queries for Grad Cafe applicant data",
    package_dir={"": "src"},
    py_modules=sorted(path.stem for path in SRC_DIR.glob("*.py")),
    python_requires=">=3.10",
    install_requires=[
        "psycopg[binary]>=3.2",
        "SQLAlchemy>=2.0",
        "python-dotenv>=1.0",
        "Flask>=3.0",
        "selenium>=4.20",
        "beautifulsoup4>=4.12",
        "urllib3>=2.0",
    ],
)
