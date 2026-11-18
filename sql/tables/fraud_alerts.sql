-- fraud_alerts table
CREATE TABLE IF NOT EXISTS fraud_alerts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER NOT NULL,
    user_id        INTEGER NOT NULL,
    risk_score     INTEGER,
    risk_level     TEXT,
    reasons        TEXT,
    status         TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING / APPROVED / REJECTED / SAFE / FRAUD
    created_at     TEXT,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id),
    FOREIGN KEY (user_id)        REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_alert_status ON fraud_alerts(status);
