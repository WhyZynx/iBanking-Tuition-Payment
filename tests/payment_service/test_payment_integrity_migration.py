from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def payment_schema(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'payment-integrity.db'}")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(text("""
            CREATE TABLE transactions (
                transaction_id VARCHAR(36) PRIMARY KEY,
                payer_user_id BIGINT NOT NULL,
                source_account_number VARCHAR(20) NOT NULL,
                student_id VARCHAR(20) NOT NULL,
                student_name VARCHAR(255),
                amount DECIMAL(15, 2),
                status VARCHAR(32) NOT NULL,
                reconciliation_code VARCHAR(64) NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE otps (
                otp_id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id VARCHAR(36) NOT NULL,
                otp_code VARCHAR(10) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                is_used BOOLEAN NOT NULL DEFAULT FALSE,
                CONSTRAINT fk_otps_transaction FOREIGN KEY (transaction_id)
                    REFERENCES transactions(transaction_id)
            )
        """))
        connection.execute(text("""
            INSERT INTO transactions (
                transaction_id, payer_user_id, source_account_number,
                student_id, amount, status
            ) VALUES ('tx-1', 7, 'acct-1', 'student-1', NULL, 'PENDING')
        """))
    yield engine
    engine.dispose()


def test_payment_schema_has_required_transaction_and_otp_constraints(payment_schema):
    inspector = inspect(payment_schema)
    transaction_columns = {
        column["name"]: column for column in inspector.get_columns("transactions")
    }
    otp_columns = {column["name"]: column for column in inspector.get_columns("otps")}

    for name in (
        "payer_user_id", "source_account_number", "student_id", "status", "created_at"
    ):
        assert transaction_columns[name]["nullable"] is False
    assert transaction_columns["amount"]["nullable"] is True
    assert transaction_columns["reconciliation_code"]["nullable"] is True
    assert transaction_columns["completed_at"]["nullable"] is True

    for name in ("transaction_id", "otp_code", "expires_at", "is_used"):
        assert otp_columns[name]["nullable"] is False
    assert inspector.get_foreign_keys("otps") == [
        {
            "name": "fk_otps_transaction",
            "constrained_columns": ["transaction_id"],
            "referred_schema": None,
            "referred_table": "transactions",
            "referred_columns": ["transaction_id"],
            "options": {},
        }
    ]


@pytest.mark.parametrize(
    "column",
    ["payer_user_id", "source_account_number", "student_id", "status", "created_at"],
)
def test_transaction_required_fields_reject_null(payment_schema, column):
    with pytest.raises(IntegrityError):
        with payment_schema.begin() as connection:
            connection.execute(
                text(f"UPDATE transactions SET `{column}` = NULL WHERE transaction_id = 'tx-1'")
            )


@pytest.mark.parametrize("column", ["transaction_id", "otp_code", "expires_at", "is_used"])
def test_otp_required_fields_reject_null(payment_schema, column):
    with pytest.raises(IntegrityError):
        with payment_schema.begin() as connection:
            connection.execute(
                text(f"INSERT INTO otps (transaction_id, otp_code, expires_at, is_used) "
                     f"VALUES ('tx-1', '123456', CURRENT_TIMESTAMP, FALSE)")
            )
            connection.execute(text(f"UPDATE otps SET `{column}` = NULL WHERE otp_id = 1"))


def test_orphan_otp_is_rejected(payment_schema):
    with pytest.raises(IntegrityError):
        with payment_schema.begin() as connection:
            connection.execute(text("""
                INSERT INTO otps (transaction_id, otp_code, expires_at)
                VALUES ('missing-transaction', '123456', CURRENT_TIMESTAMP)
            """))


def test_pending_transaction_can_keep_null_amount(payment_schema):
    with payment_schema.connect() as connection:
        amount = connection.execute(
            text("SELECT amount FROM transactions WHERE transaction_id='tx-1'")
        ).scalar_one()
    assert amount is None


def test_canonical_payment_schema_upgrades_legacy_tables_safely():
    schema = Path("db/payment/payment_init.sql").read_text(
        encoding="utf-8"
    )
    assert "ADD COLUMN reconciliation_code VARCHAR(64) NULL" in schema
    assert "ADD COLUMN student_name VARCHAR(255) NULL" in schema
    assert "SIGNAL SQLSTATE '45000'" in schema
    assert "LEFT JOIN transactions" in schema
    assert "ADD CONSTRAINT fk_otps_transaction" in schema
    assert "ON DELETE CASCADE" not in schema.upper()
    assert "UPDATE transactions" not in schema.upper()
    assert "UPDATE otps" not in schema.upper()


def test_docker_uses_the_canonical_payment_schema():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "./db/payment/payment_init.sql:/docker-entrypoint-initdb.d/04-payment-init.sql:ro" in compose


def test_student_id_migration_is_safe_to_resume_after_partial_ddl():
    migration = Path("db/user/add_user_student_id.sql").read_text(encoding="utf-8")
    assert "information_schema.columns" in migration
    assert "IF has_student_id = 0 THEN" in migration
    assert "information_schema.statistics" in migration
    assert "IF has_student_id_unique_index = 0 THEN" in migration
    assert "CALL upgrade_user_student_id();" in migration


def test_setup_runners_verify_schema_before_recording_migrations():
    powershell = Path("setup-db.ps1").read_text(encoding="utf-8")
    shell = Path("setup-db.sh").read_text(encoding="utf-8")

    assert powershell.index(
        "$schemaValid = Test-MigrationSchema $migration.Version"
    ) < powershell.index(
        'Invoke-MySql "INSERT INTO $($migration.Database).schema_migrations'
    )
    assert shell.index(
        'if migration_is_valid "$version"; then'
    ) < shell.index(
        'mysql_query "INSERT INTO ${database}.schema_migrations'
    )
    for runner in (powershell, shell):
        assert "information_schema.statistics" in runner
        assert "information_schema.key_column_usage" in runner
        assert "information_schema.check_constraints" in runner
        assert "schema was verified" in runner.lower()
