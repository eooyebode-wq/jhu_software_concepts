"""SQLAlchemy model for the applicants table, plus engine and session helpers."""

import functools
from datetime import date

from sqlalchemy import Date, Float, Integer, Text, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from db_config import get_database_url


# SQLAlchemy models only describe columns, so they have no public methods.
class Base(DeclarativeBase):  # pylint: disable=too-few-public-methods
    """Parent class for every model."""


class Applicant(Base):  # pylint: disable=too-few-public-methods
    """One row of the existing applicants table (made by load_data.py)."""

    __tablename__ = "applicants"

    p_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    program: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)
    date_added: Mapped[date | None] = mapped_column(Date)
    url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    term: Mapped[str | None] = mapped_column(Text)
    us_or_international: Mapped[str | None] = mapped_column(Text)
    gpa: Mapped[float | None] = mapped_column(Float)
    gre: Mapped[float | None] = mapped_column(Float)
    gre_v: Mapped[float | None] = mapped_column(Float)
    gre_aw: Mapped[float | None] = mapped_column(Float)
    degree: Mapped[str | None] = mapped_column(Text)
    llm_generated_program: Mapped[str | None] = mapped_column(Text)
    llm_generated_university: Mapped[str | None] = mapped_column(Text)


@functools.lru_cache(maxsize=None)
def get_engine(database_url):
    """Build one engine per database URL and reuse it.

    Args:
        database_url: A postgresql:// URL.

    Returns:
        A SQLAlchemy engine that uses the psycopg driver.
    """
    url = make_url(database_url).set(drivername="postgresql+psycopg")
    return create_engine(url)


def get_session(database_url=None):
    """Open a session on the database.

    Args:
        database_url: Optional URL that replaces the DB_* variables, used by tests.

    Returns:
        A new SQLAlchemy session.
    """
    return Session(get_engine(database_url or get_database_url()))
