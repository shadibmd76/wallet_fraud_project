"""Wallet business logic (UI chhara) - desktop_app.py eta use kore."""
import csv

from database import IntegrityError, get_db, now
from fraud import check_fraud
from security import check_password_hash, generate_password_hash


class WalletError(Exception):
    """Validation / business error - message ta user ke dekhano hoy."""


# ---------- helpers ----------
def _transfer(conn, sender_id, receiver_id, amount):
    conn.execute("UPDATE wallets SET balance = balance - ? WHERE user_id=?", (amount, sender_id))
    conn.execute("UPDATE wallets SET balance = balance + ? WHERE user_id=?", (amount, receiver_id))


def _balance(conn, user_id):
    row = conn.execute("SELECT balance FROM wallets WHERE user_id=?", (user_id,)).fetchone()
    return row["balance"] if row else 0


def _query(sql, params=()):
    conn = get_db()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


# ---------- auth ----------
def authenticate(username, password):
    rows = _query("SELECT * FROM users WHERE username=?", (username.strip().lower(),))
    if rows and check_password_hash(rows[0]["password_hash"], password):
        return dict(rows[0])
    return None


def register(full_name, username, phone, email, password, device):
    full_name, username = full_name.strip(), username.strip().lower()
    phone, email = phone.strip(), email.strip()
    device = device.strip() or "Phone-1"
    if not (full_name and username and phone and password):
        raise WalletError("Please fill in all fields.")
    if len(password) < 6:
        raise WalletError("Password must be at least 6 characters.")
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users(username,password_hash,role,full_name,phone,email,created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (username, generate_password_hash(password), "customer", full_name, phone, email, now()))
        conn.execute("INSERT INTO wallets(user_id,balance) VALUES(?,0)", (cur.lastrowid,))
        conn.execute("INSERT INTO devices(user_id,device_name) VALUES(?,?)", (cur.lastrowid, device))
        conn.commit()
    except IntegrityError:
        raise WalletError("This username or phone number already exists.")
    finally:
        conn.close()


# ---------- wallet ----------
def get_balance(user_id):
    conn = get_db()
    try:
        return _balance(conn, user_id)
    finally:
        conn.close()


def get_devices(user_id):
    return [r["device_name"] for r in
            _query("SELECT device_name FROM devices WHERE user_id=?", (user_id,))]


def deposit(user_id, amount):
    if amount <= 0 or amount > 500000:
        raise WalletError("Enter a valid amount (maximum 500,000 Tk).")
    conn = get_db()
    try:
        conn.execute("UPDATE wallets SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        conn.execute(
            "INSERT INTO transactions(sender_id,receiver_id,amount,type,status,risk_score,risk_level,created_at)"
            " VALUES(NULL,?,?,'DEPOSIT','COMPLETED',0,'LOW',?)", (user_id, amount, now()))
        conn.commit()
    finally:
        conn.close()


def send_money(user_id, receiver_name, amount, device, note=""):
    """returns (level, score). HIGH hole transaction HELD thake."""
    receiver_name = receiver_name.strip().lower()
    device = device.strip() or "Phone-1"
    conn = get_db()
    try:
        receiver = conn.execute(
            "SELECT id FROM users WHERE username=? AND role='customer'", (receiver_name,)).fetchone()
        if amount <= 0:
            raise WalletError("Enter a valid amount.")
        if not receiver:
            raise WalletError("Receiver (username) not found.")
        if receiver["id"] == user_id:
            raise WalletError("You cannot send money to your own wallet.")
        if amount > _balance(conn, user_id):
            raise WalletError("Insufficient wallet balance.")

        score, level, reasons = check_fraud(conn, user_id, amount, device)
        status = "HELD" if level == "HIGH" else "COMPLETED"
        cur = conn.execute(
            "INSERT INTO transactions(sender_id,receiver_id,amount,type,device,note,status,"
            "risk_score,risk_level,created_at) VALUES(?,?,?,'SEND',?,?,?,?,?,?)",
            (user_id, receiver["id"], amount, device, note, status, score, level, now()))
        if level != "LOW":
            conn.execute(
                "INSERT INTO fraud_alerts(transaction_id,user_id,risk_score,risk_level,reasons,created_at)"
                " VALUES(?,?,?,?,?,?)",
                (cur.lastrowid, user_id, score, level, " | ".join(reasons), now()))
        if status == "COMPLETED":
            _transfer(conn, user_id, receiver["id"], amount)
            conn.execute("INSERT OR IGNORE INTO devices(user_id,device_name) VALUES(?,?)",
                         (user_id, device))
        conn.commit()
        return level, score
    finally:
        conn.close()


# ---------- reports ----------
def fetch_transactions(user_id=None, risk=None, status=None, limit=None):
    sql = """SELECT t.id, t.created_at, t.type, s.username AS sender, r.username AS receiver,
                    t.amount, t.device, t.status, t.risk_score, t.risk_level
             FROM transactions t
             LEFT JOIN users s ON s.id = t.sender_id
             LEFT JOIN users r ON r.id = t.receiver_id
             WHERE 1=1"""
    params = []
    if user_id:
        sql += " AND (t.sender_id=? OR (t.receiver_id=? AND t.status='COMPLETED'))"
        params += [user_id, user_id]
    if risk:
        sql += " AND t.risk_level=?"
        params.append(risk)
    if status:
        sql += " AND t.status=?"
        params.append(status)
    sql += " ORDER BY t.id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return _query(sql, params)


def export_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ID", "Date", "Type", "Sender", "Receiver", "Amount", "Device",
                    "Status", "Risk Score", "Risk Level"])
        for t in rows:
            w.writerow([t["id"], t["created_at"], t["type"], t["sender"] or "-",
                        t["receiver"] or "-", t["amount"], t["device"] or "-",
                        t["status"], t["risk_score"], t["risk_level"]])


# ---------- admin ----------
def admin_stats():
    conn = get_db()
    try:
        q = lambda sql: conn.execute(sql).fetchone()[0]
        return {
            "customers": q("SELECT COUNT(*) FROM users WHERE role='customer'"),
            "transactions": q("SELECT COUNT(*) FROM transactions"),
            "volume": q("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE status='COMPLETED'"),
            "pending": q("SELECT COUNT(*) FROM fraud_alerts WHERE status='PENDING'"),
            "high": q("SELECT COUNT(*) FROM fraud_alerts WHERE risk_level='HIGH'"),
        }
    finally:
        conn.close()


def fetch_alerts():
    return _query(
        """SELECT a.id, a.created_at, u.username, t.amount, t.device, a.risk_score,
                  a.risk_level, a.reasons, a.status, t.status AS tx_status
           FROM fraud_alerts a
           JOIN users u ON u.id = a.user_id
           JOIN transactions t ON t.id = a.transaction_id
           ORDER BY (a.status='PENDING') DESC, a.id DESC LIMIT 100""")


def fetch_customers():
    return _query(
        """SELECT u.id, u.username, u.full_name, u.phone, u.email, u.created_at, w.balance
           FROM users u LEFT JOIN wallets w ON w.user_id = u.id
           WHERE u.role='customer' ORDER BY u.id""")


def review_alert(alert_id, action):
    """action: 'approve' ba 'reject'. returns message."""
    if action not in ("approve", "reject"):
        raise WalletError("Unknown action.")
    conn = get_db()
    try:
        alert = conn.execute("SELECT * FROM fraud_alerts WHERE id=?", (alert_id,)).fetchone()
        if not alert or alert["status"] != "PENDING":
            raise WalletError("This alert has already been reviewed.")
        tx = conn.execute("SELECT * FROM transactions WHERE id=?",
                          (alert["transaction_id"],)).fetchone()

        if tx["status"] == "HELD":                      # HIGH: lenden atkano chilo
            if action == "approve":
                if _balance(conn, tx["sender_id"]) >= tx["amount"]:
                    _transfer(conn, tx["sender_id"], tx["receiver_id"], tx["amount"])
                    conn.execute("UPDATE transactions SET status='COMPLETED' WHERE id=?", (tx["id"],))
                    conn.execute("INSERT OR IGNORE INTO devices(user_id,device_name) VALUES(?,?)",
                                 (tx["sender_id"], tx["device"]))
                    conn.execute("UPDATE fraud_alerts SET status='APPROVED' WHERE id=?", (alert_id,))
                    msg = "Transaction approved."
                else:
                    conn.execute("UPDATE transactions SET status='CANCELLED' WHERE id=?", (tx["id"],))
                    conn.execute("UPDATE fraud_alerts SET status='REJECTED' WHERE id=?", (alert_id,))
                    msg = "Transaction cancelled because of insufficient balance."
            else:
                conn.execute("UPDATE transactions SET status='CANCELLED' WHERE id=?", (tx["id"],))
                conn.execute("UPDATE fraud_alerts SET status='REJECTED' WHERE id=?", (alert_id,))
                msg = "Transaction rejected."
        else:                                           # MEDIUM: lenden aagei complete
            if action == "approve":
                conn.execute("UPDATE fraud_alerts SET status='SAFE' WHERE id=?", (alert_id,))
                msg = "Transaction marked as SAFE."
            else:
                conn.execute("UPDATE fraud_alerts SET status='FRAUD' WHERE id=?", (alert_id,))
                conn.execute("UPDATE transactions SET status='FRAUD' WHERE id=?", (tx["id"],))
                msg = "Transaction marked as FRAUD."
        conn.commit()
        return msg
    finally:
        conn.close()
