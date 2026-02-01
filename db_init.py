import sqlite3

conn = sqlite3.connect("expenses.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    amount INTEGER NOT NULL,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL
)
""")

conn.commit()
conn.close()

print("Database created successfully")
