from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.mysql import TIMESTAMP as MySQLTimestamp
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.user_service.database import Base

if TYPE_CHECKING:
    from backend.user_service.models.user import User


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("balance >= 0", name="chk_accounts_balance_nonnegative"),)

    account_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id"), nullable=False, index=True
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("FALSE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="ACTIVE", server_default=text("'ACTIVE'"), nullable=False
    )
    user: Mapped["User"] = relationship(back_populates="accounts")


class AccountDebit(Base):
    __tablename__ = "account_debits"
    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_account_debits_amount"),
        CheckConstraint("balance_after >= 0", name="chk_account_debits_balance"),
    )

    transaction_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    account_number: Mapped[str] = mapped_column(
        ForeignKey("accounts.account_number"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(MySQLTimestamp(), "mysql"),
        server_default=func.now(),
        nullable=False,
    )
