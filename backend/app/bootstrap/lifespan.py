"""Application startup wiring; schema migrations remain an explicit operation."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool
from sqlmodel import Session

from app.adapters.outbound.persistence.database import engine
from app.bootstrap.users import build_ensure_default_roles


def initialize_roles() -> None:
    with Session(engine) as session:
        build_ensure_default_roles(session).execute()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_in_threadpool(initialize_roles)
    yield
