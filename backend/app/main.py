from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.core.database import initialize_database
from app.domains.articles.intern_router import router as article_admin_router
from app.domains.articles.public_router import router as article_router
from app.domains.users.router import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Startup
    initialize_database()

    yield

    # Shutdown


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
    ],
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
)


app.include_router(user_router)
app.include_router(article_router)
app.include_router(article_admin_router)
app.include_router(auth_router)


@app.get("/")
def root():
    return {"message": "TTC Backend läuft"}
