-- users table
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'customer',   -- admin / customer
    full_name     TEXT NOT NULL,
    phone         TEXT UNIQUE,
    email         TEXT,
    created_at    TEXT
);
