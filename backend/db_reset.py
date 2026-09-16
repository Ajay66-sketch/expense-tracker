import os
import sqlite3

DB_NAME = "expenses.db"

# Delete old DB if exists
if os.path.exists(DB_NAME):
    os.remove(DB_NAME)
    print(f"Deleted old database: {DB_NAME}")

# Create new DB with correct schema
conn = sqlite3.connect(DB_NAME)
conn.execute("""
CREATE TABLE expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL
)
""")
conn.commit()
conn.close()

print(f"Created new database: {DB_NAME} ✅")
