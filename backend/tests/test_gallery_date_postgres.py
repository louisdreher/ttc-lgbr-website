"""Migration checks against disposable databases only."""

from datetime import date

from alembic import command
from sqlalchemy import inspect, text

from test_outbox_postgres import postgres_database  # noqa: F401 -- shared fixture


def test_gallery_date_migration_on_empty_database(postgres_database):
    engine, config = postgres_database
    command.upgrade(config, "head")
    command.check(config)
    columns = {column["name"]: column for column in inspect(engine).get_columns("gallery")}
    assert not columns["gallery_date"]["nullable"]
    assert not columns["show_date"]["nullable"]
    assert "ix_gallery_gallery_date" in {index["name"] for index in inspect(engine).get_indexes("gallery")}


def test_legacy_dates_are_backfilled_and_remain_independent(postgres_database):
    engine, config = postgres_database
    command.upgrade(config, "d4f26a41b735")
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO "user" (id, email, name, password_hash, is_active, created_at)
            VALUES (900001, 'migration@example.test', 'Test', 'test', true, now())
        """))
        connection.execute(text("""
            INSERT INTO event_category (id, name, slug, default_report_expected, is_active, sort_order)
            VALUES (900001, 'Turnier', 'turnier', false, true, 0)
        """))
        connection.execute(text("""
            INSERT INTO event (id, title, starts_at, category_id, status, visibility,
                               report_expected, is_all_day, created_at, updated_at)
            VALUES (900001, 'Event', '2007-06-15 23:30:00+00', 900001, 'PLANNED', 'PUBLIC',
                    false, false, now(), now())
        """))
        connection.execute(text("""
            INSERT INTO gallery (id, title, event_id, visibility, created_by_user_id, created_at, updated_at)
            VALUES (900001, 'Eventgalerie', 900001, 'PUBLIC', 900001, '2026-01-01 23:30:00+00', now()),
                   (900002, 'Ohne Event', NULL, 'PUBLIC', 900001, '2026-01-01 23:30:00+00', now())
        """))
    command.upgrade(config, "head")
    command.check(config)
    with engine.begin() as connection:
        rows = connection.execute(text("SELECT gallery_date, show_date FROM gallery ORDER BY id")).all()
        assert rows == [(date(2007, 6, 16), True), (date(2026, 1, 2), False)]
        connection.execute(text("UPDATE event SET starts_at = '2010-01-01 12:00:00+00' WHERE id=900001"))
        assert connection.scalar(text("SELECT gallery_date FROM gallery WHERE id=900001")) == date(2007, 6, 16)
    command.downgrade(config, "d4f26a41b735")
    assert "gallery_date" not in {c["name"] for c in inspect(engine).get_columns("gallery")}
    command.upgrade(config, "head")
    command.check(config)
