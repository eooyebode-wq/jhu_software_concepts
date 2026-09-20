"""SQLAlchemy model for the applicants table, plus the engine and session."""

from datetime import date

from sqlalchemy import Date, Float, Integer, Text, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from db_config import get_settings


class Base(DeclarativeBase):
    """Parent class for every model."""


class Applicant(Base):
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


def make_engine():
    """Build the engine from the same environment settings load_data.py uses."""
    settings = get_settings()
    url = URL.create(
        "postgresql+psycopg",
        username=settings.get("user"),
        password=settings.get("password"),
        host=settings["host"],
        port=int(settings["port"]),
        database=settings["dbname"],
    )
    return create_engine(url)


engine = make_engine()
Session = sessionmaker(engine)
