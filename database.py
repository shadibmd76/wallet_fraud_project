import os
from datetime import datetime
import pymysql
from pymysql.err import IntegrityError

# Database configuration (Defaults for local XAMPP / MySQL)
MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DB = os.environ.get("MYSQL_DB", "wallet_fraud_db")


class Row(dict):
    """Provides both dict-like key access ('column') and tuple-like integer index access (0)."""
    def __init__(self, cols, vals):
        super().__init__(zip(cols, vals))
        self._vals = tuple(vals)

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._vals[item]
        return super().__getitem__(item)


class MySQLCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None
        self.rowcount = 0

    def execute(self, sql, params=()):
        converted_sql = sql.replace("INSERT OR IGNORE INTO", "INSERT IGNORE INTO")
        converted_sql = converted_sql.replace("INSERT OR IGNORE", "INSERT IGNORE")
        converted_sql = converted_sql.replace("?", "%s")
        self._cursor.execute(converted_sql, params or ())
        self.lastrowid = self._cursor.lastrowid
        self.rowcount = self._cursor.rowcount
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in self._cursor.description]
        return Row(cols, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        cols = [d[0] for d in self._cursor.description]
        return [Row(cols, r) for r in rows]

    def close(self):
        self._cursor.close()


class MySQLConnectionWrapper:
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        wrapper = MySQLCursorWrapper(cur)
        wrapper.execute(sql, params)
        return wrapper

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def cursor(self):
        return MySQLCursorWrapper(self._conn.cursor())


def get_db():
    raw_conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        autocommit=False
    )
    return MySQLConnectionWrapper(raw_conn)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    """Initializes MySQL database, creates tables, and inserts initial admin account if not present."""
    # 1. Connect without db to ensure database exists
    root_conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset="utf8mb4"
    )
    with root_conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    root_conn.close()

    # 2. Connect to the database and create tables
    conn = get_db()
    try:
        tables = [
            """CREATE TABLE IF NOT EXISTS users (
                id            INT AUTO_INCREMENT PRIMARY KEY,
                username      VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role          VARCHAR(50) NOT NULL DEFAULT 'customer',
                full_name     VARCHAR(150) NOT NULL,
                phone         VARCHAR(50) UNIQUE,
                email         VARCHAR(150),
                created_at    VARCHAR(50)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

            """CREATE TABLE IF NOT EXISTS wallets (
                user_id INT PRIMARY KEY,
                balance DECIMAL(15, 2) NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

            """CREATE TABLE IF NOT EXISTS devices (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                user_id     INT NOT NULL,
                device_name VARCHAR(100) NOT NULL,
                UNIQUE KEY uk_user_device (user_id, device_name),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

            """CREATE TABLE IF NOT EXISTS transactions (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                sender_id   INT NULL,
                receiver_id INT NULL,
                amount      DECIMAL(15, 2) NOT NULL,
                type        VARCHAR(20) NOT NULL,
                device      VARCHAR(100) NULL,
                note        TEXT NULL,
                status      VARCHAR(30) NOT NULL,
                risk_score  INT DEFAULT 0,
                risk_level  VARCHAR(20) DEFAULT 'LOW',
                created_at  VARCHAR(50),
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE SET NULL,
                INDEX idx_tx_sender (sender_id, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

            """CREATE TABLE IF NOT EXISTS fraud_alerts (
                id             INT AUTO_INCREMENT PRIMARY KEY,
                transaction_id INT NOT NULL,
                user_id        INT NOT NULL,
                risk_score     INT,
                risk_level     VARCHAR(20),
                reasons        TEXT,
                status         VARCHAR(30) NOT NULL DEFAULT 'PENDING',
                created_at     VARCHAR(50),
                FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_alert_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"""
        ]

        for t in tables:
            conn.execute(t)

        # Seed admin if not present
        admin = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
        if not admin:
            # admin / admin123
            admin_hash = "pbkdf2_sha256$200000$6e0b553daaf59f871d816ed589be5fcd$9269d65407fa38ed15d91748ae4c22e04fe068c2b66b2ad5782bdf7ce053586f"
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, role, full_name, phone, email, created_at)"
                " VALUES (%s, %s, 'admin', 'Admin', '01700000000', 'admin@example.com', %s)",
                ("admin", admin_hash, now())
            )
            admin_id = cur.lastrowid
            conn.execute("INSERT INTO wallets (user_id, balance) VALUES (%s, 0)", (admin_id,))
            conn.execute("INSERT IGNORE INTO devices (user_id, device_name) VALUES (%s, 'Admin-Device')", (admin_id,))

        conn.commit()
    finally:
        conn.close()