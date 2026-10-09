"""Seed the database with synthetic providers and today's site visits.

    python -m app.seed

Idempotent: drops and recreates all tables. All people are fictional. SSNs start with 9 (never issued by the
SSA) and NPIs are made-up numbers that pass the NPI check-digit rule. If DEMO_PROVIDER_* is set in .env, one extra
provider is created from it (the candidate's own wallet identity, for the live digital demo) and gets the first
visit of the day. That record exists only in the local/Render database, never in the repo (ADR-0004).
"""
from datetime import date, datetime, time

from sqlmodel import Session, SQLModel

from app.config import settings
from app.db import engine
from app.models import Provider, Visit


def npi_check_digit(base9: str) -> str:
    """Luhn check digit for an NPI: computed over the prefix 80840 + the first 9 digits (CMS rule)."""
    digits = [int(c) for c in "80840" + base9]
    total = 0
    # Double every second digit starting from the rightmost payload digit.
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def make_npi(base9: str) -> str:
    return base9 + npi_check_digit(base9)


def npi_is_valid(npi: str) -> bool:
    return len(npi) == 10 and npi.isdigit() and npi_check_digit(npi[:9]) == npi[9]


# (first, last, aliases, dob, ssn, street, city, zip5, specialty, risk)
# Deliberate test cases are marked; see tasks/todo.md T03.
PROVIDERS = [
    ("Robert", "Kowalski", [], "1971-04-12", "900112233", "214 N Main St", "St. Charles", "63301",
     "Durable medical equipment", "high"),  # "Bob" nickname case
    ("Jennifer", "Thompson", ["Garcia"], "1983-09-27", "900223344", "1550 Zumbehl Rd", "St. Charles", "63303",
     "Home health agency", "high"),  # maiden-name alias case
    ("Maria", "Garcia-Lopez", [], "1979-02-03", "900334455", "88 Mid Rivers Mall Dr", "St. Peters", "63376",
     "Behavioral health", "moderate"),  # hyphenated last name case
    ("Daniel", "Okafor", [], "1985-07-03", "900445566", "3020 W Clay St Apt 4B", "St. Charles", "63301",
     "Physical therapy", "moderate"),  # apartment address + DOB swap case (07-03 vs 03-07)
    ("Priya", "Raman", [], "1990-11-19", "900556677", "4120 Old Hwy 94 S", "St. Charles", "63304",
     "Applied behavior analysis", "moderate"),
    ("Thomas", "Nguyen", [], "1968-05-30", "900667788", "701 Salt Lick Rd", "St. Peters", "63376",
     "Pharmacy", "moderate"),
    ("Angela", "Brooks", [], "1975-12-08", "900778899", "29 Jungermann Rd", "St. Peters", "63376",
     "Hospice", "moderate"),
    ("William", "Schneider", [], "1962-01-25", "900889900", "1200 Hwy K", "O'Fallon", "63366",
     "Ambulance services", "moderate"),
    ("Fatima", "Hassan", [], "1988-06-14", "900990011", "5300 Mexico Rd", "St. Peters", "63376",
     "Community mental health center", "moderate"),
    ("Kevin", "O'Brien", [], "1980-03-21", "901001122", "2440 Hwy 94 Ste 110", "St. Charles", "63303",
     "Independent diagnostic testing facility", "high"),  # apostrophe normalization case
    ("Elizabeth", "Carter", [], "1972-10-02", "901112233", "6 Kingshighway St", "St. Charles", "63301",
     "Personal care services", "high"),  # "Liz" / "Beth" nickname case
    ("Marcus", "Johnson", [], "1986-08-17", "901223344", "915 Cave Springs Blvd", "St. Peters", "63376",
     "Durable medical equipment", "high"),  # "Jonson" typo case
    ("Sofia", "Rossi", [], "1993-04-05", "901334455", "300 Main St", "O'Fallon", "63366",
     "Speech-language pathology", "limited"),
    ("James", "Whitfield", [], "1958-09-11", "901445566", "45 Triad Dr", "O'Fallon", "63366",
     "Physician group practice", "limited"),
    ("Grace", "Lee", [], "1977-01-29", "901556677", "1801 Pralle Ln", "St. Charles", "63303",
     "Federally qualified health center", "limited"),
]

# Visit times today (local time of the server; good enough for a demo schedule).
VISIT_SLOTS = [time(9, 0), time(10, 30), time(12, 0), time(13, 30), time(15, 0), time(16, 30)]
VISIT_PROVIDER_INDEXES = [0, 1, 2, 3, 9, 11]  # which seed providers get a visit today


def build_providers() -> list[Provider]:
    providers = []
    for i, (first, last, aliases, dob, ssn, street, city, zip5, specialty, risk) in enumerate(PROVIDERS):
        providers.append(
            Provider(
                npi=make_npi(f"1{(i + 1) * 37 + 400000:08d}"),
                first_name=first,
                last_name=last,
                aliases=aliases,
                dob=date.fromisoformat(dob),
                ssn=ssn,
                street=street,
                city=city,
                state="MO",
                zip5=zip5,
                specialty=specialty,
                risk_level=risk,
            )
        )
    return providers


def build_demo_provider() -> Provider | None:
    if not (settings.demo_provider_first and settings.demo_provider_last and settings.demo_provider_dob):
        return None
    try:
        dob = date.fromisoformat(settings.demo_provider_dob)
    except ValueError:
        return None
    return Provider(
        npi=make_npi("199999999"),
        first_name=settings.demo_provider_first,
        last_name=settings.demo_provider_last,
        aliases=[],
        dob=dob,
        ssn="999000000",  # synthetic; the wallet ID never carries an SSN
        street="100 Demo Way",
        city="St. Charles",
        state="MO",
        zip5="63301",
        specialty="Home health agency",
        risk_level="high",
    )


def seed(today: date | None = None) -> dict:
    today = today or date.today()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        providers = build_providers()
        session.add_all(providers)
        session.flush()  # assign ids

        visit_providers = [providers[i] for i in VISIT_PROVIDER_INDEXES]
        demo = build_demo_provider()
        if demo:
            session.add(demo)
            session.flush()
            visit_providers = [demo] + visit_providers[:-1]

        for slot, provider in zip(VISIT_SLOTS, visit_providers, strict=True):
            session.add(
                Visit(
                    provider_id=provider.id,
                    scheduled_at=datetime.combine(today, slot),
                    site_address=f"{provider.street}, {provider.city}, {provider.state} {provider.zip5}",
                )
            )
        session.commit()
        return {"providers": len(providers) + (1 if demo else 0), "visits": len(visit_providers),
                "demo_provider": bool(demo)}


def ensure_seeded() -> None:
    """Seed on startup if the database is empty (Render's free disk is wiped on every deploy)."""
    from sqlmodel import select

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if session.exec(select(Provider)).first() is None:
            seed()
        else:
            # Keep the demo schedule on "today" if the server stays up across midnight. Only the visit dates move;
            # the audit log is never touched.
            today = date.today()
            for visit in session.exec(select(Visit)).all():
                if visit.scheduled_at.date() != today:
                    visit.scheduled_at = datetime.combine(today, visit.scheduled_at.time())
                    session.add(visit)
            session.commit()


if __name__ == "__main__":
    result = seed()
    print(f"Seeded {result['providers']} providers and {result['visits']} visits for today"
          f"{' (including demo provider from .env)' if result['demo_provider'] else ''}.")
