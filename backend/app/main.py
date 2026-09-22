from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.inbound.http.articles.admin_router import (
    router as article_admin_router,
)
from app.adapters.inbound.http.articles.public_router import (
    member_router as article_member_router,
)
from app.adapters.inbound.http.articles.public_router import (
    router as article_public_router,
)
from app.adapters.inbound.http.auth.router import router as auth_router
from app.adapters.inbound.http.media.router import router as media_router
from app.adapters.inbound.http.media.gallery_router import router as gallery_router
from app.adapters.inbound.http.competition.automation_router import (
    router as automation_router,
)
from app.adapters.inbound.http.competition.router import router as competition_router
from app.adapters.inbound.http.events.admin_router import router as event_admin_router
from app.adapters.inbound.http.events.public_router import router as event_public_router
from app.adapters.inbound.http.users.admin_router import password_router
from app.adapters.inbound.http.users.admin_router import router as user_admin_router
from app.adapters.inbound.http.users.router import router as user_router
from app.bootstrap.logging import configure_logging
from app.bootstrap.settings import settings

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


app.include_router(competition_router)
app.include_router(automation_router)
app.include_router(user_router)
app.include_router(user_admin_router)
app.include_router(password_router)
app.include_router(article_admin_router)
app.include_router(article_public_router)
app.include_router(article_member_router)
app.include_router(event_admin_router)
app.include_router(event_public_router)
app.include_router(auth_router)
app.include_router(media_router)
app.include_router(gallery_router)


@app.get("/")
def root():
    return {"message": "TTC Backend läuft"}
