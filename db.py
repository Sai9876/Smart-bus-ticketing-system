import os
import sys
import pathlib
import mysql.connector


# Paths
EXE_DIR  = pathlib.Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
           else pathlib.Path(__file__).resolve().parent
BASE_DIR = pathlib.Path(getattr(sys, "_MEIPASS", pathlib.Path(__file__).resolve().parent))
CWD      = pathlib.Path().resolve()


# --------------------------------------------------
# --- PyInstaller shims (mysql-connector locales + auth plugins) ---
try:
    import mysql.connector.locales.eng.client_error  # errors text
    import mysql.connector.plugins.mysql_native_password
    import mysql.connector.plugins.caching_sha2_password
except Exception:
    pass
# -----------------------------------------------------------------


# Load .env from multiple spots
try:
    from dotenv import load_dotenv
    for p in (EXE_DIR / ".env", BASE_DIR / ".env", CWD / ".env"):
        try: load_dotenv(p, override=True)
        except: pass
except Exception:
    pass

def _must_env(key, default=None, allow_empty=False):
    v = os.getenv(key, default)
    if (v is None) or (v == "" and not allow_empty):
        raise RuntimeError(f"Missing/empty env: {key}")
    return v



def conn():
    pwd = _must_env("DB_PASS", None, allow_empty=False).strip()
    user = _must_env("DB_USER", "busapp", allow_empty=False)
    host = os.getenv("DB_HOST", "127.0.0.1").strip()
    port = int(os.getenv("DB_PORT", "3306"))

    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=pwd,
        database=_must_env("DB_NAME", "smart_bus", allow_empty=False),
        use_pure=True
    )



def init_schema():
    c = conn(); cur = c.cursor()

    # 1) base tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tickets(
      id INT AUTO_INCREMENT PRIMARY KEY,
      pnr VARCHAR(40) UNIQUE,
      boarding VARCHAR(80), dropping VARCHAR(80),
      time_slot VARCHAR(20),
      seats INT,
      base_fare DECIMAL(10,2), final_fare DECIMAL(10,2),
      phone VARCHAR(15),
      paid TINYINT DEFAULT 0,
      seat_labels VARCHAR(120),
      qr_path VARCHAR(255), pdf_path VARCHAR(255),
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS passengers(
      id INT AUTO_INCREMENT PRIMARY KEY,
      ticket_id INT, name VARCHAR(120), age INT,
      FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
    )""")

    # helper: does column exist?
    def col_exists(table, col):
        cur.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s
        """, (table, col))
        return cur.fetchone()[0] > 0

    # 2) add missing columns (no IF NOT EXISTS)
    if not col_exists("tickets", "pnr"):
        cur.execute("ALTER TABLE tickets ADD COLUMN pnr VARCHAR(40) NULL")
        # unique index (allows multiple NULLs)
        cur.execute("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME='tickets' AND INDEX_NAME='idx_tickets_pnr'
        """)
        if cur.fetchone()[0] == 0:
            cur.execute("CREATE UNIQUE INDEX idx_tickets_pnr ON tickets(pnr)")
    if not col_exists("tickets", "seat_labels"):
        cur.execute("ALTER TABLE tickets ADD COLUMN seat_labels VARCHAR(120) NULL")

    c.commit(); cur.close(); c.close()


