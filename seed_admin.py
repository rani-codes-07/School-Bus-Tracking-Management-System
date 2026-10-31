from getpass import getpass
from werkzeug.security import generate_password_hash
import mysql.connector
from mysql.connector import Error

config = {
    "host": "localhost",
    "port": 3307,
    "user": "root",
    "password": input("MySQL root password (press Enter if none): "),
    "database": "school_bus_tracking",
}
name = input("Admin name [School Admin]: ").strip() or "School Admin"
email = input("Admin email [admin@school.local]: ").strip().lower() or "admin@school.local"
password = getpass("Create admin password (at least 8 characters): ")
if len(password) < 8:
    raise SystemExit("Password must be at least 8 characters.")
try:
    conn = mysql.connector.connect(**config)
    cur = conn.cursor()
    cur.execute("""INSERT INTO users (name,email,password_hash,role)
                   VALUES (%s,%s,%s,'admin')
                   ON DUPLICATE KEY UPDATE name=VALUES(name), password_hash=VALUES(password_hash), role='admin'""",
                (name, email, generate_password_hash(password)))
    conn.commit()
    print("Admin account ready. Use the email and password you entered to log in.")
except Error as exc:
    print("Could not create admin:", exc)
    print("Check that database.sql was imported and MySQL credentials are correct.")
finally:
    try:
        cur.close()
        conn.close()
    except Exception:
        pass
