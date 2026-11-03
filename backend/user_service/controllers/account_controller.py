import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.user_service.config import INTERNAL_API_KEY
from backend.user_service.database import get_db
from backend.user_service.dependencies import get_current_user
from backend.user_service.models.user import User
from backend.user_service.schemas.account_schema import (
    AccountResponse,
    DebitRequest,
    DebitResponse,
    DebitStatusResponse,
    InternalAccountResponse,
)
from backend.user_service.services.account_service import (
    debit_account,
    get_debit_status,
    get_internal_account,
    get_user_accounts,
)


def require_internal_api_key(x_internal_api_key: str | None = Header(default=None)) -> None:
    if not hmac.compare_digest(x_internal_api_key or "", INTERNAL_API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal API key")


router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])
internal_router = APIRouter(
    prefix="/api/v1/internal/accounts",
    tags=["Internal Accounts"],
    dependencies=[Depends(require_internal_api_key)],
)
internal_debit_router = APIRouter(
    prefix="/api/v1/internal/debits",
    tags=["Internal Debits"],
    dependencies=[Depends(require_internal_api_key)],
)


@router.get("/me", response_model=list[AccountResponse], summary="List the authenticated user's accounts")
def get_my_accounts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AccountResponse]:
    accounts = get_user_accounts(db, user.user_id)
    return [AccountResponse.model_validate(account) for account in accounts]


@internal_router.get(
    "/{account_number}",
    response_model=InternalAccountResponse,
    summary="Get an account for service-to-service use",
)
def get_account_for_service(
    account_number: str,
    db: Session = Depends(get_db),
) -> InternalAccountResponse:
    account = get_internal_account(db, account_number)
    return InternalAccountResponse.model_validate(account)


@internal_router.post(
    "/{account_number}/debit",
    response_model=DebitResponse,
    status_code=status.HTTP_200_OK,
    summary="Atomically debit an active account",
)
def debit_account_for_service(
    account_number: str,
    payload: DebitRequest,
    db: Session = Depends(get_db),
) -> DebitResponse:
    account = debit_account(db, account_number, payload)
    return DebitResponse(account_number=account.account_number, remaining_balance=account.balance)


@internal_debit_router.get(
    "/{transaction_id}",
    response_model=DebitStatusResponse,
    summary="Read the status of an account debit",
)
def get_debit_status_for_service(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> DebitStatusResponse:
    debit_status = get_debit_status(db, transaction_id)
    return DebitStatusResponse(transaction_id=transaction_id, status=debit_status)
