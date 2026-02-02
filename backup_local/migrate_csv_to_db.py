import csv
import sqlite3
from datetime import datetime
import os

DB = "expenses.db"
CSV = "expenses.csv"

if not os.path.exists(CSV):
    print("No CSV found. Skipping migration.")
    exit()

conn = sqlite3.connect(DB)
cur = conn.cursor()

with open(CSV, newline="") as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) < 4:
            continue
        _, title, amount, category = row
        cur.execute(
            "INSERT INTO expenses (title, amount, category, created_at) VALUES (?, ?, ?, ?)",
            (title, int(amount), category, datetime.now().isoformat())
        )

conn.commit()
conn.close()

print("CSV migrated to SQLite successfully")
