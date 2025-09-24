import os
import sqlite3

os.makedirs("data", exist_ok=True)
DB_PATH = os.path.join("data", "ads.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        description TEXT,
        proof TEXT
    )""")
    conn.commit()
    conn.close()

def save_ad(name, phone, description, proof):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO ads (name, phone, description, proof) VALUES (?, ?, ?, ?)",
              (name, phone, description, proof))
    conn.commit()
    conn.close()
