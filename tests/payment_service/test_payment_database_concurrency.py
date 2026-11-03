from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.payment_service.models.otpModel import OtpModel
from backend.payment_service.models.transactionModel import TransactionModel


def create_database(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'payment-concurrency.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE transactions (
                transaction_id TEXT PRIMARY KEY,
                payer_user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                completed_at DATETIME NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE otps (
                otp_id INTEGER PRIMARY KEY,
                is_used BOOLEAN NOT NULL DEFAULT FALSE,
                expires_at DATETIME NOT NULL
            )
        """))
        connection.execute(text("""
            INSERT INTO transactions (transaction_id, payer_user_id, status)
            VALUES ('race-tx', 7, 'PENDING')
        """))
        connection.execute(
            text("INSERT INTO otps (otp_id, is_used, expires_at) VALUES (1, FALSE, :expires_at)"),
            {"expires_at": datetime.now() + timedelta(minutes=5)},
        )
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_transaction_processing_claim_is_atomic(tmp_path):
    engine, session_factory = create_database(tmp_path)
    barrier = Barrier(2)

    def claim():
        with session_factory() as session:
            barrier.wait()
            return TransactionModel.claim_for_processing(session, "race-tx", 7)

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(executor.map(lambda _: claim(), range(2)))

    assert sorted(claimed) == [False, True]
    with session_factory() as session:
        status = session.execute(
            text("SELECT status FROM transactions WHERE transaction_id = 'race-tx'")
        ).scalar_one()
    assert status == "PROCESSING"
    engine.dispose()


def test_stale_processing_transaction_requires_reconciliation(tmp_path):
    engine, session_factory = create_database(tmp_path)
    stale_started_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(tzinfo=None)
    with session_factory() as session:
        session.execute(
            text("UPDATE transactions SET status='PROCESSING', completed_at=:started_at WHERE transaction_id='race-tx'"),
            {"started_at": stale_started_at},
        )
        session.commit()
        updated = TransactionModel.mark_stale_processing_for_reconciliation(
            session,
            transaction_id="race-tx",
        )
        assert updated == 1

    with session_factory() as session:
        transaction = session.execute(
            text("SELECT status, completed_at FROM transactions WHERE transaction_id='race-tx'")
        ).one()
    assert transaction.status == "RECONCILIATION_REQUIRED"
    assert transaction.completed_at is None
    engine.dispose()


def test_otp_consume_is_atomic_and_one_time(tmp_path):
    engine, session_factory = create_database(tmp_path)
    barrier = Barrier(2)

    def consume():
        with session_factory() as session:
            barrier.wait()
            return OtpModel.mark_as_used(session, 1)

    with ThreadPoolExecutor(max_workers=2) as executor:
        consumed = list(executor.map(lambda _: consume(), range(2)))

    assert sorted(consumed) == [False, True]
    with session_factory() as session:
        is_used = session.execute(text("SELECT is_used FROM otps WHERE otp_id = 1")).scalar_one()
    assert is_used in (True, 1)
    engine.dispose()
