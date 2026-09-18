from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # MyTischtennis Settings
    mytt_base_url: str = "https://www.mytischtennis.de"
    mytt_club_number: str = "45017"
    mytt_club_id: str = "???"
    mytt_organization: str = "HeTTV"
    mytt_club_slug: str = "TTC_Langen-Brombach"

    # Anwendung
    environment: str = "development"
    public_frontend_url: str = "http://localhost:4200"
    password_link_minutes: int = Field(default=60, ge=5, le=1440)
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = Field(default="", repr=False)
    smtp_sender: str = ""
    smtp_starttls: bool = True

    # Compatibility with existing .env files; scheduling now lives in the database.
    competition_sync_interval_seconds: int = Field(default=3600, ge=60)
    outbox_poll_interval_seconds: int = Field(default=10, ge=1)
    outbox_batch_size: int = Field(default=100, ge=1, le=1000)
    outbox_max_attempts: int = Field(default=5, ge=1, le=100)
    outbox_lease_seconds: int = Field(default=300, ge=10)
    outbox_retry_seconds: int = Field(default=60, ge=1)

    # Logging
    log_level: str = "INFO"
    mytt_log_level: str = "INFO"
    log_to_file: bool = True
    log_directory: str = "output/logs"
    log_max_bytes: int = 5 * 1024 * 1024
    log_backup_count: int = 5

    # Datenbank
    database_url: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15

    # Refresh Token
    refresh_token_expire_days: int = 30

    # Cookie
    refresh_cookie_name: str = "refresh_token"
    cookie_secure: bool = False
    cookie_samesite: str = "strict"
    cookie_path: str = "/api/auth"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
