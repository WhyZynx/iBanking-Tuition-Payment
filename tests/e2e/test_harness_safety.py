from types import SimpleNamespace

import pytest

from tests.e2e.test_real_http_e2e import (
    _readonly_grants_verified,
    _readonly_mode,
    _redact_service_log_line,
)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def scalar_one(self):
        return self.rows[0][0]

    def __iter__(self):
        return iter(self.rows)


class FakeConnection:
    def __init__(self, role, grants):
        self.role = role
        self.grants = grants

    def execute(self, statement):
        query = str(statement)
        if query == "SELECT CURRENT_ROLE()":
            return FakeResult([(self.role,)])
        assert query == "SHOW GRANTS"
        return FakeResult([(grant,) for grant in self.grants])


def test_readonly_grants_allow_only_select_on_target_database():
    connection = FakeConnection(
        "NONE",
        [
            "GRANT USAGE ON *.* TO `reader`@`localhost`",
            "GRANT SELECT ON `account_db_e2e_test`.* TO `reader`@`localhost`",
        ],
    )
    assert _readonly_grants_verified(connection, "account_db_e2e_test")

    writable = FakeConnection(
        "NONE",
        [
            "GRANT USAGE ON *.* TO `reader`@`localhost`",
            "GRANT SELECT, INSERT ON `account_db_e2e_test`.* TO `reader`@`localhost`",
        ],
    )
    assert not _readonly_grants_verified(writable, "account_db_e2e_test")


def test_readonly_grants_reject_active_roles():
    connection = FakeConnection(
        "`e2e_reader_role`@`%`",
        ["GRANT USAGE ON *.* TO `reader`@`localhost`"],
    )
    assert not _readonly_grants_verified(connection, "account_db_e2e_test")


def test_service_log_redacts_credentials_and_tokens_before_write():
    database_url = "mysql+pymysql://demo:db-secret@127.0.0.1/account_db_e2e_test"
    api_key = "internal-secret"
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature"
    raw = (
        f"connecting to {database_url}; INTERNAL_API_KEY={api_key}; "
        f"Authorization: Bearer {token}"
    )
    safe = _redact_service_log_line(raw, (database_url, api_key))
    assert database_url not in safe
    assert "db-secret" not in safe
    assert api_key not in safe
    assert token not in safe
    assert "[REDACTED]" in safe


def test_readonly_mode_requires_only_the_profile_test(monkeypatch):
    monkeypatch.setenv("IBANKING_E2E_READONLY", "YES")
    monkeypatch.delenv("IBANKING_E2E_APPROVAL", raising=False)
    selected = SimpleNamespace(originalname="test_e2e_01_demo_login_and_jwt_validation")
    request = SimpleNamespace(session=SimpleNamespace(items=[selected]))
    assert _readonly_mode(request)

    request.session.items.append(SimpleNamespace(originalname="test_e2e_02_tuition_lookup"))
    with pytest.raises(pytest.fail.Exception):
        _readonly_mode(request)


def test_readonly_mode_rejects_approval_flag(monkeypatch):
    monkeypatch.setenv("IBANKING_E2E_READONLY", "YES")
    monkeypatch.setenv("IBANKING_E2E_APPROVAL", "unexpected")
    selected = SimpleNamespace(originalname="test_e2e_01_demo_login_and_jwt_validation")
    request = SimpleNamespace(session=SimpleNamespace(items=[selected]))
    with pytest.raises(pytest.fail.Exception):
        _readonly_mode(request)
