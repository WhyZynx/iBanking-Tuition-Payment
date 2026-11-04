from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.user_service.controllers.account_controller import (
    internal_debit_router,
    internal_router as internal_account_router,
)
from backend.user_service.controllers.account_controller import router as account_router
from backend.user_service.controllers.auth_controller import router as auth_router
from backend.user_service.controllers.user_controller import router as user_router
from backend.user_service.database import Base, engine
from backend.user_service.models import Account, User


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="iBanking User & Account Service",
    version="1.0.0",
    description="Student 1 service for authentication, users, accounts, and atomic debit operations.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Internal-API-Key"],
)
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(account_router)
app.include_router(internal_account_router)
app.include_router(internal_debit_router)


@app.get("/health", tags=["Health"], summary="Check service health")
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}
