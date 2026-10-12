from datetime import date

from sqlmodel import Session, select

from app.db import engine
from app.models import Provider, Visit
from app.seed import make_npi, npi_check_digit, npi_is_valid, seed


def test_npi_check_digit_matches_cms_example():
    # CMS's published example: base 123456789 -> check digit 3.
    assert npi_check_digit("123456789") == "3"
    assert npi_is_valid("1234567893")
    assert not npi_is_valid("1234567890")


def test_seed_is_idempotent_and_synthetic():
    first = seed(today=date(2026, 10, 9))
    second = seed(today=date(2026, 10, 9))
    assert first == second

    with Session(engine) as s:
        providers = s.exec(select(Provider)).all()
        visits = s.exec(select(Visit)).all()

    assert len(providers) == 17
    assert len(visits) == 7
    assert all(p.ssn.startswith("9") and len(p.ssn) == 9 for p in providers)
    assert all(npi_is_valid(p.npi) for p in providers)
    assert len({p.npi for p in providers}) == 17
    assert all(v.scheduled_at.date() == date(2026, 10, 9) for v in visits)


def test_seed_contains_deliberate_test_cases():
    seed()
    with Session(engine) as s:
        by_last = {p.last_name: p for p in s.exec(select(Provider)).all()}
    assert "Garcia" in by_last["Thompson"].aliases
    assert "-" in by_last["Garcia-Lopez"].last_name
    assert by_last["Kowalski"].first_name == "Robert"
    assert "Apt" in by_last["Okafor"].street


def test_make_npi_is_ten_digits():
    assert len(make_npi("100000037")) == 10


def test_stale_schema_is_rebuilt(tmp_path, monkeypatch):
    """An old local database missing a new column is rebuilt instead of crashing on startup."""
    from sqlalchemy import create_engine, text

    import app.db as db

    old = create_engine(f"sqlite:///{tmp_path}/old.db")
    with old.begin() as conn:
        conn.execute(text("CREATE TABLE visit (id INTEGER PRIMARY KEY, provider_id INTEGER, scheduled_at DATETIME, "
                          "site_address VARCHAR, status VARCHAR)"))
    monkeypatch.setattr(db, "engine", old)
    assert db._schema_is_stale()
    db.init_db()
    assert not db._schema_is_stale()
