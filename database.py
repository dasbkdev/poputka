import os
import sqlite3

os.makedirs("data", exist_ok=True)
DB_PATH = os.path.join("data", "ads.db")

def get_conn():
    # Включаем выдачу строк как tuple (по умолч.), autocommit через явные commit()
    return sqlite3.connect(DB_PATH)

def _table_has_column(c, table, column) -> bool:
    c.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in c.fetchall()]  # row = (cid, name, type, notnull, dflt_value, pk)
    return column in cols

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # --- базовые таблицы (если нет — создаём) ---
    c.execute("""CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        description TEXT,
        proof_path TEXT,           -- новое имя колонки для пути к файлу
        user_id INTEGER,           -- новое поле
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        recipient TEXT,
        check_time TEXT,
        proof_path TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('rotation_index', '0')")

    # --- миграции для старых установок ---
    # 1) если в ads нет user_id — добавим
    if not _table_has_column(c, "ads", "user_id"):
        c.execute("ALTER TABLE ads ADD COLUMN user_id INTEGER")

    # 2) раньше путь мог храниться в колонке proof — добавим proof_path и скопируем
    if not _table_has_column(c, "ads", "proof_path"):
        c.execute("ALTER TABLE ads ADD COLUMN proof_path TEXT")

    # если есть старая колонка proof — попробуем перенести данные в proof_path (один раз)
    c.execute("PRAGMA table_info(ads)")
    cols = [row[1] for row in c.fetchall()]
    if "proof" in cols:
        # перенесём только там, где proof_path пустой/NULL
        c.execute("UPDATE ads SET proof_path = COALESCE(proof_path, proof) WHERE proof_path IS NULL")

    conn.commit()
    conn.close()

def save_ad(user_id, name, phone, description, proof_path):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO ads (user_id, name, phone, description, proof_path)
                 VALUES (?, ?, ?, ?, ?)""",
              (user_id, name, phone, description, proof_path))
    conn.commit()
    conn.close()

def save_payment(user_id, amount, recipient, check_time, proof_path):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO payments (user_id, amount, recipient, check_time, proof_path)
                 VALUES (?, ?, ?, ?, ?)""",
              (user_id, amount, recipient, check_time, proof_path))
    conn.commit()
    conn.close()

def get_and_inc_rotation_index(modulo):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='rotation_index'")
    row = c.fetchone()
    idx = int(row[0]) if row else 0
    new_idx = (idx + 1) % modulo
    c.execute("UPDATE settings SET value = ? WHERE key='rotation_index'", (str(new_idx),))
    conn.commit()
    conn.close()
    return idx
