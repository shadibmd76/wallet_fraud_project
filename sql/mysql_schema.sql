-- Mobile Wallet & Fraud Detection System
-- MySQL / MariaDB Schema (XAMPP phpMyAdmin compatible)

CREATE DATABASE IF NOT EXISTS `wallet_fraud_db` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `wallet_fraud_db`;

-- 1. Users table
CREATE TABLE IF NOT EXISTS `users` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `username`      VARCHAR(100) UNIQUE NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL,
    `role`          VARCHAR(50) NOT NULL DEFAULT 'customer',
    `full_name`     VARCHAR(150) NOT NULL,
    `phone`         VARCHAR(50) UNIQUE,
    `email`         VARCHAR(150),
    `created_at`    VARCHAR(50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Wallets table
CREATE TABLE IF NOT EXISTS `wallets` (
    `user_id` INT PRIMARY KEY,
    `balance` DECIMAL(15, 2) NOT NULL DEFAULT 0,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Devices table
CREATE TABLE IF NOT EXISTS `devices` (
    `id`          INT AUTO_INCREMENT PRIMARY KEY,
    `user_id`     INT NOT NULL,
    `device_name` VARCHAR(100) NOT NULL,
    UNIQUE KEY `uk_user_device` (`user_id`, `device_name`),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Transactions table
CREATE TABLE IF NOT EXISTS `transactions` (
    `id`          INT AUTO_INCREMENT PRIMARY KEY,
    `sender_id`   INT NULL,
    `receiver_id` INT NULL,
    `amount`      DECIMAL(15, 2) NOT NULL,
    `type`        VARCHAR(20) NOT NULL,
    `device`      VARCHAR(100) NULL,
    `note`        TEXT NULL,
    `status`      VARCHAR(30) NOT NULL,
    `risk_score`  INT DEFAULT 0,
    `risk_level`  VARCHAR(20) DEFAULT 'LOW',
    `created_at`  VARCHAR(50),
    FOREIGN KEY (`sender_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
    FOREIGN KEY (`receiver_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
    INDEX `idx_tx_sender` (`sender_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Fraud Alerts table
CREATE TABLE IF NOT EXISTS `fraud_alerts` (
    `id`             INT AUTO_INCREMENT PRIMARY KEY,
    `transaction_id` INT NOT NULL,
    `user_id`        INT NOT NULL,
    `risk_score`     INT,
    `risk_level`     VARCHAR(20),
    `reasons`        TEXT,
    `status`         VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    `created_at`     VARCHAR(50),
    FOREIGN KEY (`transaction_id`) REFERENCES `transactions`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
    INDEX `idx_alert_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Initial Admin Seed (Password: admin123)
INSERT INTO `users` (`id`, `username`, `password_hash`, `role`, `full_name`, `phone`, `email`, `created_at`) VALUES
(1, 'admin', 'pbkdf2_sha256$200000$6e0b553daaf59f871d816ed589be5fcd$9269d65407fa38ed15d91748ae4c22e04fe068c2b66b2ad5782bdf7ce053586f', 'admin', 'Admin', '01700000000', 'admin@example.com', NOW())
ON DUPLICATE KEY UPDATE `username`=`username`;

INSERT INTO `wallets` (`user_id`, `balance`) VALUES (1, 0)
ON DUPLICATE KEY UPDATE `user_id`=`user_id`;

INSERT INTO `devices` (`user_id`, `device_name`) VALUES (1, 'Admin-Device')
ON DUPLICATE KEY UPDATE `user_id`=`user_id`;
