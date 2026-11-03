import subprocess
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Barrier

import requests


BASE_URL = "http://localhost:8080"
ACCOUNT_NUMBER = "6202000001"
STUDENT_IDS = ("524H0001", "524H0002")
TIMEOUT = 10


def mysql_password():
    env_path = Path(__file__).resolve().parents[2] / ".env.docker"
    for line in env_path.read_text().splitlines():
        if line.startswith("MYSQL_ROOT_PASSWORD="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("MYSQL_ROOT_PASSWORD is missing from .env.docker")


def mysql_query(database, sql):
    password = mysql_password()
    result = subprocess.run(
        [
            "docker",
            "exec",
            "ibanking-demo-mysql-1",
            "mysql",
            "-uroot",
            f"-p{password}",
            "-N",
            "-B",
            "-e",
            f"USE {database}; {sql}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def setup_demo_database():
    mysql_query(
        "ibanking_account_db",
        "DELETE FROM account_debits "
        f"WHERE account_number='{ACCOUNT_NUMBER}';",
    )
    tuition_amounts = []
    for student_id in STUDENT_IDS:
        mysql_query(
            "ibanking_tuition_db",
            "UPDATE tuition_bills "
            "SET status='UNPAID' "
            f"WHERE student_id='{student_id}';",
        )
        amount = mysql_query(
            "ibanking_tuition_db",
            "SELECT CAST(amount AS CHAR) FROM tuition_bills "
            f"WHERE student_id='{student_id}';",
        )
        tuition_amounts.append(Decimal(amount))
    mysql_query(
        "ibanking_payment_db",
        "DELETE o FROM otps o JOIN transactions t "
        "ON t.transaction_id=o.transaction_id "
        "WHERE payer_user_id=1 "
        "AND t.student_id IN ('524H0001','524H0002');",
    )
    mysql_query(
        "ibanking_payment_db",
        "DELETE FROM transactions "
        "WHERE payer_user_id=1 "
        "AND student_id IN ('524H0001','524H0002');",
    )


def get_unused_otp(transaction_id):
    otp_code = mysql_query(
        "ibanking_payment_db",
        "SELECT otp_code FROM otps "
        "WHERE transaction_id='{}' AND is_used=FALSE "
        "ORDER BY otp_id DESC LIMIT 1;".format(transaction_id),
    )
    if not otp_code:
        raise RuntimeError(f"OTP not found for transaction {transaction_id}")
    return otp_code


def test_concurrent_payments_same_account_two_students_no_overdraft():
    setup_demo_database()
    initial_balance = mysql_query(
        "ibanking_account_db",
        "SELECT CAST(balance AS CHAR) FROM accounts "
        f"WHERE account_number='{ACCOUNT_NUMBER}';",
    )
    tuition_amounts = {}
    for student_id in STUDENT_IDS:
        tuition_amounts[student_id] = Decimal(mysql_query(
            "ibanking_tuition_db",
            "SELECT CAST(amount AS CHAR) FROM tuition_bills "
            f"WHERE student_id='{student_id}';",
        ))
    assert all(
        amount <= Decimal(initial_balance) for amount in tuition_amounts.values()
    )
    assert sum(tuition_amounts.values(), Decimal("0")) > Decimal(initial_balance)

    login_response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"username": "user01", "password": "password123"},
        timeout=TIMEOUT,
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    def create_payment(student_id):
        return requests.post(
            f"{BASE_URL}/api/v1/payments",
            headers=headers,
            json={
                "student_id": student_id,
                "account_number": ACCOUNT_NUMBER,
            },
            timeout=TIMEOUT,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        create_results = list(executor.map(create_payment, STUDENT_IDS))

    assert all(response.status_code == 201 for response in create_results), [
        response.text for response in create_results
    ]

    transaction_ids = [
        response.json()["transaction_id"] for response in create_results
    ]

    otp_results = []
    for transaction_id in transaction_ids:
        otp_results.append(requests.post(
            f"{BASE_URL}/api/v1/payments/{transaction_id}/otp",
            headers=headers,
            timeout=TIMEOUT,
        ))

    assert all(response.status_code == 200 for response in otp_results), [
        response.text for response in otp_results
    ]

    otp_codes = {
        transaction_id: get_unused_otp(transaction_id)
        for transaction_id in transaction_ids
    }
    confirm_barrier = Barrier(2)

    def confirm_payment(transaction_id):
        confirm_barrier.wait(timeout=5)
        return requests.post(
            f"{BASE_URL}/api/v1/payments/confirm",
            headers=headers,
            json={
                "transactionId": transaction_id,
                "otpCode": otp_codes[transaction_id],
            },
            timeout=TIMEOUT,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        confirm_results = list(
            executor.map(confirm_payment, transaction_ids)
        )

    status_codes = sorted(response.status_code for response in confirm_results)

    balance = mysql_query(
        "ibanking_account_db",
        "SELECT CAST(balance AS CHAR) FROM accounts "
        f"WHERE account_number='{ACCOUNT_NUMBER}';",
    )

    tuition_statuses = {}
    for student_id in STUDENT_IDS:
        tuition_statuses[student_id] = mysql_query(
            "ibanking_tuition_db",
            f"SELECT status FROM tuition_bills "
            f"WHERE student_id='{student_id}';",
        )

    debit_count = mysql_query(
        "ibanking_account_db",
        "SELECT COUNT(*) FROM account_debits "
        "WHERE transaction_id IN ('{}','{}');".format(*transaction_ids),
    )
    debit_total = mysql_query(
        "ibanking_account_db",
        "SELECT COALESCE(CAST(SUM(amount) AS CHAR),'0.00') FROM account_debits "
        "WHERE transaction_id IN ('{}','{}');".format(*transaction_ids),
    )

    print("\n========== TC11 TEST RESULT ==========")
    print(f"Account: {ACCOUNT_NUMBER}")
    print(f"Initial balance: {initial_balance} VND")
    for student_id in STUDENT_IDS:
        print(f"{student_id}: {tuition_amounts[student_id]} VND UNPAID")
    print(f"Transactions: {transaction_ids}")
    print(f"Concurrent confirm results: {status_codes}")
    print(f"Successful debits: {debit_count}")
    print(f"Tuition statuses: {tuition_statuses}")
    print(f"Final balance: {balance} VND")
    print("======================================\n")

    assert status_codes == [200, 409], status_codes
    assert int(debit_count) == 1
    assert Decimal(debit_total) in {
        tuition_amounts[STUDENT_IDS[0]],
        tuition_amounts[STUDENT_IDS[1]],
    }
    assert Decimal(initial_balance) - Decimal(debit_total) == Decimal(balance)
    assert sum(status == "PAID" for status in tuition_statuses.values()) == 1
    assert sum(status == "UNPAID" for status in tuition_statuses.values()) == 1
