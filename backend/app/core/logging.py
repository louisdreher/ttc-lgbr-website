import logging
from logging.config import dictConfig
from pathlib import Path


DEFAULT_LOG_LEVEL = "INFO"
BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]


def configure_logging(
    log_level: str = DEFAULT_LOG_LEVEL,
    mytt_log_level: str = DEFAULT_LOG_LEVEL,
    log_to_file: bool = True,
    log_directory: str | Path = "output/logs",
    log_max_bytes: int = 5 * 1024 * 1024,
    log_backup_count: int = 5,
) -> None:
    """Konfiguriert Konsolen- und optionale rotierende Datei-Logs."""

    application_level = _normalize_log_level(log_level)
    mytischtennis_level = _normalize_log_level(mytt_log_level)

    if log_max_bytes <= 0:
        raise ValueError("log_max_bytes muss größer als 0 sein.")

    if log_backup_count < 0:
        raise ValueError("log_backup_count darf nicht negativ sein.")

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": application_level,
            "stream": "ext://sys.stdout",
        },
    }
    root_handlers = ["console"]
    mytischtennis_handlers = []

    if log_to_file:
        resolved_log_directory = _resolve_log_directory(log_directory)
        resolved_log_directory.mkdir(parents=True, exist_ok=True)

        handlers.update(
            {
                "application_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "default",
                    "level": application_level,
                    "filename": str(resolved_log_directory / "application.log"),
                    "maxBytes": log_max_bytes,
                    "backupCount": log_backup_count,
                    "encoding": "utf-8",
                    "delay": True,
                },
                "mytischtennis_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "default",
                    "level": mytischtennis_level,
                    "filename": str(
                        resolved_log_directory / "mytischtennis.log"
                    ),
                    "maxBytes": log_max_bytes,
                    "backupCount": log_backup_count,
                    "encoding": "utf-8",
                    "delay": True,
                },
            },
        )
        root_handlers.append("application_file")
        mytischtennis_handlers.append("mytischtennis_file")

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s %(levelname)-8s "
                        "%(name)s: %(message)s"
                    ),
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": handlers,
            "loggers": {
                "app.integrations.mytischtennis": {
                    "handlers": mytischtennis_handlers,
                    "level": mytischtennis_level,
                    "propagate": True,
                },
                "httpx": {
                    "level": "WARNING",
                },
                "httpcore": {
                    "level": "WARNING",
                },
                "sqlalchemy.engine": {
                    "level": "WARNING",
                },
            },
            "root": {
                "handlers": root_handlers,
                "level": application_level,
            },
        }
    )


def _normalize_log_level(log_level: str) -> str:
    normalized_log_level = log_level.upper()

    if normalized_log_level not in logging.getLevelNamesMapping():
        raise ValueError(f"Unbekanntes Log-Level: {log_level!r}")

    return normalized_log_level


def _resolve_log_directory(log_directory: str | Path) -> Path:
    path = Path(log_directory)

    if path.is_absolute():
        return path

    return BACKEND_DIRECTORY / path
