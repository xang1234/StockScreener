#!/usr/bin/env python3
"""Migration: Add items_reprocessed column to theme_pipeline_runs table.

Safe to run multiple times — checks if column already exists.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/migrate_add_items_reprocessed.py
"""

import sqlite3
import sys
from pathlib import Path

# Resolve DB path (same logic as app config)
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "stockscanner.db"


def main() -> None:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(theme_pipeline_runs)")
    columns = {row[1] for row in cursor.fetchall()}

    if "items_reprocessed" in columns:
        print("Column 'items_reprocessed' already exists — nothing to do.")
        conn.close()
        return

    print("Adding 'items_reprocessed' column to theme_pipeline_runs table...")
    cursor.execute(
        "ALTER TABLE theme_pipeline_runs ADD COLUMN items_reprocessed INTEGER DEFAULT 0"
    )
    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
