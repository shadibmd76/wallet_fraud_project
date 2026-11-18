"""Fraud Detection + Risk Score"""
from datetime import datetime, timedelta

# Rule limits (easy to change)
AMOUNT_LIMIT = 50000        # amount above 50,000 Tk
TX_LIMIT = 4                # 4 transactions in 10 minutes
TX_WINDOW_MINUTES = 10

# Risk Score
SCORE_HIGH_AMOUNT = 40
SCORE_FAST_TX = 35
SCORE_NEW_DEVICE = 30

MEDIUM_FROM = 30
HIGH_FROM = 60


def check_fraud(conn, user_id, amount, device):
    """returns (score, level, reasons)"""
    score, reasons = 0, []

    # Rule 1: large amount
    if amount > AMOUNT_LIMIT:
        score += SCORE_HIGH_AMOUNT
        reasons.append(f"Amount above 50,000 Tk ({amount:,.0f} Tk)")

    # Rule 2: 4 or more transactions in 10 minutes (including this one)
    since = (datetime.now() - timedelta(minutes=TX_WINDOW_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    count = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE sender_id=? AND type='SEND' AND created_at>=?",
        (user_id, since),
    ).fetchone()[0]
    if count + 1 >= TX_LIMIT:
        score += SCORE_FAST_TX
        reasons.append(f"{count + 1} transactions in {TX_WINDOW_MINUTES} minutes")

    # Rule 3: new device
    known = conn.execute(
        "SELECT 1 FROM devices WHERE user_id=? AND device_name=?", (user_id, device)
    ).fetchone()
    if not known:
        score += SCORE_NEW_DEVICE
        reasons.append(f"New device ({device})")

    score = min(score, 100)
    level = "HIGH" if score >= HIGH_FROM else "MEDIUM" if score >= MEDIUM_FROM else "LOW"
    return score, level, reasons
