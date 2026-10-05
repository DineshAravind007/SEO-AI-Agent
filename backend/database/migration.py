import sqlite3
import logging
import os
from backend.database.connection import SQLALCHEMY_DATABASE_URL

logger = logging.getLogger(__name__)

def run_migrations():
    """
    Safely and idempotently updates the SQLite database schema without deleting tables or data.
    Ensures 'user_id' exists on audits, monitoring_projects, competitor_analyses, and keyword_analyses.
    """
    if "sqlite" not in SQLALCHEMY_DATABASE_URL:
        return

    db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = db_path[2:]

    if not os.path.exists(db_path):
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        def column_exists(table: str, col: str) -> bool:
            cursor.execute(f"PRAGMA table_info({table});")
            return any(row[1] == col for row in cursor.fetchall())

        def table_exists(table: str) -> bool:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            return cursor.fetchone() is not None

        # Check and add user_id to user-owned resource tables
        tables_to_migrate = [
            "audits",
            "monitoring_projects",
            "competitor_analyses",
            "keyword_analyses",
        ]

        for table in tables_to_migrate:
            if table_exists(table) and not column_exists(table, "user_id"):
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id);")
                logger.info("Migrated table '%s': added 'user_id' column", table)

        # Check is_competitor on audits
        if table_exists("audits") and not column_exists("audits", "is_competitor"):
            cursor.execute("ALTER TABLE audits ADD COLUMN is_competitor BOOLEAN DEFAULT 0;")
            logger.info("Migrated table 'audits': added 'is_competitor' column")

        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("Database migration note: %s", e)
