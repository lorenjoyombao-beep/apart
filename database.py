import sqlite3
from pathlib import Path

DATABASE_FILE = Path(__file__).parent / "apartment_system.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL DEFAULT 'tenant',
            phone TEXT,
            email TEXT,
            assigned_unit TEXT,
            monthly_rent REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_number TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'Vacant',
            tenant_id INTEGER,
            monthly_rent REAL DEFAULT 0,
            FOREIGN KEY (tenant_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            unit_number TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_month TEXT NOT NULL,
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Paid',
            FOREIGN KEY (tenant_id) REFERENCES users(id)
        )
    """)

    # Create default administrator
    cursor.execute("""
        INSERT OR IGNORE INTO users
        (username, password, full_name, role)
        VALUES (?, ?, ?, ?)
    """, ("admin", "12345", "System Administrator", "admin"))

    # Create 200 apartment units
    for number in range(1, 201):
        unit_number = f"Unit {number}"

        cursor.execute("""
            INSERT OR IGNORE INTO units
            (unit_number, status, monthly_rent)
            VALUES (?, ?, ?)
        """, (unit_number, "Vacant", 0))

    connection.commit()
    connection.close()


def login_user(username, password):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM users
        WHERE username = ? AND password = ?
    """, (username, password))

    user = cursor.fetchone()
    connection.close()

    return user


def register_tenant(username, password, full_name, phone, email):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO users
            (username, password, full_name, role, phone, email)
            VALUES (?, ?, ?, 'tenant', ?, ?)
        """, (username, password, full_name, phone, email))

        connection.commit()
        return True, "Registration successful."

    except sqlite3.IntegrityError:
        return False, "Username already exists."

    finally:
        connection.close()
