from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    account_number: str = Field(serialization_alias="accountNumber")
    balance: Decimal
    is_default: bool = Field(serialization_alias="isDefault")
    status: str

    @field_serializer("balance")
    def serialize_balance(self, balance: Decimal) -> float:
        return float(balance)


class InternalAccountResponse(AccountResponse):
    user_id: int = Field(serialization_alias="userId")


class DebitRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    transaction_id: str = Field(alias="transactionId", min_length=1, max_length=100)

    model_config = ConfigDict(populate_by_name=True)


class DebitResponse(BaseModel):
    success: bool = True
    account_number: str = Field(serialization_alias="accountNumber")
    remaining_balance: Decimal = Field(serialization_alias="remainingBalance")

    @field_serializer("remaining_balance")
    def serialize_remaining_balance(self, balance: Decimal) -> float:
        return float(balance)