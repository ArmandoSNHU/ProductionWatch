"""Seeds a small set of synthetic accounts and transactions.

Names are obviously fictional aliases and references use a DEMO- prefix so
nobody mistakes this data for real customer information.
"""
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Transaction

SEED_ACCOUNTS = [
    ("DEMO-CHK-0001", "Test Member Alpha", "checking", Decimal("4210.55")),
    ("DEMO-SAV-0002", "Test Member Alpha", "savings", Decimal("15890.00")),
    ("DEMO-CHK-0003", "Test Member Bravo", "checking", Decimal("982.17")),
    ("DEMO-CRD-0004", "Test Member Charlie", "credit", Decimal("-640.29")),
    ("DEMO-SAV-0005", "Test Member Delta", "savings", Decimal("7320.40")),
]

SEED_TRANSACTIONS = [
    ("Payroll deposit (synthetic)", "income", Decimal("2150.00")),
    ("Grocery store (synthetic)", "groceries", Decimal("-86.42")),
    ("Fuel station (synthetic)", "auto", Decimal("-48.10")),
    ("Utility bill (synthetic)", "utilities", Decimal("-132.75")),
    ("Transfer to savings (synthetic)", "transfer", Decimal("-300.00")),
    ("Online retailer (synthetic)", "shopping", Decimal("-57.99")),
    ("Insurance premium (synthetic)", "insurance", Decimal("-118.00")),
    ("Interest credit (synthetic)", "income", Decimal("4.12")),
]


def seed_database(session: Session) -> int:
    """Insert seed data if the accounts table is empty. Returns accounts created."""
    if session.scalar(select(Account.id).limit(1)) is not None:
        return 0

    rng = random.Random(42)  # fixed seed keeps demos and tests repeatable
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for reference, alias, account_type, balance in SEED_ACCOUNTS:
        account = Account(
            reference=reference, holder_alias=alias, account_type=account_type, balance=balance
        )
        session.add(account)
        for day in range(8):
            description, category, amount = rng.choice(SEED_TRANSACTIONS)
            account.transactions.append(
                Transaction(
                    posted_at=now - timedelta(days=day, hours=rng.randint(0, 12)),
                    description=description,
                    category=category,
                    amount=amount,
                )
            )
    session.commit()
    return len(SEED_ACCOUNTS)
