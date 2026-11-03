import os
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from pathlib import Path
from urllib.parse import unquote, urlsplit

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["INTERNAL_API_KEY"] = "test-internal-key"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.user_service import database as user_database
from backend.user_service.database import Base
from backend.user_service import main as user_main
from backend.user_service.models import Account, AccountDebit, User
from backend.user_service.security import hash_password

TEST_LOGIN_PASSWORD = "test-user-login-only"


@pytest.fixture(autouse=True)
def reset_database(tmp_path, monkeypatch):
    test_db_path = Path(tmp_path) / "user_service_test.sqlite3"
    test_engine = create_engine(
        f"sqlite:///{test_db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    test_session_local = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(user_database, "engine", test_engine)
    monkeypatch.setattr(user_database, "SessionLocal", test_session_local)
    monkeypatch.setattr(user_main, "engine", test_engine)
    Base.metadata.create_all(bind=test_engine)

    @asynccontextmanager
    async def test_lifespan(_app):
        # The fixture initializes schema once; TestClient startup must not
        # concurrently call create_all() against this SQLite database.
        yield

    monkeypatch.setattr(user_main.app.router, "lifespan_context", test_lifespan)
    db = test_session_local()
    user = User(
        username="user01",
        password_hash=hash_password(TEST_LOGIN_PASSWORD),
        full_name="Nguyen Van A",
        phone="0901234567",
        email="user01@example.com",
        student_id="524H0104",
    )
    db.add(user)
    db.flush()
    db.add_all(
        [
            Account(account_number="1012345678", user_id=user.user_id, balance=Decimal("15000000"), is_default=True),
            Account(account_number="1012345679", user_id=user.user_id, balance=Decimal("5000000"), is_default=False),
            Account(account_number="1000000000", user_id=user.user_id, balance=Decimal("0"), status="INACTIVE"),
        ]
    )
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture
def client():
    with TestClient(user_main.app) as test_client:
        yield test_client


def login(client: TestClient) -> str:
    response = client.post("/api/v1/auth/login", json={"username": "user01", "password": TEST_LOGIN_PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_login_and_profile(client: TestClient):
    token = login(client)
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {
        "userId": 1,
        "username": "user01",
        "fullName": "Nguyen Van A",
        "phone": "0901234567",
        "email": "user01@example.com",
        "student_id": "524H0104",
    }
    assert "password" not in response.text
    assert "password_hash" not in response.text


def test_invalid_login_and_missing_token(client: TestClient):
    assert client.post("/api/v1/auth/login", json={"username": "user01", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "missing", "password": TEST_LOGIN_PASSWORD}).status_code == 401
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid-token"}).status_code == 401


def test_expired_jwt_is_rejected(client: TestClient):
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    token = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        "test-secret",
        algorithm="HS256",
    )
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_accounts_are_scoped_to_current_user(client: TestClient):
    db = user_database.SessionLocal()
    other_user = User(
        username="user02",
        password_hash=hash_password("other-password"),
        full_name="Nguyen Van B",
        phone="0900000000",
        email="user02@example.com",
    )
    db.add(other_user)
    db.flush()
    db.add(Account(account_number="2012345678", user_id=other_user.user_id, balance=Decimal("9000000")))
    db.commit()
    db.close()

    token = login(client)
    response = client.get("/api/v1/accounts/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert [account["accountNumber"] for account in response.json()] == ["1012345678", "1000000000", "1012345679"]
    assert "2012345678" not in response.text


def test_internal_lookup_and_debit(client: TestClient):
    headers = {"X-Internal-API-Key": "test-internal-key"}
    lookup = client.get("/api/v1/internal/accounts/1012345678", headers=headers)
    assert lookup.status_code == 200
    assert lookup.json()["balance"] == 15000000

    debit = client.post(
        "/api/v1/internal/accounts/1012345678/debit",
        headers=headers,
        json={"amount": 8500000, "transactionId": "TX-001"},
    )
    assert debit.status_code == 200
    assert debit.json() == {"success": True, "accountNumber": "1012345678", "remainingBalance": 6500000}


def test_internal_key_rejects_missing_and_invalid_values(client: TestClient):
    for headers in ({}, {"X-Internal-API-Key": "wrong-key"}):
        response = client.get("/api/v1/internal/accounts/1012345678", headers=headers)
        assert response.status_code == 401

    valid = client.get(
        "/api/v1/internal/accounts/1012345678",
        headers={"X-Internal-API-Key": "test-internal-key"},
    )
    missing_account = client.get(
        "/api/v1/internal/accounts/missing",
        headers={"X-Internal-API-Key": "test-internal-key"},
    )
    assert valid.status_code == 200
    assert missing_account.status_code == 404


def test_duplicate_debit_returns_original_result_without_debiting_again(client: TestClient):
    headers = {"X-Internal-API-Key": "test-internal-key"}
    payload = {"amount": "5000000.00", "transactionId": "RETRY-001"}

    first = client.post("/api/v1/internal/accounts/1012345678/debit", headers=headers, json=payload)
    retry = client.post("/api/v1/internal/accounts/1012345678/debit", headers=headers, json=payload)

    assert first.status_code == retry.status_code == 200
    assert first.json() == retry.json()
    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    debit_records = db.query(AccountDebit).filter_by(transaction_id="RETRY-001").all()
    assert account.balance == Decimal("10000000")
    assert len(debit_records) == 1
    db.close()


@pytest.mark.parametrize(
    "account_number, amount",
    [("1012345678", "4000000.00"), ("1012345679", "5000000.00")],
)
def test_duplicate_transaction_with_different_debit_is_rejected(client, account_number, amount):
    headers = {"X-Internal-API-Key": "test-internal-key"}
    first = client.post(
        "/api/v1/internal/accounts/1012345678/debit",
        headers=headers,
        json={"amount": "5000000.00", "transactionId": "CONFLICT-001"},
    )
    conflicting = client.post(
        f"/api/v1/internal/accounts/{account_number}/debit",
        headers=headers,
        json={"amount": amount, "transactionId": "CONFLICT-001"},
    )

    assert first.status_code == 200
    assert conflicting.status_code == 409

    db = user_database.SessionLocal()
    first_account = db.get(Account, "1012345678")
    second_account = db.get(Account, "1012345679")
    assert first_account is not None
    assert second_account is not None
    assert first_account.balance == Decimal("10000000")
    assert second_account.balance == Decimal("5000000")
    assert db.query(AccountDebit).filter_by(transaction_id="CONFLICT-001").count() == 1
    db.close()


def test_debit_record_failure_rolls_back_balance(client, monkeypatch):
    from sqlalchemy.orm import Session

    original_add = Session.add

    def fail_for_debit_record(self, instance, *_args, **_kwargs):
        if isinstance(instance, AccountDebit):
            raise RuntimeError("simulated debit record failure")
        return original_add(self, instance, *_args, **_kwargs)

    monkeypatch.setattr(Session, "add", fail_for_debit_record)
    with TestClient(user_main.app, raise_server_exceptions=False) as isolated_client:
        response = isolated_client.post(
            "/api/v1/internal/accounts/1012345678/debit",
            headers={"X-Internal-API-Key": "test-internal-key"},
            json={"amount": "5000000.00", "transactionId": "ROLLBACK-001"},
        )

    assert response.status_code == 500
    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    assert account.balance == Decimal("15000000")
    assert db.get(AccountDebit, "ROLLBACK-001") is None
    db.close()


@pytest.mark.parametrize(
    ("stage", "error_code"),
    [
        ("flush", 1213),
        ("flush", 1205),
        ("update", 1213),
        ("update", 1205),
    ],
)
def test_mysql_lock_errors_return_service_unavailable_and_rollback(
    client, monkeypatch, stage, error_code
):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session
    from sqlalchemy.sql.dml import Update

    original_flush = Session.flush
    original_execute = Session.execute
    original_rollback = Session.rollback
    rollback_calls = []

    def lock_error(statement):
        return OperationalError(
            statement,
            {},
            Exception(error_code, "simulated database lock error"),
        )

    def fail_debit_flush(self, objects=None):
        if stage == "flush" and any(
            isinstance(instance, AccountDebit) for instance in self.new
        ):
            raise lock_error("INSERT INTO account_debits")
        return original_flush(self, objects)

    def fail_account_update(self, statement, *args, **kwargs):
        if (
            stage == "update"
            and isinstance(statement, Update)
            and statement.table.name == "accounts"
        ):
            raise lock_error(statement)
        return original_execute(self, statement, *args, **kwargs)

    def track_rollback(self):
        rollback_calls.append(True)
        return original_rollback(self)

    monkeypatch.setattr(Session, "flush", fail_debit_flush)
    monkeypatch.setattr(Session, "execute", fail_account_update)
    monkeypatch.setattr(Session, "rollback", track_rollback)

    with TestClient(user_main.app, raise_server_exceptions=False) as isolated_client:
        response = isolated_client.post(
            "/api/v1/internal/accounts/1012345678/debit",
            headers={"X-Internal-API-Key": "test-internal-key"},
            json={"amount": "5000000.00", "transactionId": f"LOCK-{stage}-{error_code}"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "DEBIT_ROLLED_BACK",
            "message": (
                "Database is temporarily unavailable; debit was rolled back. "
                "Retry with the same transaction ID"
            ),
        }
    }
    assert rollback_calls
    assert "simulated database lock error" not in response.text

    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    assert account.balance == Decimal("15000000")
    assert db.get(AccountDebit, f"LOCK-{stage}-{error_code}") is None
    db.close()


def test_rollback_failure_returns_unknown_debit_outcome(client, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session
    from sqlalchemy.sql.dml import Update

    original_execute = Session.execute
    original_rollback = Session.rollback
    rollback_attempts = []

    def fail_account_update(self, statement, *args, **kwargs):
        if isinstance(statement, Update) and statement.table.name == "accounts":
            raise OperationalError(
                statement,
                {},
                Exception(1213, "simulated database lock error"),
            )
        return original_execute(self, statement, *args, **kwargs)

    def fail_first_rollback(self):
        rollback_attempts.append(True)
        if len(rollback_attempts) == 1:
            raise OperationalError(
                "ROLLBACK",
                {},
                Exception(2013, "simulated rollback connection failure"),
            )
        return original_rollback(self)

    monkeypatch.setattr(Session, "execute", fail_account_update)
    monkeypatch.setattr(Session, "rollback", fail_first_rollback)

    response = client.post(
        "/api/v1/internal/accounts/1012345678/debit",
        headers={"X-Internal-API-Key": "test-internal-key"},
        json={"amount": "5000000.00", "transactionId": "ROLLBACK-UNKNOWN-001"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "DEBIT_OUTCOME_UNKNOWN",
            "message": (
                "Debit outcome could not be confirmed; reconcile before retrying with the "
                "same transaction ID"
            ),
        }
    }
    assert rollback_attempts
    assert "simulated" not in response.text

    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    assert account.balance == Decimal("15000000")
    assert db.get(AccountDebit, "ROLLBACK-UNKNOWN-001") is None
    db.close()


def test_refresh_failure_after_commit_returns_committed_debit(client, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    def fail_refresh(self, instance, *args, **kwargs):
        raise OperationalError(
            "SELECT account",
            {},
            Exception(1213, "simulated post-commit refresh failure"),
        )

    monkeypatch.setattr(Session, "refresh", fail_refresh)
    response = client.post(
        "/api/v1/internal/accounts/1012345678/debit",
        headers={"X-Internal-API-Key": "test-internal-key"},
        json={"amount": "5000000.00", "transactionId": "REFRESH-FAIL-001"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "accountNumber": "1012345678",
        "remainingBalance": 10000000,
    }

    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    assert account.balance == Decimal("10000000")
    assert db.query(AccountDebit).filter_by(
        transaction_id="REFRESH-FAIL-001"
    ).count() == 1
    db.close()


def test_commit_error_returns_unknown_and_retry_is_idempotent(client, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session

    original_commit = Session.commit

    def commit_then_lose_ack(self):
        original_commit(self)
        raise OperationalError(
            "COMMIT",
            {},
            Exception(2013, "simulated lost commit acknowledgement"),
        )

    monkeypatch.setattr(Session, "commit", commit_then_lose_ack)
    payload = {"amount": "5000000.00", "transactionId": "COMMIT-UNKNOWN-001"}
    headers = {"X-Internal-API-Key": "test-internal-key"}
    uncertain = client.post(
        "/api/v1/internal/accounts/1012345678/debit",
        headers=headers,
        json=payload,
    )

    assert uncertain.status_code == 503
    assert uncertain.json() == {
        "detail": {
            "code": "DEBIT_OUTCOME_UNKNOWN",
            "message": (
                "Debit outcome could not be confirmed; reconcile before retrying with the "
                "same transaction ID"
            ),
        }
    }

    retry = client.post(
        "/api/v1/internal/accounts/1012345678/debit",
        headers=headers,
        json=payload,
    )
    assert retry.status_code == 200
    assert retry.json()["remainingBalance"] == 10000000

    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    assert account.balance == Decimal("10000000")
    assert db.query(AccountDebit).filter_by(
        transaction_id="COMMIT-UNKNOWN-001"
    ).count() == 1
    db.close()


def test_debit_rejects_invalid_cases(client: TestClient):
    headers = {"X-Internal-API-Key": "test-internal-key"}
    assert client.post("/api/v1/internal/accounts/missing/debit", headers=headers, json={"amount": 1, "transactionId": "TX"}).status_code == 404
    assert client.post("/api/v1/internal/accounts/1000000000/debit", headers=headers, json={"amount": 1, "transactionId": "TX"}).status_code == 409
    assert client.post("/api/v1/internal/accounts/1012345678/debit", headers=headers, json={"amount": 999999999, "transactionId": "TX"}).status_code == 409
    assert client.post("/api/v1/internal/accounts/1012345678/debit", headers=headers, json={"amount": 0, "transactionId": "TX"}).status_code == 422
    assert client.post("/api/v1/internal/accounts/1012345678/debit", headers=headers, json={"amount": -1, "transactionId": "TX-NEG"}).status_code == 422
    assert client.post("/api/v1/internal/accounts/1012345678/debit", headers=headers, json={"amount": "1.001", "transactionId": "TX-SCALE"}).status_code == 422
    assert client.post("/api/v1/internal/accounts/1012345678/debit", headers=headers, json={"amount": "10000000000000.00", "transactionId": "TX-LIMIT"}).status_code == 422
    assert client.post("/api/v1/internal/accounts/1012345678/debit", json={"amount": 1, "transactionId": "TX"}).status_code == 401


def test_concurrent_debits_allow_only_one_success(client):
    headers = {"X-Internal-API-Key": "test-internal-key"}

    def debit_once():
        with TestClient(user_main.app) as concurrent_client:
            response = concurrent_client.post(
                "/api/v1/internal/accounts/1012345678/debit",
                headers=headers,
                json={
                    "amount": 8000000,
                    "transactionId": f"CONCURRENT-DISTINCT-{os.urandom(4).hex()}",
                },
            ).status_code
            return response

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: debit_once(), range(2)))

    assert sorted(statuses) == [200, 409]
    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    assert account.balance == Decimal("7000000")
    db.close()


def test_concurrent_retries_with_same_transaction_debit_once(client):
    headers = {"X-Internal-API-Key": "test-internal-key"}

    def debit_once():
        with TestClient(user_main.app) as concurrent_client:
            return concurrent_client.post(
                "/api/v1/internal/accounts/1012345678/debit",
                headers=headers,
                json={"amount": "5000000.00", "transactionId": "CONCURRENT-SAME"},
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: debit_once(), range(2)))

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    assert account.balance == Decimal("10000000")
    assert db.query(AccountDebit).filter_by(transaction_id="CONCURRENT-SAME").count() == 1
    db.close()


def test_concurrent_same_transaction_retries_succeed_when_balance_covers_one_debit(client):
    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    account.balance = Decimal("5000000")
    db.commit()
    db.close()

    headers = {"X-Internal-API-Key": "test-internal-key"}

    def debit_once():
        with TestClient(user_main.app) as concurrent_client:
            return concurrent_client.post(
                "/api/v1/internal/accounts/1012345678/debit",
                headers=headers,
                json={"amount": "5000000.00", "transactionId": "CONCURRENT-EXACT"},
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: debit_once(), range(2)))

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    assert account.balance == Decimal("0")
    assert db.query(AccountDebit).filter_by(transaction_id="CONCURRENT-EXACT").count() == 1
    db.close()


def test_concurrent_700k_debits_from_1m_account_never_overdraw(client):
    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    account.balance = Decimal("1000000")
    db.commit()
    db.close()

    headers = {"X-Internal-API-Key": "test-internal-key"}

    def debit_once(index):
        with TestClient(user_main.app) as concurrent_client:
            return concurrent_client.post(
                "/api/v1/internal/accounts/1012345678/debit",
                headers=headers,
                json={"amount": 700000, "transactionId": f"RACE-{index}"},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(debit_once, range(2)))

    assert sorted(statuses) == [200, 409]
    db = user_database.SessionLocal()
    account = db.get(Account, "1012345678")
    assert account is not None
    assert account.balance == Decimal("300000")
    assert account.balance >= 0
    db.close()


def _mysql_test_database_url() -> str:
    """Require the dedicated ibanking_account_db_test database."""
    database_url = os.getenv("USER_SERVICE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set USER_SERVICE_TEST_DATABASE_URL to an isolated MySQL test database")

    parsed = urlsplit(database_url)
    database_name = unquote(parsed.path.lstrip("/"))
    if parsed.scheme not in {"mysql", "mysql+pymysql"}:
        pytest.skip("USER_SERVICE_TEST_DATABASE_URL must use MySQL with PyMySQL")
    if database_name.lower() != "ibanking_account_db_test":
        pytest.skip("MySQL concurrency tests require the exact database name ibanking_account_db_test")
    return database_url


@pytest.fixture
def mysql_concurrency_database(monkeypatch):
    """Build an isolated MySQL engine without changing the app's SQLite engine."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    database_url = _mysql_test_database_url()
    test_engine = create_engine(database_url, pool_pre_ping=True)
    if test_engine.dialect.name != "mysql":
        test_engine.dispose()
        pytest.skip("Configured test URL did not create a MySQL engine")

    # Verify server-side identity before schema creation or row mutation.
    with test_engine.connect() as connection:
        actual_database = connection.execute(text("SELECT DATABASE()")).scalar_one_or_none()
    if actual_database != "ibanking_account_db_test":
        test_engine.dispose()
        pytest.fail("Connected MySQL database identity is not ibanking_account_db_test")

    TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=test_engine)
    db = TestSession()
    existing_user = db.query(User).filter_by(username="concurrency-test-user").first()
    existing_account = db.get(Account, "CONCURRENCY-TEST")
    existing_ledger = db.query(AccountDebit).filter(
        AccountDebit.transaction_id.in_(
            [
                "MYSQL-DISTINCT-1",
                "MYSQL-DISTINCT-2",
                "MYSQL-SAME-TRANSACTION",
            ]
        )
    ).first()
    any_account_ledger = db.query(AccountDebit).filter_by(
        account_number="CONCURRENCY-TEST"
    ).first()
    if existing_user or existing_account or existing_ledger or any_account_ledger:
        db.close()
        test_engine.dispose()
        pytest.fail(
            "ibanking_account_db_test contains reserved concurrency fixture records; "
            "refusing to overwrite or clean them up"
        )
    user = User(
        username="concurrency-test-user",
        password_hash="unused",
        full_name="Concurrency Test",
        phone="0000000000",
        email="concurrency-test@example.com",
    )
    db.add(user)
    db.flush()
    db.add(Account(
        account_number="CONCURRENCY-TEST",
        user_id=user.user_id,
        balance=Decimal("100.00"),
    ))
    db.commit()
    db.close()

    from backend.user_service import database as user_database
    monkeypatch.setattr(user_database, "SessionLocal", TestSession)
    yield TestSession

    cleanup = TestSession()
    cleanup.query(AccountDebit).filter_by(account_number="CONCURRENCY-TEST").delete()
    cleanup.query(Account).filter_by(account_number="CONCURRENCY-TEST").delete()
    cleanup.query(User).filter_by(username="concurrency-test-user").delete()
    cleanup.commit()
    cleanup.close()
    test_engine.dispose()


def _run_mysql_concurrent_debits(payloads: list[dict]):
    headers = {"X-Internal-API-Key": "test-internal-key"}
    barrier = Barrier(len(payloads))

    def debit(payload):
        with TestClient(user_main.app) as concurrent_client:
            barrier.wait()
            return concurrent_client.post(
                "/api/v1/internal/accounts/CONCURRENCY-TEST/debit",
                headers=headers,
                json=payload,
            )

    with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
        return list(executor.map(debit, payloads))


def test_mysql_concurrent_distinct_transactions_do_not_overdraw(mysql_concurrency_database):
    responses = _run_mysql_concurrent_debits([
        {"amount": "80.00", "transactionId": "MYSQL-DISTINCT-1"},
        {"amount": "80.00", "transactionId": "MYSQL-DISTINCT-2"},
    ])

    assert sorted(response.status_code for response in responses) == [200, 409]
    db = mysql_concurrency_database()
    account = db.get(Account, "CONCURRENCY-TEST")
    assert account is not None
    assert account.balance == Decimal("20.00")
    assert account.balance >= 0
    assert db.query(AccountDebit).filter_by(account_number="CONCURRENCY-TEST").count() == 1
    db.close()


def test_mysql_concurrent_same_transaction_debits_once(mysql_concurrency_database):
    payload = {"amount": "80.00", "transactionId": "MYSQL-SAME-TRANSACTION"}
    responses = _run_mysql_concurrent_debits([payload, payload])

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    db = mysql_concurrency_database()
    account = db.get(Account, "CONCURRENCY-TEST")
    assert account is not None
    assert account.balance == Decimal("20.00")
    assert account.balance >= 0
    assert db.query(AccountDebit).filter_by(transaction_id="MYSQL-SAME-TRANSACTION").count() == 1
    db.close()
