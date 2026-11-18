-- transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id   INTEGER,
    receiver_id INTEGER,
    amount      REAL NOT NULL,
    type        TEXT NOT NULL,                 -- SEND / DEPOSIT
    device      TEXT,
    note        TEXT,
    status      TEXT NOT NULL,                 -- COMPLETED / HELD / CANCELLED / FRAUD
    risk_score  INTEGER DEFAULT 0,
    risk_level  TEXT DEFAULT 'LOW',
    created_at  TEXT,
    FOREIGN KEY (sender_id)   REFERENCES users(id),
    FOREIGN KEY (receiver_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_tx_sender ON transactions(sender_id, created_at);
