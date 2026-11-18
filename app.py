import csv
import io
from functools import wraps

from flask import (Flask, Response, flash, redirect, render_template,
                   request, session, url_for)
from security import check_password_hash, generate_password_hash

from database import IntegrityError, get_db, init_db, now
from fraud import check_fraud

app = Flask(__name__)
app.secret_key = "change-this-secret-key"


# ---------- Helper ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("This page is for Admin only.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper


def transfer(conn, sender_id, receiver_id, amount):
    conn.execute("UPDATE wallets SET balance = balance - ? WHERE user_id=?", (amount, sender_id))
    conn.execute("UPDATE wallets SET balance = balance + ? WHERE user_id=?", (amount, receiver_id))


def get_balance(conn, user_id):
    row = conn.execute("SELECT balance FROM wallets WHERE user_id=?", (user_id,)).fetchone()
    return row["balance"] if row else 0


def fetch_transactions(conn, user_id=None, risk=None, status=None, limit=None):
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
    return conn.execute(sql, params).fetchall()


# ---------- Login / Registration ----------
@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        full_name = f.get("full_name", "").strip()
        username = f.get("username", "").strip().lower()
        phone = f.get("phone", "").strip()
        email = f.get("email", "").strip()
        password = f.get("password", "")
        device = f.get("device", "").strip() or "Phone-1"

        if not (full_name and username and phone and password):
            flash("Please fill in all fields.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        else:
            conn = get_db()
            try:
                cur = conn.execute(
                    "INSERT INTO users(username,password_hash,role,full_name,phone,email,created_at)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (username, generate_password_hash(password), "customer",
                     full_name, phone, email, now()),
                )
                conn.execute("INSERT INTO wallets(user_id,balance) VALUES(?,0)", (cur.lastrowid,))
                conn.execute("INSERT INTO devices(user_id,device_name) VALUES(?,?)",
                             (cur.lastrowid, device))
                conn.commit()
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for("login"))
            except IntegrityError:
                flash("This username or phone number already exists.", "error")
            finally:
                conn.close()
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], username=user["username"],
                           role=user["role"], full_name=user["full_name"])
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Customer: Wallet ----------
@app.route("/dashboard")
@login_required
def dashboard():
    if session["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    conn = get_db()
    uid = session["user_id"]
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    balance = get_balance(conn, uid)
    txs = fetch_transactions(conn, user_id=uid, limit=10)
    conn.close()
    return render_template("dashboard.html", user=user, balance=balance, txs=txs)


@app.route("/deposit", methods=["POST"])
@login_required
def deposit():
    try:
        amount = float(request.form.get("amount", 0))
    except ValueError:
        amount = 0
    if amount <= 0 or amount > 500000:
        flash("Enter a valid amount (maximum 500,000 Tk).", "error")
        return redirect(url_for("dashboard"))
    conn = get_db()
    uid = session["user_id"]
    conn.execute("UPDATE wallets SET balance = balance + ? WHERE user_id=?", (amount, uid))
    conn.execute(
        "INSERT INTO transactions(sender_id,receiver_id,amount,type,status,risk_score,risk_level,created_at)"
        " VALUES(NULL,?,?,'DEPOSIT','COMPLETED',0,'LOW',?)", (uid, amount, now()))
    conn.commit()
    conn.close()
    flash(f"{amount:,.2f} Tk added to your wallet.", "success")
    return redirect(url_for("dashboard"))


@app.route("/send", methods=["GET", "POST"])
@login_required
def send():
    if session["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    conn = get_db()
    uid = session["user_id"]
    devices = [d["device_name"] for d in
               conn.execute("SELECT device_name FROM devices WHERE user_id=?", (uid,))]
    balance = get_balance(conn, uid)

    if request.method == "POST":
        receiver_name = request.form.get("receiver", "").strip().lower()
        device = request.form.get("device", "").strip() or "Phone-1"
        note = request.form.get("note", "").strip()
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            amount = 0

        receiver = conn.execute(
            "SELECT id FROM users WHERE username=? AND role='customer'", (receiver_name,)).fetchone()

        if amount <= 0:
            flash("Enter a valid amount.", "error")
        elif not receiver:
            flash("Receiver (username) not found.", "error")
        elif receiver["id"] == uid:
            flash("You cannot send money to your own wallet.", "error")
        elif amount > balance:
            flash("Insufficient wallet balance.", "error")
        else:
            score, level, reasons = check_fraud(conn, uid, amount, device)
            status = "HELD" if level == "HIGH" else "COMPLETED"
            cur = conn.execute(
                "INSERT INTO transactions(sender_id,receiver_id,amount,type,device,note,status,"
                "risk_score,risk_level,created_at) VALUES(?,?,?,'SEND',?,?,?,?,?,?)",
                (uid, receiver["id"], amount, device, note, status, score, level, now()))
            tx_id = cur.lastrowid

            if level != "LOW":
                conn.execute(
                    "INSERT INTO fraud_alerts(transaction_id,user_id,risk_score,risk_level,reasons,created_at)"
                    " VALUES(?,?,?,?,?,?)", (tx_id, uid, score, level, " | ".join(reasons), now()))

            if status == "COMPLETED":
                transfer(conn, uid, receiver["id"], amount)
                conn.execute("INSERT OR IGNORE INTO devices(user_id,device_name) VALUES(?,?)",
                             (uid, device))
            conn.commit()

            if level == "HIGH":
                flash(f"High risk (Score {score}). The transaction is held for Admin review.", "error")
            elif level == "MEDIUM":
                flash(f"Transaction completed, but a fraud alert was created (Score {score}).", "warning")
            else:
                flash("Transaction successful.", "success")
            conn.close()
            return redirect(url_for("dashboard"))
    conn.close()
    return render_template("send.html", devices=devices, balance=balance)


# ---------- Report / CSV ----------
@app.route("/transactions")
@login_required
def transactions():
    risk = request.args.get("risk") or None
    status = request.args.get("status") or None
    conn = get_db()
    uid = None if session["role"] == "admin" else session["user_id"]
    txs = fetch_transactions(conn, user_id=uid, risk=risk, status=status)
    conn.close()
    return render_template("transactions.html", txs=txs, risk=risk, status=status)


@app.route("/export/transactions.csv")
@login_required
def export_csv():
    risk = request.args.get("risk") or None
    status = request.args.get("status") or None
    conn = get_db()
    uid = None if session["role"] == "admin" else session["user_id"]
    txs = fetch_transactions(conn, user_id=uid, risk=risk, status=status)
    conn.close()

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["ID", "Date", "Type", "Sender", "Receiver", "Amount", "Device",
                "Status", "Risk Score", "Risk Level"])
    for t in txs:
        w.writerow([t["id"], t["created_at"], t["type"], t["sender"] or "-", t["receiver"] or "-",
                    t["amount"], t["device"] or "-", t["status"], t["risk_score"], t["risk_level"]])
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=transactions.csv"})


# ---------- Admin ----------
@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()
    stats = {
        "users": conn.execute("SELECT COUNT(*) FROM users WHERE role='customer'").fetchone()[0],
        "txs": conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
        "volume": conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE status='COMPLETED'").fetchone()[0],
        "pending": conn.execute(
            "SELECT COUNT(*) FROM fraud_alerts WHERE status='PENDING'").fetchone()[0],
        "high": conn.execute(
            "SELECT COUNT(*) FROM fraud_alerts WHERE risk_level='HIGH'").fetchone()[0],
    }
    alerts = conn.execute(
        """SELECT a.*, u.username, t.amount, t.device, t.status AS tx_status
           FROM fraud_alerts a
           JOIN users u ON u.id = a.user_id
           JOIN transactions t ON t.id = a.transaction_id
           ORDER BY (a.status='PENDING') DESC, a.id DESC LIMIT 50""").fetchall()
    conn.close()
    return render_template("admin.html", stats=stats, alerts=alerts)


@app.route("/admin/customers")
@admin_required
def customers():
    conn = get_db()
    rows = conn.execute(
        """SELECT u.*, w.balance FROM users u
           LEFT JOIN wallets w ON w.user_id = u.id
           WHERE u.role='customer' ORDER BY u.id""").fetchall()
    conn.close()
    return render_template("customers.html", rows=rows)


@app.route("/admin/alert/<int:alert_id>/<action>", methods=["POST"])
@admin_required
def alert_action(alert_id, action):
    if action not in ("approve", "reject"):
        return redirect(url_for("admin_dashboard"))
    conn = get_db()
    alert = conn.execute("SELECT * FROM fraud_alerts WHERE id=?", (alert_id,)).fetchone()
    if not alert or alert["status"] != "PENDING":
        conn.close()
        flash("This alert has already been reviewed.", "error")
        return redirect(url_for("admin_dashboard"))
    tx = conn.execute("SELECT * FROM transactions WHERE id=?", (alert["transaction_id"],)).fetchone()

    if tx["status"] == "HELD":                       # HIGH risk: transaction was held
        if action == "approve":
            if get_balance(conn, tx["sender_id"]) >= tx["amount"]:
                transfer(conn, tx["sender_id"], tx["receiver_id"], tx["amount"])
                conn.execute("UPDATE transactions SET status='COMPLETED' WHERE id=?", (tx["id"],))
                conn.execute("INSERT OR IGNORE INTO devices(user_id,device_name) VALUES(?,?)",
                             (tx["sender_id"], tx["device"]))
                conn.execute("UPDATE fraud_alerts SET status='APPROVED' WHERE id=?", (alert_id,))
                flash("Transaction approved.", "success")
            else:
                conn.execute("UPDATE transactions SET status='CANCELLED' WHERE id=?", (tx["id"],))
                conn.execute("UPDATE fraud_alerts SET status='REJECTED' WHERE id=?", (alert_id,))
                flash("Transaction cancelled because of insufficient balance.", "error")
        else:
            conn.execute("UPDATE transactions SET status='CANCELLED' WHERE id=?", (tx["id"],))
            conn.execute("UPDATE fraud_alerts SET status='REJECTED' WHERE id=?", (alert_id,))
            flash("Transaction rejected.", "success")
    else:                                            # MEDIUM risk: transaction already completed
        if action == "approve":
            conn.execute("UPDATE fraud_alerts SET status='SAFE' WHERE id=?", (alert_id,))
            flash("Transaction marked as SAFE.", "success")
        else:
            conn.execute("UPDATE fraud_alerts SET status='FRAUD' WHERE id=?", (alert_id,))
            conn.execute("UPDATE transactions SET status='FRAUD' WHERE id=?", (tx["id"],))
            flash("Transaction marked as FRAUD.", "success")
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
