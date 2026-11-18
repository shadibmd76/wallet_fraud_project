-- devices table (a device not found here is treated as NEW)
CREATE TABLE IF NOT EXISTS devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    device_name TEXT NOT NULL,
    UNIQUE (user_id, device_name),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
