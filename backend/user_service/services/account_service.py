import logging
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm import Session

from backend.user_service.models.account import Account, AccountDebit
from backend.user_service.schemas.account_schema import DebitRequest


MYSQL_LOCK_ERROR_CODES = {1205, 1213}
DEBIT_ROLLED_BACK_DETAIL = {
    "code": "DEBIT_ROLLED_BACK",
    "message": (
        "Database is temporarily unavailable; debit was rolled back. "
        "Retry with the same transaction ID"
    ),
}
DEBIT_OUTCOME_UNKNOWN_DETAIL = {
    "code": "DEBIT_OUTCOME_UNKNOWN",
    "message": (
        "Debit outcome could not be confirmed; reconcile before retrying with the "
        "same transaction ID"
    ),
}
logger = logging.getLogger(__name__)


def _mysql_error_code(error: OperationalError) -> int | None:
    original_error = error.orig
    error_args = getattr(original_error, "args", ())
    if not error_args:
        return None
    try:
        return int(error_args[0])
    except (TypeError, ValueError):
        return None


def get_user_accounts(db: Session, user_id: int) -> list[Account]:
    return list(
        db.scalars(
            select(Account)
            .where(Account.user_id == user_id)
            .order_by(Account.is_default.desc(), Account.account_number)
        )
    )


def get_internal_account(db: Session, account_number: str) -> Account:
    account = db.get(Account, account_number)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


def debit_account(db: Session, account_number: str, debit: DebitRequest) -> Account:
    return _debit_account(db, account_number, debit)


def _debit_account(db: Session, account_number: str, debit: DebitRequest) -> Account:
    previous_debit = db.get(AccountDebit, debit.transaction_id)
    if previous_debit is not None:
        if (
            previous_debit.account_number != account_number
            or previous_debit.amount != debit.amount
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transaction ID was already used for a different debit",
            )
        account = get_internal_account(db, account_number)
        account.balance = previous_debit.balance_after
        return account

    account = get_internal_account(db, account_number)
    if account.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account is inactive")

    debit_record = AccountDebit(
        transaction_id=debit.transaction_id,
        account_number=account_number,
        amount=debit.amount,
        balance_after=Decimal("0.00"),
    )
    db.add(debit_record)

    try:
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            previous_debit = db.get(AccountDebit, debit.transaction_id)
            if previous_debit is None:
                raise
            if (
                previous_debit.account_number != account_number
                or previous_debit.amount != debit.amount
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Transaction ID was already used for a different debit",
                )
            account = get_internal_account(db, account_number)
            account.balance = previous_debit.balance_after
            return account

        result = db.execute(
            update(Account)
            .where(
                Account.account_number == account_number,
                Account.status == "ACTIVE",
                Account.balance >= debit.amount,
            )
            .values(balance=Account.balance - debit.amount)
        )
        if not isinstance(result, CursorResult):
            raise RuntimeError("Account debit UPDATE did not return a cursor result")
        if result.rowcount != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Insufficient available balance",
            )

        balance_after = db.scalar(
            select(Account.balance).where(Account.account_number == account_number)
        )
        if balance_after is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Updated account balance could not be retrieved",
            )

        debit_record.balance_after = balance_after
    except Exception as exc:
        try:
            db.rollback()
        except Exception as rollback_error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=DEBIT_OUTCOME_UNKNOWN_DETAIL,
            ) from rollback_error

        if (
            isinstance(exc, OperationalError)
            and _mysql_error_code(exc) in MYSQL_LOCK_ERROR_CODES
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=DEBIT_ROLLED_BACK_DETAIL,
            ) from exc
        raise

    try:
        db.commit()
    except Exception as exc:
        try:
            db.rollback()
        except Exception as rollback_error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=DEBIT_OUTCOME_UNKNOWN_DETAIL,
            ) from rollback_error
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DEBIT_OUTCOME_UNKNOWN_DETAIL,
        ) from exc

    try:
        db.refresh(account)
    except Exception:
        logger.warning(
            "Account refresh failed after debit commit; returning committed balance"
        )
        try:
            db.rollback()
        except Exception:
            logger.warning("Could not clean up the session after account refresh failure")
        set_committed_value(account, "account_number", account_number)
        set_committed_value(account, "balance", balance_after)
    return account
