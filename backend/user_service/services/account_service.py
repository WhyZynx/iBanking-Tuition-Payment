import logging
from decimal import Decimal
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm import Session

from backend.user_service.models.account import Account, AccountDebit
from backend.user_service.schemas.account_schema import DebitRequest


MYSQL_LOCK_ERROR_CODES = {1205, 1213}
ACCOUNT_NOT_FOUND_DETAIL = {
    "code": "ACCOUNT_NOT_FOUND",
    "message": "Account not found.",
}
ACCOUNT_INACTIVE_DETAIL = {
    "code": "ACCOUNT_INACTIVE",
    "message": "Account is inactive.",
}
INSUFFICIENT_BALANCE_DETAIL = {
    "code": "INSUFFICIENT_BALANCE",
    "message": "Insufficient available balance.",
}
TRANSACTION_ID_CONFLICT_DETAIL = {
    "code": "TRANSACTION_ID_CONFLICT",
    "message": "Transaction ID was already used for a different debit.",
}
DEBIT_ROLLED_BACK_DETAIL = {
    "code": "DEBIT_ROLLED_BACK",
    "message": "Debit was rolled back successfully.",
}
DEBIT_OUTCOME_UNKNOWN_DETAIL = {
    "code": "DEBIT_OUTCOME_UNKNOWN",
    "message": "Debit outcome could not be confirmed.",
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


def _get_debit_account(db: Session, account_number: str) -> Account:
    try:
        return get_internal_account(db, account_number)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ACCOUNT_NOT_FOUND_DETAIL,
            ) from exc
        raise


def get_debit_status(
    db: Session, transaction_id: str
) -> Literal["DEBITED", "NOT_FOUND"]:
    found_transaction_id = db.scalar(
        select(AccountDebit.transaction_id).where(
            AccountDebit.transaction_id == transaction_id
        )
    )
    return "DEBITED" if found_transaction_id is not None else "NOT_FOUND"


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
                detail=TRANSACTION_ID_CONFLICT_DETAIL,
            )
        account = _get_debit_account(db, account_number)
        account.balance = previous_debit.balance_after
        return account

    account = _get_debit_account(db, account_number)
    if account.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ACCOUNT_INACTIVE_DETAIL,
        )

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
            try:
                db.rollback()
            except Exception as rollback_error:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=DEBIT_OUTCOME_UNKNOWN_DETAIL,
                ) from rollback_error
            previous_debit = db.get(AccountDebit, debit.transaction_id)
            if previous_debit is None:
                raise
            if (
                previous_debit.account_number != account_number
                or previous_debit.amount != debit.amount
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=TRANSACTION_ID_CONFLICT_DETAIL,
                )
            account = _get_debit_account(db, account_number)
            account.balance = previous_debit.balance_after
            return account

        result = db.connection().execute(
            update(Account)
            .where(
                Account.account_number == account_number,
                Account.status == "ACTIVE",
                Account.balance >= debit.amount,
            )
            .values(balance=Account.balance - debit.amount)
        )
        if result.rowcount != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=INSUFFICIENT_BALANCE_DETAIL,
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
