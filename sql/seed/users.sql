-- demo users (passwords are PBKDF2 hashes (security.py): admin123 / demo123 / rahim123)
INSERT INTO users (id,username,password_hash,role,full_name,phone,email,created_at) VALUES
  (1,'admin','pbkdf2_sha256$200000$6e0b553daaf59f871d816ed589be5fcd$9269d65407fa38ed15d91748ae4c22e04fe068c2b66b2ad5782bdf7ce053586f','admin','Admin','01700000000','admin@example.com',datetime('now','localtime')),
  (2,'demo','pbkdf2_sha256$200000$fcf2f7ff14cbef1f2171fe2a0a04fd1c$b7fe58ef1ad9f67ef9c8dcd13d6df87eaa47ece4e4f6ede131fdb56c26ea08a5','customer','Demo Customer','01711111111','demo@example.com',datetime('now','localtime')),
  (3,'rahim','pbkdf2_sha256$200000$d227dd242810d68f5a1300ad64057849$f6819930e30cb9feeb7f6c6979655cd9de4e97a3d386d1c9a185b5046db0c85e','customer','Rahim Uddin','01722222222','rahim@example.com',datetime('now','localtime'));
