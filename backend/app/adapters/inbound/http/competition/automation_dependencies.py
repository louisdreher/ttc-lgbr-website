from app.bootstrap.competition_automation import (
    build_get_sync_matches,
    build_get_sync_status,
    build_request_match_reload,
    build_request_sync,
    build_update_sync_settings,
)
from app.bootstrap.messaging import build_get_outbox_status, build_retry_outbox_message


def provide_sync_status():
    return build_get_sync_status()


def provide_sync_settings():
    return build_update_sync_settings()


def provide_sync_request():
    return build_request_sync()


def provide_match_reload():
    return build_request_match_reload()


def provide_sync_matches():
    return build_get_sync_matches()


def provide_outbox_status():
    return build_get_outbox_status()


def provide_outbox_retry():
    return build_retry_outbox_message()
