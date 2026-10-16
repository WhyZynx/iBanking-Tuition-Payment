"""Opt-in HTTP E2E suite for a disposable, explicitly approved MySQL setup.

No service calls are mocked. The suite never creates schemas or cleans rows. A
fresh disposable database set is required for each run that completes payments.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url


APPROVAL = "I_APPROVE_WRITES_TO_THE_ISOLATED_E2E_DATABASES"
DATABASE_NAMES = {
    "user": "account_db_e2e_test",
    "tuition": "ibanking_tuition_e2e_test",
    "payment": "payment_db_e2e_test",
}
PROTECTED_DATABASES = {
    "account_db",
    "account_db_test",
    "ibanking_tuition",
    "payment_db",
}
TIMEOUT = 10
READONLY_DATABASE_URLS = {
    "user": "IBANKING_E2E_READONLY_USER_DATABASE_URL",
    "tuition": "IBANKING_E2E_READONLY_TUITION_DATABASE_URL",
    "payment": "IBANKING_E2E_READONLY_PAYMENT_DATABASE_URL",
}
READONLY_TEST_NAME = "test_e2e_01_demo_login_and_jwt_validation"
USER_SERVICE_LOG_PATH = Path(tempfile.gettempdir()) / "ibanking-e2e-user-service.log"

_BEARER_PATTERN = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~-]+")
_JWT_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_URL_CREDENTIALS_PATTERN = re.compile(r"(?i)(mysql(?:\+[^:/@]+)?://)[^\s/@]+@")
_SECRET_FIELD_PATTERN = re.compile(
    r"(?i)(\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|authorization)\b\s*[=:]\s*)[^\s,;]+"
)


def _safe_log_secrets(env: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        value
        for key, value in env.items()
        if value and re.search(r"(?:PASSWORD|SECRET|API[_-]?KEY|TOKEN|DATABASE_URL)", key, re.I)
    )


def _redact_service_log_line(line: str, secrets: tuple[str, ...]) -> str:
    for secret in sorted(secrets, key=len, reverse=True):
        line = line.replace(secret, "[REDACTED]")
    line = _URL_CREDENTIALS_PATTERN.sub(r"\1[REDACTED]@", line)
    line = _BEARER_PATTERN.sub(r"\1[REDACTED]", line)
    line = _JWT_PATTERN.sub("[REDACTED_JWT]", line)
    return _SECRET_FIELD_PATTERN.sub(r"\1[REDACTED]", line)


def _readonly_grants_verified(connection, expected_database: str) -> bool:
    """Accept only direct SELECT-on-this-database grants, with no active roles."""
    role = connection.execute(text("SELECT CURRENT_ROLE()")).scalar_one()
    if role not in (None, "NONE"):
        return False
    grants = [str(row[0]).strip() for row in connection.execute(text("SHOW GRANTS"))]
    if not grants:
        return False

    allowed = re.compile(
        rf"^GRANT (?:USAGE ON \*\.\*|SELECT ON [`]?{re.escape(expected_database)}[`]?\.\*) TO .+$",
        re.IGNORECASE,
    )
    return all(allowed.fullmatch(grant) for grant in grants) and any(
        re.search(rf"\bSELECT ON [`]?{re.escape(expected_database)}[`]?\.\*(?:\s|$)", grant, re.I)
        for grant in grants
    )


def _readonly_mode(request) -> bool:
    value = os.getenv("IBANKING_E2E_READONLY")
    if value is None:
        return False
    if value != "YES":
        pytest.fail("IBANKING_E2E_READONLY must be exactly YES when set")
    if os.getenv("IBANKING_E2E_APPROVAL"):
        pytest.fail("Do not set IBANKING_E2E_APPROVAL in READONLY mode")
    selected = getattr(request.session, "items", ())
    if len(selected) != 1 or selected[0].originalname != READONLY_TEST_NAME:
        pytest.fail("READONLY mode permits only test_e2e_01_demo_login_and_jwt_validation")
    return True


@dataclass
class E2E:
    user_url: str
    tuition_url: str
    payment_url: str
    otp_reader_url: str | None
    engines: dict[str, object]
    service_processes: list[subprocess.Popen]
    primary_username: str
    primary_password: str
    second_username: str
    second_password: str
    primary_account: str
    low_balance_account: str
    second_account: str
    successful_student: str
    insufficient_student: str
    paid_student: str
    expired_student: str
    shared_student: str

    def login(self, username: str, password: str) -> tuple[str, dict]:
        response = requests.post(
            f"{self.user_url}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        body = response.json()
        assert body.get("token_type", "bearer").lower() == "bearer"
        token = body.get("access_token")
        assert isinstance(token, str) and token
        headers = {"Authorization": f"Bearer {token}"}
        return token, headers

    def otp(self, transaction_id: str) -> str:
        self.require_otp_reader()
        response = requests.get(
            self.otp_reader_url,
            params={"transaction_id": transaction_id},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        code = response.json().get("otp_code")
        assert isinstance(code, str) and len(code) == 6 and code.isdigit()
        return code

    def require_otp_reader(self) -> None:
        if (
            not self.otp_reader_url
            or os.getenv("IBANKING_E2E_LOCAL_SMTP_READY") != "YES"
        ):
            pytest.skip(
                "Configure and verify a local SMTP sink plus the test-only OTP reader "
                "before starting an OTP scenario."
            )
        _check_local_smtp()

    def scalar(self, service: str, query: str, params: dict | None = None):
        with self.engines[service].connect() as connection:
            return connection.execute(text(query), params or {}).scalar_one_or_none()


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"Set {name} only after preparing the isolated E2E environment")
    return value


def _check_db_url(env_name: str, expected_database: str) -> URL:
    try:
        url = make_url(_required(env_name))
    except Exception as exc:
        pytest.fail(f"{env_name} is not a valid SQLAlchemy URL ({type(exc).__name__})")
    if url.drivername != "mysql+pymysql":
        pytest.fail(f"{env_name} must use mysql+pymysql")
    if url.database != expected_database or url.database in PROTECTED_DATABASES:
        pytest.fail(f"{env_name} must target {expected_database}; target rejected")
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail(f"{env_name} must target a locally verified disposable MySQL server")
    if not url.username or url.password is None:
        pytest.fail(f"{env_name} must include explicitly configured test credentials")
    return url


def _check_otp_reader_url() -> str | None:
    value = os.getenv("IBANKING_E2E_OTP_READER_URL")
    if not value:
        return None
    parsed = urlparse(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.port
    ):
        pytest.fail("OTP reader must be a local HTTP endpoint without credentials in its URL")
    return value


def _check_local_smtp() -> None:
    host = _required("IBANKING_E2E_SMTP_HOST").strip("[]").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("OTP scenarios require a loopback SMTP sink")


def _stop_service(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    reader = getattr(process, "_safe_log_reader", None)
    if reader is not None:
        reader.join(timeout=5)


def _start_service(module: str, port: int, env: dict[str, str], *, capture_user_log: bool = False):
    root = Path(__file__).resolve().parents[2]
    log_handle = None
    stdout = subprocess.DEVNULL
    stderr = subprocess.DEVNULL
    if capture_user_log:
        # Redaction happens in memory before any subprocess output is persisted.
        log_handle = USER_SERVICE_LOG_PATH.open("w", encoding="utf-8", buffering=1)
        stdout = subprocess.PIPE
        stderr = subprocess.STDOUT
    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", module,
            "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
        ],
        cwd=root,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
    )
    if capture_user_log:
        secrets = _safe_log_secrets(env)

        def write_sanitized_output() -> None:
            try:
                assert process.stdout is not None and log_handle is not None
                for line in process.stdout:
                    log_handle.write(_redact_service_log_line(line, secrets))
            finally:
                if log_handle is not None:
                    log_handle.close()

        reader = threading.Thread(target=write_sanitized_output, daemon=True)
        process._safe_log_reader = reader
        reader.start()
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"Service failed to start on port {port}; no scenario requests were sent")
        try:
            if requests.get(f"{base_url}/health", timeout=1).status_code == 200:
                return process, base_url
        except requests.RequestException:
            pass
        time.sleep(0.2)
    _stop_service(process)
    pytest.fail(f"Service readiness timed out on port {port}; no scenario requests were sent")


def _require_free_service_ports() -> None:
    for port in (8001, 8002, 8003):
        sock = socket.socket()
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            pytest.skip(
                f"Port {port} is already in use. Stop existing services so the suite can "
                "start isolated child processes with the verified E2E database URLs."
            )
        finally:
            sock.close()


@pytest.fixture(scope="session")
def e2e(request) -> E2E:
    readonly = _readonly_mode(request)
    if not readonly and os.getenv("IBANKING_E2E_APPROVAL") != APPROVAL:
        pytest.skip(
            "Real payment E2E can write account, tuition, and payment rows; "
            "explicit isolated-database approval is required."
        )
    if os.getenv("IBANKING_E2E_ISOLATION_CONFIRMED") != "YES":
        pytest.skip("Confirm the disposable MySQL server and service database targets first")
    expected_mysql_host = _required("IBANKING_E2E_MYSQL_SERVER_HOSTNAME")
    expected_mysql_port = int(_required("IBANKING_E2E_MYSQL_SERVER_PORT"))
    expected_mysql_datadir = os.path.normcase(
        os.path.normpath(_required("IBANKING_E2E_MYSQL_DATADIR"))
    )

    url_names = READONLY_DATABASE_URLS if readonly else {
        "user": "IBANKING_E2E_USER_DATABASE_URL",
        "tuition": "IBANKING_E2E_TUITION_DATABASE_URL",
        "payment": "IBANKING_E2E_PAYMENT_DATABASE_URL",
    }
    urls = {
        name: _check_db_url(url_names[name], DATABASE_NAMES[name])
        for name in DATABASE_NAMES
    }
    if len({url.database for url in urls.values()}) != 3:
        pytest.fail("User, Tuition, and Payment must each use a distinct test database")
    for url in urls.values():
        if url.port != expected_mysql_port:
            pytest.fail("Database URL port does not match the confirmed disposable MySQL server")

    jwt_secret = _required("IBANKING_E2E_JWT_SECRET")
    internal_api_key = _required("IBANKING_E2E_INTERNAL_API_KEY")
    _require_free_service_ports()
    engines = {name: create_engine(url, pool_pre_ping=True) for name, url in urls.items()}
    service_processes: list[subprocess.Popen] = []
    try:
        # Validate the selected database on each connection before any HTTP write.
        for name, engine in engines.items():
            try:
                with engine.connect() as connection:
                    row = connection.execute(
                        text("SELECT DATABASE(), @@hostname, @@port, @@datadir, VERSION()")
                    ).one()
            except Exception as exc:
                pytest.fail(
                    f"Read-only MySQL identity query failed for {name} ({type(exc).__name__})",
                    pytrace=False,
                )
            else:
                actual_datadir = os.path.normcase(os.path.normpath(str(row[3])))
                if (
                    row[0] != DATABASE_NAMES[name]
                    or row[1] != expected_mysql_host
                    or int(row[2]) != expected_mysql_port
                    or actual_datadir != expected_mysql_datadir
                    or not str(row[4]).startswith("8.")
                ):
                    pytest.fail(f"MySQL identity check rejected the {name} database target")
                if readonly and not _readonly_grants_verified(connection, DATABASE_NAMES[name]):
                    pytest.fail(
                        f"READONLY credentials for {name} must have only direct SELECT access "
                        "to that database and no active MySQL roles"
                    )

        required_tables = {
            "user": {"users", "accounts", "account_debits"},
            "tuition": {"tuition_bills", "tuition_payment_claims"},
            "payment": {"transactions", "otps"},
        }
        required_columns = {
            "user": {
                "users": {"user_id", "username", "password_hash", "student_id"},
                "accounts": {"account_number", "user_id", "balance", "is_default", "status"},
                "account_debits": {"transaction_id", "account_number", "amount", "balance_after"},
            },
            "tuition": {
                "tuition_bills": {"student_id", "student_name", "amount", "status"},
                "tuition_payment_claims": {"student_id", "transaction_id"},
            },
            "payment": {
                "transactions": {
                    "transaction_id", "payer_user_id", "source_account_number", "student_id",
                    "student_name", "amount", "status", "created_at", "completed_at",
                },
                "otps": {"otp_id", "transaction_id", "otp_code", "expires_at", "is_used"},
            },
        }
        required_foreign_keys = {
            "user": {
                ("accounts", "user_id", "users", "user_id"),
                ("account_debits", "account_number", "accounts", "account_number"),
            },
            "tuition": {
                ("tuition_payment_claims", "student_id", "tuition_bills", "student_id"),
            },
            "payment": set(),
        }
        for name, engine in engines.items():
            with engine.connect() as connection:
                found_tables = set(
                    connection.execute(
                        text(
                            "SELECT TABLE_NAME FROM information_schema.tables "
                            "WHERE TABLE_SCHEMA=DATABASE()"
                        )
                    ).scalars()
                )
            if not required_tables[name].issubset(found_tables):
                pytest.fail(f"Required schema tables are missing in the isolated {name} database")
            with engine.connect() as connection:
                for table, expected_columns in required_columns[name].items():
                    found_columns = set(
                        connection.execute(
                            text(
                                "SELECT COLUMN_NAME FROM information_schema.columns "
                                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table"
                            ),
                            {"table": table},
                        ).scalars()
                    )
                    if not expected_columns.issubset(found_columns):
                        pytest.fail(f"Required columns are missing from {name}.{table}")
                found_keys = set(
                    connection.execute(
                        text(
                            "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, "
                            "REFERENCED_COLUMN_NAME FROM information_schema.key_column_usage "
                            "WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL"
                        )
                    ).all()
                )
            if not required_foreign_keys[name].issubset(found_keys):
                pytest.fail(f"Required foreign keys are missing in the isolated {name} database")

        shared_env = os.environ.copy()
        shared_env.update({
            "JWT_SECRET_KEY": jwt_secret,
            "JWT_ALGORITHM": "HS256",
            "INTERNAL_API_KEY": internal_api_key,
        })
        user_env = shared_env.copy()
        user_env["DATABASE_URL"] = urls["user"].render_as_string(hide_password=False)
        service_processes.append(
            _start_service(
                "backend.user_service.main:app", 8001, user_env, capture_user_log=True
            )[0]
        )

        tuition_env = shared_env.copy()
        tuition_env["DATABASE_URL"] = urls["tuition"].render_as_string(hide_password=False)
        service_processes.append(
            _start_service("backend.tuition_service.main:app", 8002, tuition_env)[0]
        )

        payment_env = shared_env.copy()
        payment_env["PAYMENT_DATABASE_URL"] = urls["payment"].render_as_string(hide_password=False)
        payment_env["USER_SERVICE_URL"] = "http://127.0.0.1:8001"
        payment_env["TUITION_SERVICE_URL"] = "http://127.0.0.1:8002"
        for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM_EMAIL"):
            payment_env[key] = os.getenv(f"IBANKING_E2E_{key}", "")
        service_processes.append(
            _start_service("backend.payment_service.main:app", 8003, payment_env)[0]
        )

        result = E2E(
            user_url="http://127.0.0.1:8001",
            tuition_url="http://127.0.0.1:8002",
            payment_url="http://127.0.0.1:8003",
            otp_reader_url=_check_otp_reader_url(),
            engines=engines,
            service_processes=service_processes,
            primary_username=_required("IBANKING_E2E_PRIMARY_USERNAME"),
            primary_password=_required("IBANKING_E2E_PRIMARY_PASSWORD"),
            second_username=_required("IBANKING_E2E_SECOND_USERNAME"),
            second_password=_required("IBANKING_E2E_SECOND_PASSWORD"),
            primary_account=os.getenv("IBANKING_E2E_PRIMARY_ACCOUNT", "6201000001"),
            low_balance_account=os.getenv("IBANKING_E2E_LOW_BALANCE_ACCOUNT", "6201000002"),
            second_account=os.getenv("IBANKING_E2E_SECOND_ACCOUNT", "6201000005"),
            successful_student=os.getenv("IBANKING_E2E_SUCCESS_STUDENT", "DEMO24003"),
            insufficient_student=os.getenv("IBANKING_E2E_INSUFFICIENT_STUDENT", "DEMO24001"),
            paid_student=os.getenv("IBANKING_E2E_PAID_STUDENT", "DEMO24006"),
            expired_student=os.getenv("IBANKING_E2E_EXPIRED_STUDENT", "DEMO24004"),
            shared_student=os.getenv("IBANKING_E2E_SHARED_STUDENT", "DEMO24005"),
        )
    except BaseException:
        for process in reversed(service_processes):
            _stop_service(process)
        for engine in engines.values():
            engine.dispose()
        raise
    request.addfinalizer(
        lambda: [_stop_service(process) for process in reversed(service_processes)]
    )
    request.addfinalizer(lambda: [engine.dispose() for engine in engines.values()])
    return result


@pytest.fixture(scope="session")
def successful_payment(e2e: E2E) -> dict:
    e2e.require_otp_reader()
    _, headers = e2e.login(e2e.second_username, e2e.second_password)
    bill_before = e2e.scalar(
        "tuition", "SELECT status FROM tuition_bills WHERE student_id=:student",
        {"student": e2e.successful_student},
    )
    if bill_before != "UNPAID":
        pytest.skip("Successful-payment bill is not pristine; use a fresh isolated E2E database set")
    before_balance = e2e.scalar(
        "user", "SELECT balance FROM accounts WHERE account_number=:account",
        {"account": e2e.second_account},
    )
    response = requests.post(
        f"{e2e.payment_url}/api/v1/payments",
        headers=headers,
        json={"student_id": e2e.successful_student, "account_number": e2e.second_account},
        timeout=TIMEOUT,
    )
    assert response.status_code == 201
    transaction_id = response.json()["transaction_id"]
    otp_response = requests.post(
        f"{e2e.payment_url}/api/v1/payments/{transaction_id}/otp",
        headers=headers,
        timeout=TIMEOUT,
    )
    assert otp_response.status_code == 200
    code = e2e.otp(transaction_id)
    confirmed = requests.post(
        f"{e2e.payment_url}/api/v1/payments/confirm",
        headers=headers,
        json={"transactionId": transaction_id, "otpCode": code},
        timeout=TIMEOUT,
    )
    assert confirmed.status_code == 200
    assert confirmed.json().get("status") == "SUCCESS"

    amount = e2e.scalar(
        "payment", "SELECT amount FROM transactions WHERE transaction_id=:id", {"id": transaction_id}
    )
    after_balance = e2e.scalar(
        "user", "SELECT balance FROM accounts WHERE account_number=:account",
        {"account": e2e.second_account},
    )
    after_status = e2e.scalar(
        "tuition", "SELECT status FROM tuition_bills WHERE student_id=:student",
        {"student": e2e.successful_student},
    )
    debit_count = e2e.scalar(
        "user", "SELECT COUNT(*) FROM account_debits WHERE transaction_id=:id", {"id": transaction_id}
    )
    assert amount is not None and before_balance - after_balance == amount
    assert after_status == "PAID"
    assert debit_count == 1
    otp_used = e2e.scalar(
        "payment",
        "SELECT is_used FROM otps WHERE transaction_id=:id ORDER BY otp_id DESC LIMIT 1",
        {"id": transaction_id},
    )
    assert otp_used in (1, True)
    replay = requests.post(
        f"{e2e.payment_url}/api/v1/payments/confirm",
        headers=headers,
        json={"transactionId": transaction_id, "otpCode": code},
        timeout=TIMEOUT,
    )
    assert replay.status_code == 409
    return {"transaction_id": transaction_id, "headers": headers}


def test_e2e_01_demo_login_and_jwt_validation(e2e: E2E):
    _, headers = e2e.login(e2e.primary_username, e2e.primary_password)
    response = requests.get(f"{e2e.user_url}/api/v1/users/me", headers=headers, timeout=TIMEOUT)
    assert response.status_code == 200
    assert response.json().get("username") == e2e.primary_username
    mapped_user_id = e2e.scalar(
        "user", "SELECT user_id FROM users WHERE username=:username",
        {"username": e2e.primary_username},
    )
    account_owner_id = e2e.scalar(
        "user", "SELECT user_id FROM accounts WHERE account_number=:account",
        {"account": e2e.primary_account},
    )
    assert mapped_user_id is not None and mapped_user_id == account_owner_id
    assert response.json().get("student_id") is not None
    payment_response = requests.get(
        f"{e2e.payment_url}/api/v1/transactions/me", headers=headers, timeout=TIMEOUT
    )
    assert payment_response.status_code == 200
    assert isinstance(payment_response.json().get("items"), list)


def test_e2e_02_tuition_lookup(e2e: E2E):
    response = requests.get(
        f"{e2e.tuition_url}/api/v1/tuition/{e2e.insufficient_student}", timeout=TIMEOUT
    )
    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == e2e.insufficient_student
    assert body["status"] == "UNPAID"
    assert float(body["amount"]) > 0


def test_e2e_03_successful_payment(e2e: E2E, successful_payment: dict):
    assert successful_payment["transaction_id"]


def test_e2e_04_insufficient_balance(e2e: E2E):
    _, headers = e2e.login(e2e.primary_username, e2e.primary_password)
    before = e2e.scalar(
        "user", "SELECT balance FROM accounts WHERE account_number=:account",
        {"account": e2e.low_balance_account},
    )
    bill = e2e.scalar(
        "tuition", "SELECT amount FROM tuition_bills WHERE student_id=:student AND status='UNPAID'",
        {"student": e2e.insufficient_student},
    )
    assert bill is not None and before < bill
    ledger_before = e2e.scalar(
        "user", "SELECT COUNT(*) FROM account_debits WHERE account_number=:account",
        {"account": e2e.low_balance_account},
    )
    response = requests.post(
        f"{e2e.payment_url}/api/v1/payments",
        headers=headers,
        json={"student_id": e2e.insufficient_student, "account_number": e2e.low_balance_account},
        timeout=TIMEOUT,
    )
    after = e2e.scalar(
        "user", "SELECT balance FROM accounts WHERE account_number=:account",
        {"account": e2e.low_balance_account},
    )
    ledger_after = e2e.scalar(
        "user", "SELECT COUNT(*) FROM account_debits WHERE account_number=:account",
        {"account": e2e.low_balance_account},
    )
    assert response.status_code == 409
    assert response.json().get("detail") == "Insufficient account balance"
    assert before == after
    assert ledger_before == ledger_after


def test_e2e_05_already_paid_tuition(e2e: E2E):
    _, headers = e2e.login(e2e.primary_username, e2e.primary_password)
    before = e2e.scalar(
        "tuition", "SELECT status FROM tuition_bills WHERE student_id=:student",
        {"student": e2e.paid_student},
    )
    balance_before = e2e.scalar(
        "user", "SELECT balance FROM accounts WHERE account_number=:account",
        {"account": e2e.primary_account},
    )
    ledger_before = e2e.scalar(
        "user", "SELECT COUNT(*) FROM account_debits WHERE account_number=:account",
        {"account": e2e.primary_account},
    )
    response = requests.post(
        f"{e2e.payment_url}/api/v1/payments",
        headers=headers,
        json={"student_id": e2e.paid_student, "account_number": e2e.primary_account},
        timeout=TIMEOUT,
    )
    after = e2e.scalar(
        "tuition", "SELECT status FROM tuition_bills WHERE student_id=:student",
        {"student": e2e.paid_student},
    )
    balance_after = e2e.scalar(
        "user", "SELECT balance FROM accounts WHERE account_number=:account",
        {"account": e2e.primary_account},
    )
    ledger_after = e2e.scalar(
        "user", "SELECT COUNT(*) FROM account_debits WHERE account_number=:account",
        {"account": e2e.primary_account},
    )
    assert response.status_code == 409
    assert before == after == "PAID"
    assert balance_before == balance_after
    assert ledger_before == ledger_after


def _create_pending(e2e: E2E, username: str, password: str, student: str, account: str):
    e2e.require_otp_reader()
    _, headers = e2e.login(username, password)
    response = requests.post(
        f"{e2e.payment_url}/api/v1/payments",
        headers=headers,
        json={"student_id": student, "account_number": account},
        timeout=TIMEOUT,
    )
    assert response.status_code == 201
    transaction_id = response.json()["transaction_id"]
    response = requests.post(
        f"{e2e.payment_url}/api/v1/payments/{transaction_id}/otp",
        headers=headers,
        timeout=TIMEOUT,
    )
    assert response.status_code == 200
    return transaction_id, headers


def test_e2e_06_invalid_otp(e2e: E2E):
    transaction_id, headers = _create_pending(
        e2e, e2e.primary_username, e2e.primary_password,
        e2e.insufficient_student, e2e.primary_account,
    )
    valid_code = e2e.otp(transaction_id)
    invalid_code = "000000" if valid_code != "000000" else "000001"
    response = requests.post(
        f"{e2e.payment_url}/api/v1/payments/confirm",
        headers=headers,
        json={"transactionId": transaction_id, "otpCode": invalid_code},
        timeout=TIMEOUT,
    )
    status_response = requests.get(
        f"{e2e.payment_url}/api/v1/payments/{transaction_id}", headers=headers, timeout=TIMEOUT
    )
    assert response.status_code == 400
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "PENDING"
    assert e2e.scalar(
        "user", "SELECT COUNT(*) FROM account_debits WHERE transaction_id=:id", {"id": transaction_id}
    ) == 0


def test_e2e_07_expired_otp(e2e: E2E):
    transaction_id, headers = _create_pending(
        e2e, e2e.primary_username, e2e.primary_password,
        e2e.expired_student, e2e.primary_account,
    )
    code = e2e.otp(transaction_id)
    # Test-only clock setup on the already-verified disposable Payment database.
    with e2e.engines["payment"].begin() as connection:
        result = connection.execute(
            text("UPDATE otps SET expires_at=CURRENT_TIMESTAMP - INTERVAL 1 MINUTE WHERE transaction_id=:id AND is_used=FALSE"),
            {"id": transaction_id},
        )
    assert result.rowcount == 1
    response = requests.post(
        f"{e2e.payment_url}/api/v1/payments/confirm",
        headers=headers,
        json={"transactionId": transaction_id, "otpCode": code},
        timeout=TIMEOUT,
    )
    assert response.status_code == 400
    assert e2e.scalar(
        "user", "SELECT COUNT(*) FROM account_debits WHERE transaction_id=:id", {"id": transaction_id}
    ) == 0


def test_e2e_08_duplicate_debit_retry(e2e: E2E):
    account = e2e.low_balance_account
    transaction_id = "phase51-e2e-debit-retry-demo"
    headers = {"X-Internal-API-Key": _required("IBANKING_E2E_INTERNAL_API_KEY")}
    before = e2e.scalar(
        "user", "SELECT balance FROM accounts WHERE account_number=:account", {"account": account}
    )
    existing = e2e.scalar(
        "user", "SELECT COUNT(*) FROM account_debits WHERE transaction_id=:id AND account_number=:account",
        {"id": transaction_id, "account": account},
    )
    url = f"{e2e.user_url}/api/v1/internal/accounts/{account}/debit"
    payload = {"amount": 1, "transactionId": transaction_id}
    first = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    second = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    assert first.status_code == second.status_code == 200
    assert first.json()["remainingBalance"] == second.json()["remainingBalance"]
    assert e2e.scalar(
        "user", "SELECT COUNT(*) FROM account_debits WHERE transaction_id=:id", {"id": transaction_id}
    ) == 1
    current = e2e.scalar(
        "user", "SELECT balance FROM accounts WHERE account_number=:account", {"account": account}
    )
    prior_balance = e2e.scalar(
        "user", "SELECT balance_after FROM account_debits WHERE transaction_id=:id", {"id": transaction_id}
    )
    assert current == prior_balance
    expected_balance = before if existing else before - Decimal("1.00")
    assert current == expected_balance


def test_e2e_09_two_payers_compete_for_same_bill(e2e: E2E):
    initial = e2e.scalar(
        "tuition", "SELECT status FROM tuition_bills WHERE student_id=:student",
        {"student": e2e.shared_student},
    )
    if initial != "UNPAID":
        pytest.skip("Shared-bill scenario is no longer pristine; use a fresh isolated E2E database set")
    first_id, first_headers = _create_pending(
        e2e, e2e.primary_username, e2e.primary_password, e2e.shared_student, e2e.primary_account
    )
    second_id, second_headers = _create_pending(
        e2e, e2e.second_username, e2e.second_password, e2e.shared_student, e2e.second_account
    )
    first_code, second_code = e2e.otp(first_id), e2e.otp(second_id)

    def confirm(transaction_id, headers, code):
        return requests.post(
            f"{e2e.payment_url}/api/v1/payments/confirm",
            headers=headers,
            json={"transactionId": transaction_id, "otpCode": code},
            timeout=TIMEOUT,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(confirm, first_id, first_headers, first_code),
            executor.submit(confirm, second_id, second_headers, second_code),
        ]
        responses = [future.result() for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert e2e.scalar(
        "tuition", "SELECT status FROM tuition_bills WHERE student_id=:student",
        {"student": e2e.shared_student},
    ) == "PAID"
    assert e2e.scalar(
        "user",
        "SELECT COUNT(*) FROM account_debits WHERE transaction_id IN (:first, :second)",
        {"first": first_id, "second": second_id},
    ) == 1
    assert e2e.scalar(
        "payment",
        "SELECT COUNT(*) FROM transactions WHERE transaction_id IN (:first, :second) AND status='SUCCESS'",
        {"first": first_id, "second": second_id},
    ) == 1


def test_e2e_10_failure_timeout_and_reconciliation():
    pytest.skip(
        "Requires a separately controlled fault-injection proxy and a fresh disposable database; "
        "no such safe harness is configured."
    )


def test_e2e_11_transaction_history_consistency(e2e: E2E, successful_payment: dict):
    response = requests.get(
        f"{e2e.payment_url}/api/v1/transactions/me",
        headers=successful_payment["headers"],
        timeout=TIMEOUT,
    )
    assert response.status_code == 200
    items = response.json().get("items")
    assert isinstance(items, list)
    found = [
        item for item in items
        if item.get("transactionId") == successful_payment["transaction_id"]
    ]
    assert len(found) == 1
    assert found[0]["status"] == "SUCCESS"


def test_e2e_12_unauthorized_access(e2e: E2E):
    cases = [
        requests.get(f"{e2e.user_url}/api/v1/users/me", timeout=TIMEOUT),
        requests.get(f"{e2e.user_url}/api/v1/accounts/me", timeout=TIMEOUT),
        requests.post(
            f"{e2e.payment_url}/api/v1/payments",
            json={"student_id": e2e.insufficient_student, "account_number": e2e.primary_account},
            timeout=TIMEOUT,
        ),
        requests.get(
            f"{e2e.user_url}/api/v1/internal/accounts/{e2e.primary_account}", timeout=TIMEOUT
        ),
        requests.post(
            f"{e2e.tuition_url}/api/v1/tuition/{e2e.shared_student}/claim",
            json={"transaction_id": "unauthorized-e2e-check"}, timeout=TIMEOUT,
        ),
    ]
    assert [response.status_code for response in cases] == [401, 401, 401, 401, 401]

