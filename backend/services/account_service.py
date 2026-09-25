from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.models.account import Account
from backend.schemas.account_schema import DebitRequest


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
    account = get_internal_account(db, account_number)
    if account.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account is inactive")

    result = db.execute(
        update(Account)
        .where(
            Account.account_number == account_number,
            Account.status == "ACTIVE",
            Account.balance >= debit.amount,
        )
        .values(balance=Account.balance - debit.amount)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Insufficient available balance")

    db.commit()
    db.refresh(account)
    return account