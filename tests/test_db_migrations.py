from sqlalchemy import create_engine, inspect, text

from bangstats.database import db


def test_screenshot_filename_column_migration_is_idempotent():
    temp_engine = create_engine("sqlite://")
    with temp_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE screenshot ("
                "id INTEGER PRIMARY KEY, "
                "user_id INTEGER NOT NULL"
                ")"
            )
        )

    original_engine = db.engine
    db.engine = temp_engine
    try:
        db._run_schema_migrations()
        db._run_schema_migrations()

        with temp_engine.begin() as conn:
            columns = {column["name"] for column in inspect(conn).get_columns("screenshot")}

        assert "filename" in columns
    finally:
        db.engine = original_engine
