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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


settings = Settings()
print (settings)