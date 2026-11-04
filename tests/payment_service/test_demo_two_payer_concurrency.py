"""One-shot concurrency demonstration against the local demo stack.

This test performs a real payment and leaves the selected tuition bill PAID.
Use only a disposable local demo database with a currently UNPAID bill.
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
from pathlib import Path
import re
import subprocess
from threading import Barrier
from urllib.parse import urlparse

import pytest
import requests



PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.getenv("IBANKING_DEMO_BASE_URL", "http://localhost:8080").rstrip("/")
FIRST_USERNAME = os.getenv("IBANKING_DEMO_FIRST_USERNAME", "user08")
FIRST_PASSWORD = os.getenv("IBANKING_DEMO_FIRST_PASSWORD", "password123")
SECOND_USERNAME = os.getenv("IBANKING_DEMO_SECOND_USERNAME", "user04")
SECOND_PASSWORD = os.getenv("IBANKING_DEMO_SECOND_PASSWORD", "password123")
STUDENT_ID = os.getenv("IBANKING_DEMO_STUDENT_ID", "524H0004")
TIMEOUT = 15


def mysql_query(sql: str) -> str:
    env_file = PROJECT_ROOT / ".env.docker"
    if not env_file.is_file():
        pytest.fail("Missing .env.docker; start/configure the local demo stack first.")

    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-p",
            "ibanking-demo",
            "exec",
            "-T",
            "mysql",
            "sh",
            "-c",
            'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -uroot --batch --skip-column-names',
        ],
        input=f"{sql}\n",
        check=False,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        cwd=PROJECT_ROOT,
    )
    if result.returncode:
        pytest.fail(
            "Could not query the local demo MySQL container. "
            "Start it with ./setup.sh and check Docker Compose logs.\n"
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def login(username: str, password: str) -> dict[str, str]:
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"username": username, "password": password},
        timeout=TIMEOUT,
    )
    assert response.status_code == 200, f"Login failed for {username}: {response.text}"
    token = response.json().get("access_token")
    assert isinstance(token, str) and token, f"No access token returned for {username}"
    return {"Authorization": f"Bearer {token}"}


def payment_account(headers: dict[str, str], amount: Decimal) -> dict:
    response = requests.get(
        f"{BASE_URL}/api/v1/accounts/me",
        headers=headers,
        timeout=TIMEOUT,
    )
    assert response.status_code == 200, f"Could not list accounts: {response.text}"
    accounts = response.json()
    eligible = [
        account
        for account in accounts
        if account["status"] == "ACTIVE"
    and Decimal(str(account["balance"])) >= amount
    ]

    if not eligible:
            pytest.skip(
                f"No ACTIVE account has enough balance for "
                f"{amount} VND."
            )
    return next((account for account in eligible if account["isDefault"]), eligible[0])


def get_otp(transaction_id: str) -> str:
    assert re.fullmatch(r"[0-9a-fA-F-]{36}", transaction_id), "Invalid transaction ID"
    code = mysql_query(
        "USE ibanking_payment_db;\n"
        "SELECT otp_code FROM otps "
        f"WHERE transaction_id='{transaction_id}' AND is_used=FALSE "
        "ORDER BY otp_id DESC LIMIT 1;"
    )
    assert re.fullmatch(r"\d{6}", code), f"Could not find an unused OTP for {transaction_id}"
    return code

def validate_demo_preconditions(
    first_headers: dict[str, str],
    second_headers: dict[str, str],
) -> tuple[dict, dict, Decimal]:
    """Validate demo data before creating real payment transactions."""

    if FIRST_USERNAME == SECOND_USERNAME:
        pytest.skip("Two different demo users are required.")

    tuition_response = requests.get(
        f"{BASE_URL}/api/v1/tuition/{STUDENT_ID}",
        headers=first_headers,
        timeout=TIMEOUT,
    )

    assert tuition_response.status_code == 200, (
        f"Tuition lookup failed for {STUDENT_ID}: "
        f"{tuition_response.text}"
    )

    tuition = tuition_response.json()

    if tuition.get("status") != "UNPAID":
        pytest.skip(
            f"Tuition bill {STUDENT_ID} is not UNPAID. "
            f"Current status: {tuition.get('status')}."
        )

    amount = Decimal(str(tuition["amount"]))

    if not amount.is_finite() or amount <= 0:
        pytest.skip(
            f"Invalid tuition amount for {STUDENT_ID}: {amount}."
        )

    first_account = payment_account(first_headers, amount)
    second_account = payment_account(second_headers, amount)

    if first_account["accountNumber"] == second_account["accountNumber"]:
        pytest.skip(
            "The two demo users must use different bank accounts."
        )

    initial_balances = {
        first_account["accountNumber"]: Decimal(
            str(first_account["balance"])
        ),
        second_account["accountNumber"]: Decimal(
            str(second_account["balance"])
        ),
    }

    return first_account, second_account, amount


@pytest.mark.demo_live
def test_two_demo_accounts_concurrently_pay_the_same_tuition():
    if os.getenv("IBANKING_DEMO_CONCURRENCY_APPROVAL") != "YES":
        pytest.fail(
            "This test makes real payments and modifies the demo database. "
            "Use a disposable demo database and set "
            "IBANKING_DEMO_CONCURRENCY_APPROVAL=YES."
        )

    parsed_url = urlparse(BASE_URL)

    if parsed_url.scheme != "http" or parsed_url.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        pytest.fail(
            "The demo test only permits an HTTP service on this computer."
        )

    mysql_query("SELECT 1;")

    first_headers = login(FIRST_USERNAME, FIRST_PASSWORD)
    second_headers = login(SECOND_USERNAME, SECOND_PASSWORD)

    first_account, second_account, amount = validate_demo_preconditions(
        first_headers,
        second_headers,
    )

    initial_balances = {
        first_account["accountNumber"]: Decimal(
            str(first_account["balance"])
        ),
        second_account["accountNumber"]: Decimal(
            str(second_account["balance"])
        ),
    }

    transactions = []
    for headers, account in (
        (first_headers, first_account),
        (second_headers, second_account),
    ):
        response = requests.post(
            f"{BASE_URL}/api/v1/payments",
            headers=headers,
            json={
                "student_id": STUDENT_ID,
                "account_number": account["accountNumber"],
            },
            timeout=TIMEOUT,
        )
        assert response.status_code == 201, f"Could not create payment: {response.text}"
        transactions.append(
            {
                "id": response.json()["transaction_id"],
                "headers": headers,
                "account": account["accountNumber"],
            }
        )

    for transaction in transactions:
        response = requests.post(
            f"{BASE_URL}/api/v1/payments/{transaction['id']}/otp",
            headers=transaction["headers"],
            timeout=TIMEOUT,
        )
        assert response.status_code == 200, f"Could not request OTP: {response.text}"
        transaction["otp"] = get_otp(transaction["id"])

    barrier = Barrier(2)

    def confirm(transaction: dict) -> requests.Response:
        barrier.wait(timeout=10)
        return requests.post(
            f"{BASE_URL}/api/v1/payments/confirm",
            headers=transaction["headers"],
            json={
                "transactionId": transaction["id"],
                "otpCode": transaction["otp"],
            },
            timeout=TIMEOUT,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(confirm, transactions))

    assert sorted(response.status_code for response in responses) == [200, 409], [
        f"HTTP {response.status_code}: {response.text}" for response in responses
    ]

    for transaction in transactions:
        response = requests.get(
            f"{BASE_URL}/api/v1/payments/{transaction['id']}",
            headers=transaction["headers"],
            timeout=TIMEOUT,
        )
        assert response.status_code == 200, f"Could not read payment: {response.text}"
        transaction["status"] = response.json()["status"]

        history_response = requests.get(
            f"{BASE_URL}/api/v1/transactions/me",
            headers=transaction["headers"],
            timeout=TIMEOUT,
        )
        assert history_response.status_code == 200, (
            f"Could not read payment history: {history_response.text}"
        )
        history = history_response.json().get("items", [])
        matching = [
            item for item in history if item.get("transactionId") == transaction["id"]
        ]
        assert len(matching) == 1, "Transaction missing or duplicated in history"
        transaction["history_status"] = matching[0]["status"]

    assert sorted(transaction["status"] for transaction in transactions) == [
        "FAILED",
        "SUCCESS",
    ], [transaction["status"] for transaction in transactions]
    assert all(
        transaction["history_status"] == transaction["status"]
        for transaction in transactions
    ), "Payment history does not match transaction status"

    final_balances = {}
    for transaction in transactions:
        response = requests.get(
            f"{BASE_URL}/api/v1/accounts/me",
            headers=transaction["headers"],
            timeout=TIMEOUT,
        )
        assert response.status_code == 200, f"Could not verify balances: {response.text}"
        account = next(
            item
            for item in response.json()
            if item["accountNumber"] == transaction["account"]
        )
        final_balances[transaction["account"]] = Decimal(str(account["balance"]))

    balance_changes = {
        account: initial_balances[account] - final_balances[account]
        for account in initial_balances
    }
    assert sorted(balance_changes.values()) == [Decimal("0"), amount], balance_changes

    final_tuition_response = requests.get(
        f"{BASE_URL}/api/v1/tuition/{STUDENT_ID}",
        headers=first_headers,
        timeout=TIMEOUT,
    )
    assert final_tuition_response.status_code == 200
    assert final_tuition_response.json()["status"] == "PAID"

    print("\n========== TWO-PAYER CONCURRENCY RESULT ==========")
    print(f"Student: {STUDENT_ID} | Tuition: {amount} VND | Status: PAID")
    for transaction in transactions:
        print(
            f"Transaction {transaction['id']}: {transaction['status']} "
            f"(history: {transaction['history_status']})"
        )
    for account, balance in initial_balances.items():
        print(
            f"Account {account}: {balance} -> {final_balances[account]} VND "
            f"(debited {balance_changes[account]} VND)"
        )
    print("==================================================\n")