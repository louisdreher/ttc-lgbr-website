from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.core.logging import configure_logging
from app.core.settings import settings
from app.domains.articles.intern_router import router as article_admin_router
from app.domains.articles.public_router import router as article_router
from app.domains.content.events.admin_router import router as event_admin_router
from app.domains.users.router import router as user_router

configure_logging(
    log_level=settings.log_level,
    mytt_log_level=settings.mytt_log_level,
    log_to_file=settings.log_to_file,
    log_directory=settings.log_directory,
    log_max_bytes=settings.log_max_bytes,
    log_backup_count=settings.log_backup_count,
)


app = FastAPI()

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
        "PATCH",
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
app.include_router(event_admin_router)
app.include_router(auth_router)


@app.get("/")
def root():
    return {"message": "TTC Backend läuft"}
