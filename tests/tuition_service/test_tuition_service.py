from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Lock
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.tuition_service.controllers import tuition_controller

app = tuition_controller.app
TEST_INTERNAL_API_KEY = "test-internal-api-key"
INTERNAL_API_HEADERS = {"X-Internal-API-Key": TEST_INTERNAL_API_KEY}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        tuition_controller,
        "INTERNAL_API_KEY",
        TEST_INTERNAL_API_KEY
    )
    app.dependency_overrides[
        tuition_controller.require_authenticated_user
    ] = lambda: 1
    app.dependency_overrides[
        tuition_controller.require_tuition_reader
    ] = lambda: 1
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(
        tuition_controller.require_authenticated_user,
        None,
    )
    app.dependency_overrides.pop(
        tuition_controller.require_tuition_reader,
        None,
    )


def create_connection(fetchone=None, fetchall=None, rowcount=1):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall
    cursor.rowcount = rowcount

    cursor_context = MagicMock()
    cursor_context.__enter__.return_value = cursor
    cursor_context.__exit__.return_value = False

    connection = MagicMock()
    connection.cursor.return_value = cursor_context

    return connection, cursor


def test_get_all_tuitions(client):
    tuition_data = [
        {
            "student_id": "524H0012",
            "student_name": "Nguyen Minh Anh",
            "amount": Decimal("18500000.00"),
            "status": "UNPAID"
        },
        {
            "student_id": "524H0078",
            "student_name": "Le Hoang Phuc",
            "amount": Decimal("19750000.00"),
            "status": "PAID"
        }
    ]

    connection, _ = create_connection(fetchall=tuition_data)

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=connection
    ):
        response = client.get("/api/v1/tuition")

    assert response.status_code == 200
    assert response.json() == [
        {
            "student_id": "524H0012",
            "student_name": "Nguyen Minh Anh",
            "amount": "18500000.00",
            "status": "UNPAID"
        },
        {
            "student_id": "524H0078",
            "student_name": "Le Hoang Phuc",
            "amount": "19750000.00",
            "status": "PAID"
        }
    ]


def test_get_existing_tuition(client):
    tuition_data = {
        "student_id": "524H0012",
        "student_name": "Nguyen Minh Anh",
        "amount": Decimal("18500000.00"),
        "status": "UNPAID"
    }

    connection, _ = create_connection(fetchone=tuition_data)

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=connection
    ):
        response = client.get("/api/v1/tuition/524H0012")

    assert response.status_code == 200
    assert response.json() == {
        "student_id": "524H0012",
        "student_name": "Nguyen Minh Anh",
        "amount": "18500000.00",
        "status": "UNPAID"
    }


def test_get_tuition_normalizes_student_id(client):
    tuition_data = {
        "student_id": "524H0012",
        "student_name": "Nguyen Minh Anh",
        "amount": Decimal("18500000.00"),
        "status": "UNPAID"
    }

    connection, cursor = create_connection(fetchone=tuition_data)

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=connection
    ):
        response = client.get("/api/v1/tuition/524h0012")

    assert response.status_code == 200
    assert cursor.execute.call_args[0][1] == ("524H0012",)


def test_get_missing_tuition(client):
    connection, _ = create_connection(fetchone=None)

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=connection
    ):
        response = client.get("/api/v1/tuition/524H9999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Tuition information not found"
    }


def test_mark_tuition_as_paid(client):
    update_connection, _ = create_connection(
        fetchone={"transaction_id": "TX-UPDATE-104", "claimed_at": "2026-11-03"},
        rowcount=1,
    )

    paid_tuition = {
        "student_id": "524H0104",
        "student_name": "Pham Ngoc Han",
        "amount": Decimal("17300000.00"),
        "status": "PAID"
    }

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=update_connection
    ), patch(
        "backend.tuition_service.services.tuition_service.get_tuition",
        return_value=paid_tuition
    ):
        response = client.put(
            "/api/v1/tuition/524H0104/pay",
            headers=INTERNAL_API_HEADERS,
            json={"transaction_id": "TX-UPDATE-104"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "student_id": "524H0104",
        "student_name": "Pham Ngoc Han",
        "amount": "17300000.00",
        "status": "PAID"
    }

    update_connection.commit.assert_called_once()


def test_mark_tuition_as_paid_without_transaction_id_uses_single_claim(client):
    update_connection, _ = create_connection(
        fetchone={
            "claim_count": 1,
            "transaction_id": "TX-LEGACY-PAYMENT",
        },
        rowcount=1,
    )

    paid_tuition = {
        "student_id": "524H0104",
        "student_name": "Pham Ngoc Han",
        "amount": Decimal("17300000.00"),
        "status": "PAID"
    }

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=update_connection
    ), patch(
        "backend.tuition_service.services.tuition_service.get_tuition",
        return_value=paid_tuition
    ):
        response = client.put(
            "/api/v1/tuition/524H0104/pay",
            headers=INTERNAL_API_HEADERS,
        )

    assert response.status_code == 200
    assert response.json()["status"] == "PAID"
    update_connection.commit.assert_called_once()


def test_mark_already_paid_tuition(client):
    connection, _ = create_connection(
        fetchone={"status": "PAID"},
        rowcount=0
    )

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=connection
    ):
        response = client.put(
            "/api/v1/tuition/524H0078/pay",
            headers=INTERNAL_API_HEADERS,
            json={"transaction_id": "TX-UPDATE-078"},
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Tuition has already been paid"
    }


def test_mark_missing_tuition_as_paid(client):
    connection, _ = create_connection(
        fetchone=None,
        rowcount=0
    )

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=connection
    ):
        response = client.put(
            "/api/v1/tuition/524H9999/pay",
            headers=INTERNAL_API_HEADERS,
            json={"transaction_id": "TX-UPDATE-999"},
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Tuition information not found"
    }


def test_concurrent_payment_status_allows_only_one_success(monkeypatch):
    monkeypatch.setattr(
        tuition_controller,
        "INTERNAL_API_KEY",
        TEST_INTERNAL_API_KEY
    )
    state = {
        "paid": False
    }

    lock = Lock()

    paid_tuition = {
        "student_id": "524H0104",
        "student_name": "Pham Ngoc Han",
        "amount": Decimal("17300000.00"),
        "status": "PAID"
    }

    def create_concurrent_connection():
        cursor = MagicMock()

        def execute(query, params=None):
            _ = params
            if "UPDATE tuition_bills" in query:
                with lock:
                    if state["paid"]:
                        cursor.rowcount = 0
                    else:
                        state["paid"] = True
                        cursor.rowcount = 1

            elif "SELECT status" in query:
                cursor.fetchone.return_value = {
                    "status": "PAID"
                }

        cursor.execute.side_effect = execute

        cursor_context = MagicMock()
        cursor_context.__enter__.return_value = cursor
        cursor_context.__exit__.return_value = False

        connection = MagicMock()
        connection.cursor.return_value = cursor_context

        return connection

    def pay_once():
        with TestClient(app) as concurrent_client:
            return concurrent_client.put(
                "/api/v1/tuition/524H0104/pay",
                headers=INTERNAL_API_HEADERS,
                json={"transaction_id": "TX-CONCURRENT-104"},
            ).status_code

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        side_effect=lambda: create_concurrent_connection()
    ), patch(
        "backend.tuition_service.services.tuition_service.get_tuition",
        return_value=paid_tuition
    ):
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(
                executor.map(
                    lambda _: pay_once(),
                    range(2)
                )
            )

    assert sorted(statuses) == [200, 409]


def test_concurrent_payment_claims_for_same_student_allow_one_payer(monkeypatch):
    monkeypatch.setattr(
        tuition_controller,
        "INTERNAL_API_KEY",
        TEST_INTERNAL_API_KEY
    )
    state = {"claim": None}
    lock = Lock()

    def create_connection():
        cursor = MagicMock()

        def execute(query, params=None):
            if "FROM tuition_payment_claims" in query and "claimed_at <" in query:
                cursor.fetchone.return_value = None
            elif "INSERT IGNORE INTO tuition_payment_claims" in query:
                transaction_id, student_id = params
                with lock:
                    if student_id == "524H0104" and state["claim"] is None:
                        state["claim"] = transaction_id
                        cursor.rowcount = 1
                    else:
                        cursor.rowcount = 0
            elif "SELECT status FROM tuition_bills" in query:
                cursor.fetchone.return_value = {"status": "UNPAID"}

        cursor.execute.side_effect = execute
        cursor_context = MagicMock()
        cursor_context.__enter__.return_value = cursor
        cursor_context.__exit__.return_value = False
        connection = MagicMock()
        connection.cursor.return_value = cursor_context
        return connection

    def claim_once(transaction_id):
        with TestClient(app) as concurrent_client:
            return concurrent_client.post(
                "/api/v1/tuition/524H0104/claim",
                headers=INTERNAL_API_HEADERS,
                json={"transaction_id": transaction_id},
            )

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        side_effect=create_connection,
    ):
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(claim_once, ["TX-PAYER-A", "TX-PAYER-B"]))

    assert sorted(response.status_code for response in responses) == [201, 409]
    assert state["claim"] in {"TX-PAYER-A", "TX-PAYER-B"}


def test_pay_tuition_without_internal_api_key_is_rejected(client):
    response = client.put(
        "/api/v1/tuition/524H0104/pay",
        json={"transaction_id": "TX-NO-KEY"},
    )

    assert response.status_code == 401


def test_tuition_lookup_requires_authentication(monkeypatch):
    monkeypatch.setattr(
        tuition_controller,
        "JWT_SECRET_KEY",
        TEST_INTERNAL_API_KEY
    )
    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.get("/api/v1/tuition")

    assert response.status_code == 401


def test_tuition_lookup_accepts_internal_api_key(client):
    tuition_data = {
        "student_id": "524H0012",
        "student_name": "Nguyen Minh Anh",
        "amount": Decimal("18500000.00"),
        "status": "UNPAID",
    }
    connection, _ = create_connection(fetchone=tuition_data)

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=connection,
    ):
        response = client.get(
            "/api/v1/tuition/524H0012",
            headers=INTERNAL_API_HEADERS,
        )

    assert response.status_code == 200


def test_pay_tuition_requires_transaction_claim(client):
    connection, cursor = create_connection(rowcount=1)
    cursor.fetchone.side_effect = [
        {"claim_count": 0, "transaction_id": None},
        {"status": "UNPAID"},
    ]

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=connection,
    ):
        response = client.put(
            "/api/v1/tuition/524H0104/pay",
            headers=INTERNAL_API_HEADERS,
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "No active tuition payment claim for this student",
    }


def test_pay_tuition_rejects_mismatched_transaction_claim(client):
    connection, cursor = create_connection(rowcount=1)
    cursor.fetchone.side_effect = [
        None,
        {"status": "UNPAID"},
    ]

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=connection,
    ):
        response = client.put(
            "/api/v1/tuition/524H0104/pay",
            headers=INTERNAL_API_HEADERS,
            json={"transaction_id": "TX-MISMATCHED"},
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "No active tuition payment claim for this transaction",
    }


def test_pay_tuition_with_wrong_internal_api_key_is_rejected(client):
    response = client.put(
        "/api/v1/tuition/524H0104/pay",
        headers={"X-Internal-API-Key": "wrong-key"},
        json={"transaction_id": "TX-WRONG-KEY"},
    )

    assert response.status_code == 401


def test_pay_tuition_with_valid_internal_api_key_runs_business_logic(client):
    paid_tuition = {
        "student_id": "524H0104",
        "student_name": "Pham Ngoc Han",
        "amount": Decimal("17300000.00"),
        "status": "PAID"
    }

    with patch(
        "backend.tuition_service.controllers.tuition_controller.mark_tuition_as_paid",
        return_value=paid_tuition
    ) as mark_paid:
        response = client.put(
            "/api/v1/tuition/524H0104/pay",
            headers=INTERNAL_API_HEADERS,
            json={"transaction_id": "TX-VALID-104"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "PAID"
    mark_paid.assert_called_once_with("524H0104", "TX-VALID-104")


def test_release_claim_is_idempotent(client):
    first_connection, first_cursor = create_connection(rowcount=1)
    second_connection, second_cursor = create_connection(rowcount=0)

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        side_effect=[first_connection, second_connection],
    ):
        first_response = client.delete(
            "/api/v1/tuition/524H0104/claim/TX-RELEASE-104",
            headers=INTERNAL_API_HEADERS,
        )
        second_response = client.delete(
            "/api/v1/tuition/524H0104/claim/TX-RELEASE-104",
            headers=INTERNAL_API_HEADERS,
        )

    assert first_response.status_code == 200
    assert first_response.json() == {"released": True}
    assert second_response.status_code == 200
    assert second_response.json() == {"released": False}
    assert first_cursor.execute.call_args[0][1] == (
        "524H0104",
        "TX-RELEASE-104",
    )
    assert second_cursor.execute.call_args[0][1] == (
        "524H0104",
        "TX-RELEASE-104",
    )


@pytest.mark.parametrize(
    ("row", "expected_state", "expected_active"),
    [
        ({"is_active": 1}, "ACTIVE", True),
        ({"is_active": 0}, "EXPIRED", False),
        (None, "NOT_FOUND", False),
    ],
)
def test_get_claim_status(client, row, expected_state, expected_active):
    connection, _ = create_connection(fetchone=row)

    with patch(
        "backend.tuition_service.services.tuition_service.get_tuition_connection",
        return_value=connection,
    ):
        response = client.get(
            "/api/v1/tuition/524H0104/claim/TX-STATUS-104",
            headers=INTERNAL_API_HEADERS,
        )

    assert response.status_code == 200
    assert response.json() == {
        "student_id": "524H0104",
        "transaction_id": "TX-STATUS-104",
        "state": expected_state,
        "active": expected_active,
    }


def test_release_claim_with_wrong_internal_api_key_is_rejected(client):
    response = client.delete(
        "/api/v1/tuition/524H0104/claim/TX-WRONG-KEY",
        headers={"X-Internal-API-Key": "wrong-key"},
    )

    assert response.status_code == 401


def test_get_claim_status_with_wrong_internal_api_key_is_rejected(client):
    response = client.get(
        "/api/v1/tuition/524H0104/claim/TX-WRONG-KEY",
        headers={"X-Internal-API-Key": "wrong-key"},
    )

    assert response.status_code == 401
