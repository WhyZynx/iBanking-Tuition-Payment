from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.user_service.models.account import Account, AccountDebit
from backend.user_service.schemas.account_schema import DebitRequest


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

    try:
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
            db.rollback()
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
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(account)
    return account
