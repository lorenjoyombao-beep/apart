import os
import shutil
from tkinter import filedialog
from PIL import Image, ImageTk
import sqlite3
from pathlib import Path
from datetime import datetime, date
from tkcalendar import DateEntry
import tkinter as tk
from tkinter import ttk, messagebox

import customtkinter as ctk

# ==========================================================
# APPLICATION THEME
# ==========================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "background": "#101B33",
    "surface": "#111C2D",
    "surface_light": "#17263A",
    "sidebar": "#0F1A2B",
    "primary": "#3B82F6",
    "primary_hover": "#2563EB",
    "success": "#16A34A",
    "success_hover": "#15803D",
    "warning": "#D97706",
    "warning_hover": "#B45309",
    "danger": "#DC2626",
    "danger_hover": "#B91C1C",
    "text": "#F8FAFC",
    "muted": "#94A3B8",
    "border": "#26364D",
    "occupied": "#713F12",
    "vacant": "#16283E"
}


# ==========================================================
# DATABASE
# ==========================================================

DATABASE_FILE = Path(__file__).parent / "apartment_system.db"


class Database:

    def __init__(self):
        self.connection = sqlite3.connect(DATABASE_FILE)
        self.connection.row_factory = sqlite3.Row
        self.create_tables()
        self.create_default_data()

    def create_tables(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'tenant',
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                assigned_unit TEXT DEFAULT '',
                monthly_rent REAL DEFAULT 0,
                profile_picture TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        try:
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN profile_picture TEXT DEFAULT ''
            """)
        except sqlite3.OperationalError:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_number TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'Vacant',
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
                payment_date TEXT NOT NULL,
                reference TEXT DEFAULT '',
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY (tenant_id) REFERENCES users(id)
            )
        """)

        try:
            cursor.execute("""
                ALTER TABLE payments
                ADD COLUMN reference TEXT DEFAULT ''
            """)
        except sqlite3.OperationalError:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS concerns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                unit_number TEXT DEFAULT '',
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                admin_reply TEXT DEFAULT '',
                status TEXT DEFAULT 'Open',
                created_at TEXT NOT NULL,
                resolved_at TEXT DEFAULT '',
                FOREIGN KEY (tenant_id) REFERENCES users(id)
            )
        """)

        try:
            cursor.execute("""
                ALTER TABLE concerns
                ADD COLUMN tenant_notified INTEGER DEFAULT 0
            """)
        except sqlite3.OperationalError:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contact_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                old_phone TEXT DEFAULT '',
                new_phone TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                status TEXT DEFAULT 'New',
                FOREIGN KEY (tenant_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rent_due_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                unit_number TEXT DEFAULT '',
                amount REAL DEFAULT 0,
                due_date TEXT NOT NULL,
                payment_month TEXT NOT NULL,
                status TEXT DEFAULT 'Open',
                notification_sent INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES users(id)
            )
        """)

        self.connection.commit()

    def mark_due_notification_sent(self, due_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            UPDATE rent_due_dates
            SET notification_sent = 1
            WHERE id = ?
        """, (due_id,))

        self.connection.commit()

    def get_due_notifications(self, tenant_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT *
            FROM rent_due_dates
            WHERE tenant_id = ?
            AND status = 'Open'
            AND notification_sent = 0
        """, (tenant_id,))

        return cursor.fetchall()

    def get_tenant_due_dates(self, tenant_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT *
            FROM rent_due_dates
            WHERE tenant_id = ?
            ORDER BY due_date ASC
        """, (tenant_id,))

        return cursor.fetchall()

    def get_due_dates(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                rent_due_dates.id,
                users.full_name AS tenant_name,
                rent_due_dates.unit_number,
                rent_due_dates.amount,
                rent_due_dates.due_date,
                rent_due_dates.payment_month,
                rent_due_dates.status,
                rent_due_dates.notification_sent
            FROM rent_due_dates
            INNER JOIN users
                ON rent_due_dates.tenant_id = users.id
            ORDER BY rent_due_dates.due_date ASC
        """)

        return cursor.fetchall()

    def create_due_date(
        self,
        tenant_id,
        amount,
        due_date,
        payment_month
    ):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT assigned_unit
            FROM users
            WHERE id = ? AND role = 'tenant'
        """, (tenant_id,))

        tenant = cursor.fetchone()

        if tenant is None:
            return False, "Tenant not found."

        try:
            datetime.strptime(
                due_date,
                "%Y-%m-%d"
            )
        except ValueError:
            return False, "Use the date format YYYY-MM-DD."

        cursor.execute("""
            INSERT INTO rent_due_dates
            (
                tenant_id,
                unit_number,
                amount,
                due_date,
                payment_month,
                status,
                notification_sent,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 'Open', 0, ?)
        """, (
            tenant_id,
            tenant["assigned_unit"] or "Not assigned",
            amount,
            due_date,
            payment_month,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        self.connection.commit()

        return True, "Rent due date created successfully."

    def create_default_data(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO users
            (username, password, full_name, role)
            VALUES (?, ?, ?, ?)
        """, (
            "admin",
            "12345",
            "System Administrator",
            "admin"
        ))

        cursor.execute("SELECT COUNT(*) AS total FROM units")
        total_units = cursor.fetchone()["total"]

        if total_units == 0:
            for number in range(1, 201):
                cursor.execute("""
                    INSERT INTO units
                    (unit_number, status, monthly_rent)
                    VALUES (?, ?, ?)
                """, (
                    f"Unit {number}",
                    "Vacant",
                    0
                ))

        self.connection.commit()

    def approve_payment(self, payment_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT status
            FROM payments
            WHERE id = ?
        """, (payment_id,))

        payment = cursor.fetchone()

        if payment is None:
            return False, "Payment not found."

        if payment["status"].strip().lower() == "paid":
            return False, "This payment is already Paid."

        if payment["status"].strip().lower() == "rejected":
            return False, "Rejected payments cannot be approved."

        cursor.execute("""
            UPDATE payments
            SET status = 'Paid'
            WHERE id = ?
        """, (payment_id,))

        self.connection.commit()

        return True, "Payment approved and marked as Paid."

    def reject_payment(self, payment_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT status
            FROM payments
            WHERE id = ?
        """, (payment_id,))

        payment = cursor.fetchone()

        if payment is None:
            return False, "Payment not found."

        current_status = payment["status"].strip().lower()

        if current_status == "rejected":
            return False, "This payment is already rejected."

        if current_status == "paid":
            return False, "A Paid payment cannot be rejected."

        cursor.execute("""
            UPDATE payments
            SET status = 'Rejected'
            WHERE id = ?
        """, (payment_id,))

        self.connection.commit()

        return True, "Payment rejected successfully."

    # -------------------------
    # USERS
    # -------------------------

    def login(self, username, password):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE username = ? AND password = ?
        """, (username, password))

        return cursor.fetchone()

    def register_tenant(self, full_name, username, password, phone, email):
        try:
            cursor = self.connection.cursor()

            cursor.execute("""
                INSERT INTO users
                (full_name, username, password, role, phone, email)
                VALUES (?, ?, ?, 'tenant', ?, ?)
            """, (
                full_name,
                username,
                password,
                phone,
                email
            ))

            self.connection.commit()
            return True, "Tenant account created successfully."

        except sqlite3.IntegrityError:
            return False, "Username already exists."

    def get_tenants(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE role = 'tenant'
            ORDER BY full_name
        """)

        return cursor.fetchall()

    def get_tenant(self, tenant_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE id = ?
        """, (tenant_id,))

        return cursor.fetchone()

    # -------------------------
    # UNITS
    # -------------------------

    def get_units(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                units.id,
                units.unit_number,
                units.status,
                units.monthly_rent,
                users.full_name AS tenant_name
            FROM units
            LEFT JOIN users
                ON units.tenant_id = users.id
            ORDER BY units.id
        """)

        return cursor.fetchall()

    def get_vacant_units(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT *
            FROM units
            WHERE status = 'Vacant'
            ORDER BY id
        """)

        return cursor.fetchall()

    def add_unit(self, unit_number, monthly_rent):
        try:
            cursor = self.connection.cursor()

            cursor.execute("""
                INSERT INTO units
                (unit_number, status, monthly_rent)
                VALUES (?, 'Vacant', ?)
            """, (
                unit_number,
                monthly_rent
            ))

            self.connection.commit()
            return True, "Unit added successfully."

        except sqlite3.IntegrityError:
            return False, "That unit number already exists."

    def delete_unit(self, unit_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT status
            FROM units
            WHERE id = ?
        """, (unit_id,))

        unit = cursor.fetchone()

        if unit is None:
            return False, "Unit not found."

        if unit["status"] == "Occupied":
            return False, "Occupied units cannot be deleted."

        cursor.execute("""
            DELETE FROM units
            WHERE id = ?
        """, (unit_id,))

        self.connection.commit()
        return True, "Unit deleted successfully."

    def delete_unit_by_number(self, unit_number):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT status
            FROM units
            WHERE unit_number = ?
        """, (unit_number,))

        unit = cursor.fetchone()

        if unit is None:
            return False, "Unit not found."

        if unit["status"] == "Occupied":
            return False, "Occupied units cannot be deleted."

        cursor.execute("""
            DELETE FROM units
            WHERE unit_number = ?
        """, (unit_number,))

        self.connection.commit()

        return True, "Unit deleted successfully."

    # -------------------------
    # ASSIGNMENT
    # -------------------------

    def assign_tenant(self, tenant_id, unit_id, monthly_rent):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT *
            FROM users
            WHERE id = ? AND role = 'tenant'
        """, (tenant_id,))

        tenant = cursor.fetchone()

        cursor.execute("""
            SELECT *
            FROM units
            WHERE id = ? AND status = 'Vacant'
        """, (unit_id,))

        unit = cursor.fetchone()

        if tenant is None:
            return False, "Tenant not found."

        if unit is None:
            return False, "Unit is not available."

        cursor.execute("""
            UPDATE units
            SET status = 'Occupied',
                tenant_id = ?,
                monthly_rent = ?
            WHERE id = ?
        """, (
            tenant_id,
            monthly_rent,
            unit_id
        ))

        cursor.execute("""
            UPDATE users
            SET assigned_unit = ?,
                monthly_rent = ?
            WHERE id = ?
        """, (
            unit["unit_number"],
            monthly_rent,
            tenant_id
        ))

        self.connection.commit()
        return True, "Tenant assigned successfully."

    def unassign_tenant(self, tenant_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT assigned_unit
            FROM users
            WHERE id = ?
        """, (tenant_id,))

        tenant = cursor.fetchone()

        if tenant is None:
            return False, "Tenant not found."

        if not tenant["assigned_unit"]:
            return False, "This tenant has no assigned unit."

        cursor.execute("""
            UPDATE units
            SET status = 'Vacant',
                tenant_id = NULL,
                monthly_rent = 0
            WHERE unit_number = ?
        """, (tenant["assigned_unit"],))

        cursor.execute("""
            UPDATE users
            SET assigned_unit = '',
                monthly_rent = 0
            WHERE id = ?
        """, (tenant_id,))

        self.connection.commit()
        return True, "Tenant assignment removed."

        # -------------------------
    # PAYMENTS
    # -------------------------

    def submit_payment(
        self,
        tenant_id,
        amount,
        payment_month,
        reference
    ):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT assigned_unit
            FROM users
            WHERE id = ?
        """, (tenant_id,))

        tenant = cursor.fetchone()

        if tenant is None:
            return False, "Tenant not found."

        if not tenant["assigned_unit"]:
            return False, "You do not have an assigned unit yet."

        cursor.execute("""
            INSERT INTO payments
            (
                tenant_id,
                unit_number,
                amount,
                payment_month,
                payment_date,
                reference,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'Pending')
        """, (
            tenant_id,
            tenant["assigned_unit"],
            amount,
            payment_month,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            reference
        ))

        self.connection.commit()

        return True, "Payment submitted. Waiting for verification."

    def get_payments(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                payments.id,
                users.full_name AS tenant_name,
                payments.unit_number,
                payments.amount,
                payments.payment_month,
                payments.payment_date,
                payments.reference,
                payments.status
            FROM payments
            INNER JOIN users
                ON payments.tenant_id = users.id
            WHERE TRIM(LOWER(payments.status)) != 'rejected'
            ORDER BY payments.id DESC
        """)

        return cursor.fetchall()

    def get_tenant_payments(self, tenant_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT *
            FROM payments
            WHERE tenant_id = ?
            ORDER BY id DESC
        """, (tenant_id,))

        return cursor.fetchall()

    def submit_concern(self, tenant_id, subject, message):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT assigned_unit
            FROM users
            WHERE id = ?
        """, (tenant_id,))

        tenant = cursor.fetchone()

        if tenant is None:
            return False, "Tenant not found."

        unit_number = tenant["assigned_unit"] or "Not assigned"

        cursor.execute("""
            INSERT INTO concerns
            (
                tenant_id,
                unit_number,
                subject,
                message,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, 'Open', ?)
        """, (
            tenant_id,
            unit_number,
            subject,
            message,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        self.connection.commit()

        return True, "Your concern has been submitted."

    def get_concerns(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                concerns.id,
                users.full_name AS tenant_name,
                concerns.unit_number,
                concerns.subject,
                concerns.message,
                concerns.admin_reply,
                concerns.status,
                concerns.created_at,
                concerns.resolved_at
            FROM concerns
            INNER JOIN users
                ON concerns.tenant_id = users.id
            ORDER BY concerns.id DESC
        """)

        return cursor.fetchall()

    def get_tenant_concerns(self, tenant_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT *
            FROM concerns
            WHERE tenant_id = ?
            ORDER BY id DESC
        """, (tenant_id,))

        return cursor.fetchall()

    def resolve_concern(self, concern_id, admin_reply):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT status
            FROM concerns
            WHERE id = ?
        """, (concern_id,))

        concern = cursor.fetchone()

        if concern is None:
            return False, "Concern not found."

        if concern["status"] == "Resolved":
            return False, "This concern is already resolved."

        cursor.execute("""
            UPDATE concerns
            SET status = 'Resolved',
                admin_reply = ?,
                resolved_at = ?,
                tenant_notified = 0
            WHERE id = ?
        """, (
            admin_reply,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            concern_id
        ))

        self.connection.commit()

        return True, "Concern marked as resolved."

    # -------------------------
    # DASHBOARD STATISTICS
    # -------------------------

    def get_statistics(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM units
        """)
        total_units = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM units
            WHERE status = 'Occupied'
        """)
        occupied_units = cursor.fetchone()["total"]

        vacant_units = total_units - occupied_units

        # Only Paid payments count as collected money
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM payments
            WHERE TRIM(LOWER(status)) = 'paid'
        """)
        collected = cursor.fetchone()["total"]

        # Total rent currently expected from assigned tenants
        cursor.execute("""
            SELECT COALESCE(SUM(monthly_rent), 0) AS total
            FROM users
            WHERE role = 'tenant'
            AND assigned_unit IS NOT NULL
            AND TRIM(assigned_unit) != ''
        """)
        expected_rent = cursor.fetchone()["total"]

        # Pending and Rejected payments are not deducted from unpaid balance
        unpaid_balance = max(
            expected_rent - collected,
            0
        )

        return {
            "total_units": total_units,
            "occupied_units": occupied_units,
            "vacant_units": vacant_units,
            "collected": collected,
            "unpaid": unpaid_balance
        }

    def get_unnotified_resolved_concerns(self, tenant_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT *
            FROM concerns
            WHERE tenant_id = ?
            AND status = 'Resolved'
            AND tenant_notified = 0
            ORDER BY id DESC
        """, (tenant_id,))

        return cursor.fetchall()

    def mark_concerns_as_notified(self, tenant_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            UPDATE concerns
            SET tenant_notified = 1
            WHERE tenant_id = ?
            AND status = 'Resolved'
            AND tenant_notified = 0
        """, (tenant_id,))

        self.connection.commit()

    def update_tenant_phone(self, tenant_id, new_phone):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT phone
            FROM users
            WHERE id = ? AND role = 'tenant'
        """, (tenant_id,))

        tenant = cursor.fetchone()

        if tenant is None:
            return False, "Tenant not found."

        old_phone = tenant["phone"] or ""

        if old_phone.strip() == new_phone.strip():
            return False, "The new contact number is the same as the current number."

        cursor.execute("""
            UPDATE users
            SET phone = ?
            WHERE id = ?
        """, (
            new_phone,
            tenant_id
        ))

        cursor.execute("""
            INSERT INTO contact_updates
            (
                tenant_id,
                old_phone,
                new_phone,
                changed_at,
                status
            )
            VALUES (?, ?, ?, ?, 'New')
        """, (
            tenant_id,
            old_phone,
            new_phone,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        self.connection.commit()

        return True, "Contact number updated successfully."

    def get_contact_updates(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                contact_updates.id,
                users.full_name AS tenant_name,
                users.assigned_unit,
                contact_updates.old_phone,
                contact_updates.new_phone,
                contact_updates.changed_at,
                contact_updates.status
            FROM contact_updates
            INNER JOIN users
                ON contact_updates.tenant_id = users.id
            ORDER BY contact_updates.id DESC
        """)

        return cursor.fetchall()

    def mark_contact_update_read(self, update_id):
        cursor = self.connection.cursor()

        cursor.execute("""
            UPDATE contact_updates
            SET status = 'Read'
            WHERE id = ?
        """, (update_id,))

        self.connection.commit()

        return True, "Contact update marked as read."


# ==========================================================
# MAIN APPLICATION
# ==========================================================

class ApartmentManagementApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.db = Database()
        self.current_user = None
        self.checked_units = set()
        self.current_view = None

        self.title("Apartment Management System")
        self.geometry("1280x780")
        self.minsize(1150, 700)

        self.configure(
            fg_color=COLORS["background"]
        )

        self.setup_treeview_style()
        self.show_role_selection()

    def clear_tenant_search(self):
        self.tenant_search_entry.delete(
            0,
            "end"
        )

        self.refresh_tenants()

    def apply_unit_filter(self, selected_filter):
        self.current_unit_page = 0
        self.refresh_units()

    def next_unit_page(self):
        units = self.db.get_units()

        total_units = len(units)

        total_pages = (
            total_units + self.units_per_page - 1
        ) // self.units_per_page

        if self.current_unit_page < total_pages - 1:
            self.current_unit_page += 1
            self.refresh_units()

    def previous_unit_page(self):
        if self.current_unit_page > 0:
            self.current_unit_page -= 1
            self.refresh_units()

    def create_unit_card(
        self,
        parent,
        unit,
        row,
        column
    ):
        unit_number = unit["unit_number"]
        status = unit["status"]
        tenant_name = unit["tenant_name"]

        if status == "Occupied":
            card_color = "#713F12"
            border_color = "#F59E0B"
            house_icon = "🔐🏠"
            status_text = "Occupied"
            status_color = "#FDE68A"
            display_tenant = tenant_name or "Assigned tenant"
        else:
            card_color = "#16283E"
            border_color = "#2563EB"
            house_icon = "🏠"
            status_text = "Vacant"
            status_color = "#93C5FD"
            display_tenant = "Available"

        card = ctk.CTkFrame(
            parent,
            width=190,
            height=225,
            corner_radius=18,
            fg_color=card_color,
            border_width=2,
            border_color=border_color
        )

        card.grid(
            row=row,
            column=column,
            padx=10,
            pady=10,
            sticky="nsew"
        )

        card.grid_propagate(False)

        # Tenant name above the house icon
        tenant_label = ctk.CTkLabel(
            card,
            text=display_tenant,
            text_color="white",
            font=ctk.CTkFont(
                size=13,
                weight="bold"
            ),
            wraplength=160
        )

        tenant_label.pack(
            pady=(16, 3)
        )

        # House icon
        icon_label = ctk.CTkLabel(
            card,
            text=house_icon,
            font=ctk.CTkFont(size=58)
        )

        icon_label.pack(
            pady=2
        )

        # Unit number
        ctk.CTkLabel(
            card,
            text=unit_number,
            text_color="white",
            font=ctk.CTkFont(
                size=16,
                weight="bold"
            )
        ).pack(
            pady=(0, 3)
        )

        # Status
        ctk.CTkLabel(
            card,
            text=status_text,
            text_color=status_color,
            font=ctk.CTkFont(size=12)
        ).pack(
            pady=2
        )

        # Checkbox for deletion
        checkbox_variable = tk.BooleanVar(
            value=unit_number in self.checked_units
        )

        self.unit_check_vars[unit_number] = checkbox_variable

        def checkbox_changed(
            selected_unit=unit_number,
            variable=checkbox_variable
        ):
            if variable.get():
                self.checked_units.add(selected_unit)
            else:
                self.checked_units.discard(selected_unit)

        ctk.CTkCheckBox(
            card,
            text="Select",
            variable=checkbox_variable,
            command=checkbox_changed,
            text_color="#D6E4F0",
            checkbox_width=20,
            checkbox_height=20
        ).pack(
            pady=(4, 8)
        )

    def toggle_tenant_password(self):
        if self.tenant_show_password_var.get():
            self.tenant_password_entry.configure(
                show=""
            )
        else:
            self.tenant_password_entry.configure(
                show="*"
            )

    def tenant_login(self):
        username = self.tenant_username_entry.get().strip()
        password = self.tenant_password_entry.get().strip()

        if not username or not password:
            messagebox.showwarning(
                "Missing Information",
                "Enter your tenant username and password."
            )
            return

        user = self.db.login(
            username,
            password
        )

        if user is None:
            messagebox.showerror(
                "Login Failed",
                "Invalid username or password."
            )
            return

        if user["role"] != "tenant":
            messagebox.showerror(
                "Invalid Account Type",
                "This login page is only for tenants."
            )
            return

        self.current_user = user

        self.show_tenant_dashboard()

    def show_tenant_login(self):
        self.clear_window()

        self.configure(
            fg_color=COLORS["background"]
        )

        login_frame = ctk.CTkFrame(
            self,
            width=450,
            height=570,
            corner_radius=22,
            fg_color=COLORS["surface"]
        )

        login_frame.place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

        login_frame.pack_propagate(False)

        ctk.CTkLabel(
            login_frame,
            text="👤",
            font=ctk.CTkFont(size=48)
        ).pack(
            pady=(35, 5)
        )

        ctk.CTkLabel(
            login_frame,
            text="Tenant Login",
            text_color=COLORS["text"],
            font=ctk.CTkFont(
                size=26,
                weight="bold"
            )
        ).pack(pady=5)

        ctk.CTkLabel(
            login_frame,
            text="Access your tenant dashboard",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=13)
        ).pack(
            pady=(0, 28)
        )

        self.tenant_username_entry = ctk.CTkEntry(
            login_frame,
            width=340,
            height=45,
            placeholder_text="Tenant username",
            corner_radius=10
        )

        self.tenant_username_entry.pack(
            pady=8
        )

        self.tenant_password_entry = ctk.CTkEntry(
            login_frame,
            width=340,
            height=45,
            placeholder_text="Tenant password",
            show="*",
            corner_radius=10
        )

        self.tenant_password_entry.pack(
            pady=8
        )

        self.tenant_show_password_var = tk.BooleanVar(
            value=False
        )

        ctk.CTkCheckBox(
            login_frame,
            text="Show password",
            variable=self.tenant_show_password_var,
            command=self.toggle_tenant_password
        ).pack(
            pady=(8, 20)
        )

        ctk.CTkButton(
            login_frame,
            text="TENANT LOGIN",
            width=340,
            height=45,
            corner_radius=10,
            fg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            font=ctk.CTkFont(
                size=13,
                weight="bold"
            ),
            command=self.tenant_login
        ).pack(
            pady=5
        )

        ctk.CTkLabel(
            login_frame,
            text="Don't have a tenant account?",
            text_color=COLORS["muted"]
        ).pack(
            pady=(25, 3)
        )

        ctk.CTkButton(
            login_frame,
            text="Register as Tenant",
            width=340,
            height=38,
            fg_color="transparent",
            hover_color="#1E3A5F",
            text_color=COLORS["primary"],
            command=self.show_registration
        ).pack()

        ctk.CTkButton(
            login_frame,
            text="← Back",
            width=340,
            height=38,
            fg_color="transparent",
            hover_color="#1E3A5F",
            command=self.show_role_selection
        ).pack(
            pady=(10, 0)
        )

    def show_role_selection(self):
        self.clear_window()

        self.configure(
            fg_color=COLORS["background"]
        )

        main_frame = ctk.CTkFrame(
            self,
            width=650,
            height=500,
            corner_radius=24,
            fg_color=COLORS["surface"]
        )

        main_frame.place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

        main_frame.pack_propagate(False)

        ctk.CTkLabel(
            main_frame,
            text="🏠",
            font=ctk.CTkFont(size=55)
        ).pack(
            pady=(40, 5)
        )

        ctk.CTkLabel(
            main_frame,
            text="Apartment Management System",
            text_color=COLORS["text"],
            font=ctk.CTkFont(
                size=27,
                weight="bold"
            )
        ).pack(pady=5)

        ctk.CTkLabel(
            main_frame,
            text="Choose your account type",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=14)
        ).pack(pady=(0, 30))

        buttons_frame = ctk.CTkFrame(
            main_frame,
            fg_color="transparent"
        )

        buttons_frame.pack(
            fill="x",
            padx=80
        )

        ctk.CTkButton(
            buttons_frame,
            text="ADMIN LOGIN",
            height=55,
            corner_radius=12,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            font=ctk.CTkFont(
                size=14,
                weight="bold"
            ),
            command=self.show_login
        ).pack(
            fill="x",
            pady=8
        )

        ctk.CTkButton(
            buttons_frame,
            text="TENANT LOGIN",
            height=55,
            corner_radius=12,
            fg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            font=ctk.CTkFont(
                size=14,
                weight="bold"
            ),
            command=self.show_tenant_login
        ).pack(
            fill="x",
            pady=8
        )

        ctk.CTkLabel(
            main_frame,
            text="Tenants can register from the Tenant Login page.",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=12)
        ).pack(
            side="bottom",
            pady=25
        )

    def delete_checked_units(self):
        if not self.checked_units:
            messagebox.showwarning(
                "No Units Selected",
                "Check at least one unit to delete."
            )
            return

        units = self.db.get_units()

        unit_map = {
            unit["unit_number"]: unit
            for unit in units
        }

        selected_vacant_units = []
        selected_occupied_units = []

        for unit_number in self.checked_units:
            unit = unit_map.get(unit_number)

            if unit is None:
                continue

            if unit["status"] == "Occupied":
                selected_occupied_units.append(
                    unit_number
                )
            else:
                selected_vacant_units.append(
                    unit_number
                )

        if not selected_vacant_units:
            messagebox.showwarning(
                "Cannot Delete",
                "Occupied units cannot be deleted."
            )
            return

        delete_list = "\n".join(
            selected_vacant_units
        )

        warning_text = (
            "The following vacant units will be deleted:\n\n"
            f"{delete_list}\n\n"
        )

        if selected_occupied_units:
            occupied_list = "\n".join(
                selected_occupied_units
            )

            warning_text += (
                "These occupied units will not be deleted:\n\n"
                f"{occupied_list}"
            )

        confirm = messagebox.askyesno(
            "Confirm Deletion",
            warning_text
        )

        if not confirm:
            return

        deleted_count = 0

        for unit_number in selected_vacant_units:
            success, message = self.db.delete_unit_by_number(
                unit_number
            )

            if success:
                deleted_count += 1

        self.checked_units.clear()

        self.refresh_units()

        messagebox.showinfo(
            "Deletion Complete",
            f"{deleted_count} vacant unit(s) deleted."
        )

    def toggle_unit_check(self, event):
        region = self.units_tree.identify_region(
            event.x,
            event.y
        )

        column = self.units_tree.identify_column(
            event.x
        )

        row_id = self.units_tree.identify_row(
            event.y
        )

        # Only allow clicking the Select column
        if region != "cell" or column != "#1" or not row_id:
            return

        values = self.units_tree.item(
            row_id,
            "values"
        )

        unit_number = values[1]

        if unit_number in self.checked_units:
            self.checked_units.remove(unit_number)
        else:
            self.checked_units.add(unit_number)

        self.refresh_units()

    def create_calendar_picker(self, parent):
        date_picker = DateEntry(
            parent,
            width=24,
            date_pattern="yyyy-mm-dd",
            background="#285477",
            foreground="white",
            borderwidth=2,
            font=("Arial", 12)
        )

        date_picker.pack(
            padx=5,
            pady=5,
            ipady=6
        )

        return date_picker

    def check_tenant_due_notifications(self, tenant_id):
        due_dates = self.db.get_due_notifications(
            tenant_id
        )

        today = datetime.now().date()
        notifications = []

        for due in due_dates:
            try:
                due_date = datetime.strptime(
                    due["due_date"],
                    "%Y-%m-%d"
                ).date()
            except ValueError:
                continue

            days_remaining = (
                due_date - today
            ).days

            # Notify when due date is within one week
            if 0 <= days_remaining <= 7:
                if days_remaining == 0:
                    timing = "today"
                elif days_remaining == 1:
                    timing = "tomorrow"
                else:
                    timing = f"in {days_remaining} days"

                notifications.append(
                    f"Payment month: {due['payment_month']}\n"
                    f"Amount: {self.money(due['amount'])}\n"
                    f"Due date: {due['due_date']} "
                    f"({timing})"
                )

                self.db.mark_due_notification_sent(
                    due["id"]
                )

        if notifications:
            messagebox.showwarning(
                "Rent Payment Reminder",
                "Your rent payment is due soon:\n\n"
                + "\n\n".join(notifications)
            )

    def add_due_date_window(self):
        window = ctk.CTkToplevel(self)

        window.title("Add Rent Due Date")
        window.geometry("470x520")
        window.transient(self)
        window.grab_set()

        ctk.CTkLabel(
            window,
            text="Add Rent Due Date",
            font=ctk.CTkFont(
                size=22,
                weight="bold"
            )
        ).pack(
            pady=(25, 20)
        )

        tenants = self.db.get_tenants()

        tenant_values = [
            f"{tenant['id']} - {tenant['full_name']}"
            for tenant in tenants
            if tenant["assigned_unit"]
        ]

        tenant_combo = ctk.CTkComboBox(
            window,
            width=350,
            values=tenant_values or ["No assigned tenants"]
        )

        tenant_combo.pack(pady=8)

        amount_entry = ctk.CTkEntry(
            window,
            width=350,
            height=42,
            placeholder_text="Rent amount"
        )

        amount_entry.pack(pady=8)

        ctk.CTkLabel(
            window,
            text="Select Due Date"
        ).pack(
            pady=(10, 5)
        )

        due_date_frame = ctk.CTkFrame(
            window,
            fg_color="transparent"
        )

        due_date_frame.pack(
            pady=8
        )

        ctk.CTkLabel(
            window,
            text="Select Rent Due Date"
        ).pack(
            pady=(10, 5)
        )

        due_date_entry = self.create_calendar_picker(
            window
        )

        month_entry = ctk.CTkEntry(
            window,
            width=350,
            height=42,
            placeholder_text="Payment month, example: October 2026"
        )

        month_entry.pack(pady=8)

        def save_due_date():
            tenant_value = tenant_combo.get().strip()
            amount_text = amount_entry.get().strip()
            due_date = due_date_entry.get_date().strftime(
                "%Y-%m-%d"
            )
            payment_month = month_entry.get().strip()

            if "-" not in tenant_value:
                messagebox.showwarning(
                    "Missing Tenant",
                    "Select a tenant.",
                    parent=window
                )
                return

            if not amount_text or not due_date or not payment_month:
                messagebox.showwarning(
                    "Missing Information",
                    "Complete all fields.",
                    parent=window
                )
                return

            try:
                amount = float(amount_text)
            except ValueError:
                messagebox.showerror(
                    "Invalid Amount",
                    "Enter a valid rent amount.",
                    parent=window
                )
                return

            tenant_id = tenant_value.split(" - ")[0]

            success, message = self.db.create_due_date(
                tenant_id,
                amount,
                due_date,
                payment_month
            )

            if success:
                messagebox.showinfo(
                    "Success",
                    message,
                    parent=window
                )

                window.destroy()
                self.refresh_due_dates()

            else:
                messagebox.showerror(
                    "Error",
                    message,
                    parent=window
                )

        ctk.CTkButton(
            window,
            text="SAVE DUE DATE",
            width=350,
            height=45,
            command=save_due_date
        ).pack(pady=25)

    def refresh_due_dates(self):
        for row in self.due_dates_tree.get_children():
            self.due_dates_tree.delete(row)

        for due in self.db.get_due_dates():
            self.due_dates_tree.insert(
                "",
                "end",
                values=(
                    due["id"],
                    due["tenant_name"],
                    due["unit_number"],
                    self.money(due["amount"]),
                    due["due_date"],
                    due["payment_month"],
                    due["status"]
                )
            )

    def show_due_dates(self):
        self.clear_content()

        self.page_title(
            "Rent Due Dates",
            "Set and manage tenant rent due dates"
        )

        toolbar = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )

        toolbar.pack(
            fill="x",
            padx=25,
            pady=5
        )

        ctk.CTkButton(
            toolbar,
            text="+ Add Due Date",
            width=170,
            height=38,
            command=self.add_due_date_window
        ).pack(
            side="left"
        )

        ctk.CTkButton(
            toolbar,
            text="Refresh",
            width=110,
            height=38,
            command=self.refresh_due_dates
        ).pack(
            side="left",
            padx=8
        )

        self.due_dates_tree = self.create_tree(
            self.content,
            (
                "id",
                "tenant",
                "unit",
                "amount",
                "due_date",
                "month",
                "status"
            ),
            (
                "ID",
                "Tenant",
                "Unit",
                "Amount",
                "Due Date",
                "Payment Month",
                "Status"
            )
        )

        self.refresh_due_dates()

    def mark_selected_contact_update_read(self):
        selected = self.contact_updates_tree.selection()

        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Select a contact update first."
            )
            return

        values = self.contact_updates_tree.item(
            selected[0],
            "values"
        )

        update_id = values[0]
        current_status = values[6]

        if current_status == "Read":
            messagebox.showinfo(
                "Already Read",
                "This contact update is already marked as Read."
            )
            return

        success, message = self.db.mark_contact_update_read(
            update_id
        )

        if success:
            messagebox.showinfo(
                "Success",
                message
            )
            self.refresh_contact_updates()
        else:
            messagebox.showerror(
                "Error",
                message
            )

    def refresh_contact_updates(self):
        for row in self.contact_updates_tree.get_children():
            self.contact_updates_tree.delete(row)

        for update in self.db.get_contact_updates():
            self.contact_updates_tree.insert(
                "",
                "end",
                values=(
                    update["id"],
                    update["tenant_name"],
                    update["assigned_unit"] or "Not assigned",
                    update["old_phone"] or "Not provided",
                    update["new_phone"],
                    update["changed_at"],
                    update["status"]
                )
            )

    def show_contact_updates(self):
        self.clear_content()

        self.page_title(
            "Contact Updates",
            "Review contact number changes made by tenants"
        )

        toolbar = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )

        toolbar.pack(
            fill="x",
            padx=25,
            pady=5
        )

        ctk.CTkButton(
            toolbar,
            text="Mark Selected as Read",
            width=190,
            height=38,
            command=self.mark_selected_contact_update_read
        ).pack(
            side="left"
        )

        ctk.CTkButton(
            toolbar,
            text="Refresh",
            width=110,
            height=38,
            command=self.refresh_contact_updates
        ).pack(
            side="left",
            padx=8
        )

        self.contact_updates_tree = self.create_tree(
            self.content,
            (
                "id",
                "tenant",
                "unit",
                "old_phone",
                "new_phone",
                "date",
                "status"
            ),
            (
                "ID",
                "Tenant",
                "Unit",
                "Previous Number",
                "New Number",
                "Changed At",
                "Status"
            )
        )

        self.refresh_contact_updates()

    def update_contact_number_window(self):
        tenant = self.db.get_tenant(
            self.current_user["id"]
        )

        window = ctk.CTkToplevel(self)
        window.title("Update Contact Number")
        window.geometry("450x360")
        window.transient(self)
        window.grab_set()

        ctk.CTkLabel(
            window,
            text="Update Contact Number",
            font=ctk.CTkFont(
                size=22,
                weight="bold"
            )
        ).pack(
            pady=(30, 15)
        )

        ctk.CTkLabel(
            window,
            text=f"Current number: {tenant['phone'] or 'Not provided'}",
            text_color="#b8c5cf"
        ).pack(
            pady=8
        )

        phone_entry = ctk.CTkEntry(
            window,
            width=340,
            height=44,
            placeholder_text="Enter new contact number"
        )

        phone_entry.pack(
            pady=15
        )

        def save_phone():
            new_phone = phone_entry.get().strip()

            if not new_phone:
                messagebox.showwarning(
                    "Missing Contact Number",
                    "Enter your new contact number.",
                    parent=window
                )
                return

            success, message = self.db.update_tenant_phone(
                tenant["id"],
                new_phone
            )

            if success:
                messagebox.showinfo(
                    "Contact Number Updated",
                    (
                        f"{message}\n\n"
                        "The administrator has been notified."
                    ),
                    parent=window
                )

                window.destroy()
                self.show_tenant_dashboard()

            else:
                messagebox.showwarning(
                    "Update Not Saved",
                    message,
                    parent=window
                )

        ctk.CTkButton(
            window,
            text="SAVE NEW NUMBER",
            width=340,
            height=45,
            command=save_phone
        ).pack(
            pady=20
        )

    def show_tenant_concerns(self):
        self.clear_window()

        tenant = self.db.get_tenant(
            self.current_user["id"]
        )

        header = ctk.CTkFrame(
            self,
            height=75,
            corner_radius=0,
            fg_color="#203346"
        )

        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="My Apartment Concerns",
            font=ctk.CTkFont(
                size=24,
                weight="bold"
            )
        ).pack(
            side="left",
            padx=30
        )

        ctk.CTkButton(
            header,
            text="Back to Dashboard",
            width=150,
            command=self.show_tenant_dashboard
        ).pack(
            side="right",
            padx=25
        )

        ctk.CTkLabel(
            self,
            text="View your submitted concerns and administrator responses.",
            text_color="#aebbc5"
        ).pack(
            anchor="w",
            padx=35,
            pady=(25, 5)
        )

        tree_frame = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        tree_frame.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=10
        )

        tree = self.create_tree(
            tree_frame,
            (
                "id",
                "unit",
                "subject",
                "message",
                "status",
                "admin_reply",
                "date"
            ),
            (
                "ID",
                "Unit",
                "Subject",
                "Concern",
                "Status",
                "Admin Reply",
                "Date"
            )
        )

        tree.column(
            "message",
            width=260
        )

        tree.column(
            "admin_reply",
            width=260
        )

        concerns = self.db.get_tenant_concerns(
            tenant["id"]
        )

        for concern in concerns:
            tree.insert(
                "",
                "end",
                values=(
                    concern["id"],
                    concern["unit_number"],
                    concern["subject"],
                    concern["message"],
                    concern["status"],
                    concern["admin_reply"] or "No response yet",
                    concern["created_at"]
                )
            )

    def notify_tenant_concerns(self, tenant_id):
        concerns = self.db.get_unnotified_resolved_concerns(
            tenant_id
        )

        if not concerns:
            return

        message_lines = []

        for concern in concerns:
            reply = concern["admin_reply"] or (
                "The administrator marked this concern as resolved."
            )

            message_lines.append(
                f"Subject: {concern['subject']}\n"
                f"Unit: {concern['unit_number']}\n"
                f"Admin response: {reply}"
            )

        messagebox.showinfo(
            "Concern Resolved",
            "Your apartment concern has been resolved.\n\n"
            + "\n\n".join(message_lines)
        )

        self.db.mark_concerns_as_notified(
            tenant_id
        )

    def show_concerns(self):
        self.clear_content()

        self.page_title(
            "Tenant Concerns",
            "View and respond to concerns submitted by tenants"
        )

        toolbar = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )

        toolbar.pack(
            fill="x",
            padx=25,
            pady=5
        )

        ctk.CTkButton(
            toolbar,
            text="Mark Selected as Resolved",
            width=210,
            height=38,
            fg_color="#21885f",
            hover_color="#2da873",
            command=self.resolve_selected_concern
        ).pack(
            side="left"
        )

        ctk.CTkButton(
            toolbar,
            text="Refresh",
            width=110,
            height=38,
            command=self.refresh_concerns
        ).pack(
            side="left",
            padx=8
        )

        self.concerns_tree = self.create_tree(
            self.content,
            (
                "id",
                "tenant",
                "unit",
                "subject",
                "message",
                "status",
                "date"
            ),
            (
                "ID",
                "Tenant",
                "Unit",
                "Subject",
                "Concern",
                "Status",
                "Date Submitted"
            )
        )

        self.concerns_tree.column(
            "message",
            width=280
        )

        self.concerns_tree.bind(
            "<<TreeviewSelect>>",
            self.show_selected_concern_details
        )

        self.refresh_concerns()

    def refresh_concerns(self):
        for row in self.concerns_tree.get_children():
            self.concerns_tree.delete(row)

        for concern in self.db.get_concerns():
            self.concerns_tree.insert(
                "",
                "end",
                values=(
                    concern["id"],
                    concern["tenant_name"],
                    concern["unit_number"],
                    concern["subject"],
                    concern["message"],
                    concern["status"],
                    concern["created_at"]
                )
            )

    def show_selected_concern_details(self, event=None):
        selected = self.concerns_tree.selection()

        if not selected:
            return

        values = self.concerns_tree.item(
            selected[0],
            "values"
        )

        messagebox.showinfo(
            "Tenant Concern",
            (
                f"Tenant: {values[1]}\n"
                f"Unit: {values[2]}\n"
                f"Subject: {values[3]}\n\n"
                f"Message:\n{values[4]}\n\n"
                f"Status: {values[5]}"
            )
        )

    def resolve_selected_concern(self):
        selected = self.concerns_tree.selection()

        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Select a concern first."
            )
            return

        values = self.concerns_tree.item(
            selected[0],
            "values"
        )

        concern_id = values[0]
        tenant_name = values[1]
        current_status = values[5]

        if current_status == "Resolved":
            messagebox.showinfo(
                "Already Resolved",
                "This concern is already resolved."
            )
            return

        reply_window = ctk.CTkToplevel(self)
        reply_window.title("Resolve Concern")
        reply_window.geometry("500x400")
        reply_window.transient(self)
        reply_window.grab_set()

        ctk.CTkLabel(
            reply_window,
            text=f"Respond to {tenant_name}",
            font=ctk.CTkFont(
                size=20,
                weight="bold"
            )
        ).pack(pady=(25, 15))

        reply_textbox = ctk.CTkTextbox(
            reply_window,
            width=400,
            height=170
        )

        reply_textbox.pack(pady=10)

        ctk.CTkLabel(
            reply_window,
            text="Enter an optional response or resolution note."
        ).pack(pady=5)

        def save_resolution():
            admin_reply = reply_textbox.get(
                "1.0",
                "end"
            ).strip()

            success, message = self.db.resolve_concern(
                concern_id,
                admin_reply
            )

            if success:
                messagebox.showinfo(
                    "Success",
                    message,
                    parent=reply_window
                )

                reply_window.destroy()
                self.refresh_concerns()
            else:
                messagebox.showerror(
                    "Error",
                    message,
                    parent=reply_window
                )

        ctk.CTkButton(
            reply_window,
            text="MARK AS RESOLVED",
            width=400,
            height=42,
            fg_color="#21885f",
            hover_color="#2da873",
            command=save_resolution
        ).pack(pady=20)

    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()

    def toggle_password(self):
        if self.show_password_var.get():
            self.login_password.configure(show="")
        else:
            self.login_password.configure(show="*")

    def login(self):
        username = self.login_username.get().strip()
        password = self.login_password.get().strip()

        if not username or not password:
            messagebox.showwarning(
                "Missing Information",
                "Please enter your username and password."
            )
            return

        user = self.db.login(
            username,
            password
        )

        if user is None:
            messagebox.showerror(
                "Login Failed",
                "Invalid username or password."
            )
            return

        self.current_user = user

        if user["role"] == "admin":
            self.show_admin_layout()
        else:
            self.show_tenant_dashboard()

    def show_registration(self):
        self.clear_window()

        frame = ctk.CTkFrame(
            self,
            width=500,
            height=620,
            corner_radius=20,
            fg_color="#203346"
        )

        frame.place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

        frame.pack_propagate(False)

        ctk.CTkLabel(
            frame,
            text="Tenant Registration",
            font=ctk.CTkFont(
                size=25,
                weight="bold"
            )
        ).pack(pady=(30, 25))

        self.register_full_name = ctk.CTkEntry(
            frame,
            width=350,
            height=42,
            placeholder_text="Full name"
        )
        self.register_full_name.pack(pady=7)

        self.register_username = ctk.CTkEntry(
            frame,
            width=350,
            height=42,
            placeholder_text="Username"
        )
        self.register_username.pack(pady=7)

        self.register_password = ctk.CTkEntry(
            frame,
            width=350,
            height=42,
            placeholder_text="Password",
            show="*"
        )
        self.register_password.pack(pady=7)

        self.register_phone = ctk.CTkEntry(
            frame,
            width=350,
            height=42,
            placeholder_text="Phone number"
        )
        self.register_phone.pack(pady=7)

        self.register_email = ctk.CTkEntry(
            frame,
            width=350,
            height=42,
            placeholder_text="Email address"
        )
        self.register_email.pack(pady=7)

        ctk.CTkButton(
            frame,
            text="REGISTER",
            width=350,
            height=45,
            command=self.register_new_tenant
        ).pack(pady=(25, 8))

        ctk.CTkButton(
            frame,
            text="← Back to Login",
            command=self.show_login,
            fg_color="transparent",
            hover_color="#294a66"
        ).pack()

    def register_new_tenant(self):
        full_name = self.register_full_name.get().strip()
        username = self.register_username.get().strip()
        password = self.register_password.get().strip()
        phone = self.register_phone.get().strip()
        email = self.register_email.get().strip()

        if not full_name or not username or not password:
            messagebox.showwarning(
                "Missing Information",
                "Full name, username, and password are required."
            )
            return

        success, message = self.db.register_tenant(
            full_name,
            username,
            password,
            phone,
            email
        )

        if success:
            messagebox.showinfo(
                "Registration Successful",
                message
            )
            self.show_login()
        else:
            messagebox.showerror(
                "Registration Error",
                message
            )

    def show_login(self):
        self.clear_window()

        self.configure(
            fg_color="#0d171f"
        )

        login_frame = ctk.CTkFrame(
            self,
            width=430,
            height=560,
            corner_radius=20,
            fg_color="#203346"
        )

        login_frame.place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

        login_frame.pack_propagate(False)

        ctk.CTkLabel(
            login_frame,
            text="🏠",
            font=ctk.CTkFont(size=48)
        ).pack(pady=(35, 0))

        ctk.CTkLabel(
            login_frame,
            text="Apartment Management",
            font=ctk.CTkFont(
                size=24,
                weight="bold"
            )
        ).pack(pady=(5, 5))

        ctk.CTkLabel(
            login_frame,
            text="Sign in to manage your apartment",
            text_color="#b8c4ce",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(0, 30))

        self.login_username = ctk.CTkEntry(
            login_frame,
            width=330,
            height=45,
            placeholder_text="Username",
            corner_radius=8
        )

        self.login_username.pack(pady=8)

        self.login_password = ctk.CTkEntry(
            login_frame,
            width=330,
            height=45,
            placeholder_text="Password",
            show="*",
            corner_radius=8
        )

        self.login_password.pack(pady=8)

        self.show_password_var = tk.BooleanVar(
            value=False
        )

        ctk.CTkCheckBox(
            login_frame,
            text="Show password",
            variable=self.show_password_var,
            command=self.toggle_password
        ).pack(pady=(8, 20))

        ctk.CTkButton(
            login_frame,
            text="LOGIN",
            width=330,
            height=45,
            command=self.login
        ).pack(pady=5)

    def preview_assignment_tenant(self, selected_value):
        if "-" not in selected_value:
            return

        tenant_id = selected_value.split(" - ")[0]

        tenant = self.db.get_tenant(
            tenant_id
        )

        if tenant is None:
            return

        profile_image = self.create_profile_image(
            tenant["profile_picture"],
            (100, 100)
        )

        self.assignment_profile_image_ref = profile_image

        self.assignment_profile_image.configure(
            image=profile_image,
            text=""
        )

        self.assignment_profile_name.configure(
            text=tenant["full_name"]
        )

    def preview_selected_tenant(self, event=None):
        selected = self.tenants_tree.selection()

        if not selected:
            return

        values = self.tenants_tree.item(
            selected[0],
            "values"
        )

        tenant_id = values[0]

        tenant = self.db.get_tenant(
            tenant_id
        )

        if tenant is None:
            return

        profile_image = self.create_profile_image(
            tenant["profile_picture"],
            (145, 145)
        )

        self.tenant_preview_image_ref = profile_image

        self.tenant_preview_image.configure(
            image=profile_image,
            text=""
        )

        self.tenant_preview_name.configure(
            text=tenant["full_name"]
        )

        self.tenant_preview_details.configure(
            text=(
                f"Username: {tenant['username']}\n\n"
                f"Phone: {tenant['phone'] or 'Not provided'}\n\n"
                f"Email: {tenant['email'] or 'Not provided'}\n\n"
                f"Unit: {tenant['assigned_unit'] or 'Not assigned'}\n\n"
                f"Rent: {self.money(tenant['monthly_rent'])}"
            )
        )

    def approve_selected_payment(self):
        selected = self.payments_tree.selection()

        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Select a payment first."
            )
            return

        values = self.payments_tree.item(
            selected[0],
            "values"
        )

        payment_id = values[0]
        tenant_name = values[1]
        amount = values[3]
        status = values[7]

        if status != "Pending":
            messagebox.showwarning(
                "Cannot Approve",
                f"This payment is already {status}."
            )
            return

        confirm = messagebox.askyesno(
            "Approve Payment",
            (
                f"Approve this payment?\n\n"
                f"Tenant: {tenant_name}\n"
                f"Amount: {amount}"
            )
        )

        if not confirm:
            return

        success, message = self.db.approve_payment(
            payment_id
        )

        if success:
            messagebox.showinfo(
                "Payment Approved",
                message
            )
            self.refresh_payments()
        else:
            messagebox.showerror(
                "Approval Error",
                message
            )

    def reject_selected_payment(self):
        selected = self.payments_tree.selection()

        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Select a payment first."
            )
            return

        values = self.payments_tree.item(
            selected[0],
            "values"
        )

        payment_id = values[0]
        tenant_name = values[1]
        status = values[7]

        if status != "Pending":
            messagebox.showwarning(
                "Cannot Reject",
                f"This payment is already {status}."
            )
            return

        confirm = messagebox.askyesno(
            "Reject Payment",
            f"Reject the payment submitted by {tenant_name}?"
        )

        if not confirm:
            return

        success, message = self.db.reject_payment(
            payment_id
        )

        if success:
            messagebox.showinfo(
                "Payment Rejected",
                message
            )

            # Reload the payment list.
            # The rejected payment will no longer appear.
            self.show_payments()

        else:
            messagebox.showerror(
                "Rejection Error",
                message
            )

    def choose_profile_picture(self):
        file_path = filedialog.askopenfilename(
            title="Choose Profile Picture",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg"),
                ("PNG Files", "*.png"),
                ("JPEG Files", "*.jpg *.jpeg")
            ]
        )

        if not file_path:
            return

        profile_folder = Path(__file__).parent / "profile_pictures"
        profile_folder.mkdir(exist_ok=True)

        file_extension = Path(file_path).suffix
        new_file = profile_folder / (
            f"tenant_{self.current_user['id']}{file_extension}"
        )

        try:
            shutil.copy(file_path, new_file)

            self.db.connection.execute("""
                UPDATE users
                SET profile_picture = ?
                WHERE id = ?
            """, (
                str(new_file),
                self.current_user["id"]
            ))

            self.db.connection.commit()

            self.current_user = self.db.get_tenant(
                self.current_user["id"]
            )

            messagebox.showinfo(
                "Profile Picture",
                "Profile picture updated successfully."
            )

            self.show_tenant_dashboard()

        except Exception as error:
            messagebox.showerror(
                "Upload Error",
                f"Unable to save profile picture:\n{error}"
            )

    def create_profile_image(self, image_path, size=(110, 110)):
        if image_path and os.path.exists(image_path):
            try:
                image = Image.open(image_path)
                image = image.resize(size)
                return ctk.CTkImage(
                    light_image=image,
                    dark_image=image,
                    size=size
                )
            except Exception:
                pass

        image = Image.new(
            "RGB",
            size,
            "#31506b"
        )

        return ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=size
        )

    def tenant_info_card(self, parent, title, value, color, column):
        card = ctk.CTkFrame(
            parent,
            height=105,
            corner_radius=12,
            fg_color=color
        )

        card.grid(
            row=0,
            column=column,
            padx=5,
            sticky="nsew"
        )

        parent.grid_columnconfigure(
            column,
            weight=1
        )

        ctk.CTkLabel(
            card,
            text=title,
            text_color="#d7e2eb"
        ).pack(
            anchor="w",
            padx=15,
            pady=(17, 5)
        )

        ctk.CTkLabel(
            card,
            text=str(value),
            font=ctk.CTkFont(size=19, weight="bold")
        ).pack(
            anchor="w",
            padx=15
        )

    def tenant_payment_window(self):
        tenant = self.db.get_tenant(
            self.current_user["id"]
        )

        if not tenant["assigned_unit"]:
            messagebox.showwarning(
                "No Assigned Unit",
                "You cannot submit payment because you do not have an assigned unit yet."
            )
            return

        window = ctk.CTkToplevel(self)
        window.title("Submit Rent Payment")
        window.geometry("450x500")
        window.transient(self)
        window.grab_set()

        ctk.CTkLabel(
            window,
            text="Submit Rent Payment",
            font=ctk.CTkFont(size=23, weight="bold")
        ).pack(pady=(25, 10))

        ctk.CTkLabel(
            window,
            text=(
                f"Unit: {tenant['assigned_unit']}\n"
                f"Monthly rent: {self.money(tenant['monthly_rent'])}"
            ),
            text_color="#b6c3cd"
        ).pack(pady=8)

        amount_entry = ctk.CTkEntry(
            window,
            width=350,
            height=42,
            placeholder_text="Payment amount"
        )

        amount_entry.pack(pady=10)

        ctk.CTkLabel(
            window,
            text="Select Payment Date"
        ).pack(
            pady=(10, 5)
        )

        payment_date_picker = self.create_calendar_picker(
            window
        )

        reference_entry = ctk.CTkEntry(
            window,
            width=350,
            height=42,
            placeholder_text="Payment reference or receipt number"
        )

        reference_entry.pack(pady=10)

        ctk.CTkLabel(
            window,
            text=(
                "Payment will be marked as Pending.\n"
                "The administrator can view the submitted payment."
            ),
            text_color="#d3a64b",
            justify="center"
        ).pack(pady=15)

        def submit():
            amount_text = amount_entry.get().strip()
            selected_payment_date = (
                payment_date_picker.get_date()
            )

            payment_month = selected_payment_date.strftime(
                "%B %Y"
            )
            reference = reference_entry.get().strip()

            if not amount_text or not payment_month:
                messagebox.showwarning(
                    "Missing Information",
                    "Enter the amount and payment month.",
                    parent=window
                )
                return

            try:
                amount = float(amount_text)
            except ValueError:
                messagebox.showerror(
                    "Invalid Amount",
                    "Enter a valid payment amount.",
                    parent=window
                )
                return

            success, message = self.db.submit_payment(
                tenant["id"],
                amount,
                payment_month,
                reference
            )

            if success:
                messagebox.showinfo(
                    "Payment Submitted",
                    message,
                    parent=window
                )
                window.destroy()
                self.show_tenant_dashboard()
            else:
                messagebox.showerror(
                    "Payment Error",
                    message,
                    parent=window
                )

        ctk.CTkButton(
            window,
            text="SUBMIT PAYMENT",
            width=350,
            height=45,
            command=submit
        ).pack(pady=20)

    # ======================================================
    # GENERAL
    # ======================================================

    def setup_treeview_style(self):
        style = ttk.Style()

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Treeview",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            fieldbackground=COLORS["surface"],
            rowheight=38,
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", 10)
        )

        style.configure(
            "Treeview.Heading",
            background=COLORS["primary"],
            foreground="white",
            borderwidth=0,
            relief="flat",
            font=("Segoe UI", 10, "bold")
        )

        style.map(
            "Treeview",
            background=[
                ("selected", COLORS["primary_hover"])
            ],
            foreground=[
                ("selected", "white")
            ]
        )

        style.map(
            "Treeview.Heading",
            background=[
                ("active", COLORS["primary_hover"])
            ]
        )

    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()

    def money(self, amount):
        return f"₱{amount:,.2f}"

    def create_button(self, parent, text, command, width=150):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold")
        )

    # ======================================================
    # LOGIN
    # ======================================================

    def show_login(self):
        self.clear_window()

        container = ctk.CTkFrame(
            self,
            width=430,
            height=570,
            corner_radius=20,
            fg_color="#203346"
        )

        container.place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

        container.pack_propagate(False)

        ctk.CTkLabel(
            container,
            text="🏠",
            font=ctk.CTkFont(size=48)
        ).pack(pady=(35, 0))

        ctk.CTkLabel(
            container,
            text="Apartment Management",
            font=ctk.CTkFont(size=25, weight="bold")
        ).pack(pady=(5, 4))

        ctk.CTkLabel(
            container,
            text="Sign in to manage your apartment",
            text_color="#b5c0ca",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(0, 32))

        self.login_username = ctk.CTkEntry(
            container,
            width=330,
            height=45,
            placeholder_text="Username",
            corner_radius=8
        )
        self.login_username.pack(pady=8)

        self.login_password = ctk.CTkEntry(
            container,
            width=330,
            height=45,
            placeholder_text="Password",
            show="*",
            corner_radius=8
        )
        self.login_password.pack(pady=8)

        self.show_password_var = tk.BooleanVar(value=False)

        ctk.CTkCheckBox(
            container,
            text="Show password",
            variable=self.show_password_var,
            command=self.toggle_password
        ).pack(pady=(8, 20))

        self.create_button(
            container,
            "LOGIN",
            self.login,
            330
        ).pack(pady=5)

        ctk.CTkButton(
            container,
            text="← Back to Home",
            width=340,
            height=42,
            corner_radius=10,
            fg_color="transparent",
            hover_color="#1E3A5F",
            text_color=COLORS["primary"],
            command=self.show_role_selection
        ).pack(
            pady=(28, 10)
        )

    def toggle_password(self):
        if self.show_password_var.get():
            self.login_password.configure(show="")
        else:
            self.login_password.configure(show="*")

    def login(self):
        username = self.login_username.get().strip()
        password = self.login_password.get().strip()

        if not username or not password:
            messagebox.showwarning(
                "Missing Information",
                "Enter username and password."
            )
            return

        user = self.db.login(username, password)

        if user is None:
            messagebox.showerror(
                "Login Failed",
                "Invalid username or password."
            )
            return

        self.current_user = user

        if user["role"] == "admin":
            self.show_admin_layout()
        else:
            self.show_tenant_dashboard()

    # ======================================================
    # TENANT REGISTRATION
    # ======================================================

    def show_registration(self):
        self.clear_window()

        frame = ctk.CTkFrame(
            self,
            width=500,
            height=620,
            corner_radius=20,
            fg_color="#203346"
        )

        frame.place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

        frame.pack_propagate(False)

        ctk.CTkLabel(
            frame,
            text="Tenant Registration",
            font=ctk.CTkFont(size=25, weight="bold")
        ).pack(pady=(30, 25))

        self.register_full_name = ctk.CTkEntry(
            frame,
            width=350,
            height=42,
            placeholder_text="Full name"
        )
        self.register_full_name.pack(pady=7)

        self.register_username = ctk.CTkEntry(
            frame,
            width=350,
            height=42,
            placeholder_text="Username"
        )
        self.register_username.pack(pady=7)

        self.register_password = ctk.CTkEntry(
            frame,
            width=350,
            height=42,
            placeholder_text="Password",
            show="*"
        )
        self.register_password.pack(pady=7)

        self.register_phone = ctk.CTkEntry(
            frame,
            width=350,
            height=42,
            placeholder_text="Phone number"
        )
        self.register_phone.pack(pady=7)

        self.register_email = ctk.CTkEntry(
            frame,
            width=350,
            height=42,
            placeholder_text="Email address"
        )
        self.register_email.pack(pady=7)

        self.create_button(
            frame,
            "REGISTER",
            self.register_tenant,
            350
        ).pack(pady=(25, 8))

        ctk.CTkButton(
            frame,
            text="← Back to Login",
            command=self.show_login,
            fg_color="transparent",
            hover_color="#294a66"
        ).pack()

    def register_tenant(self):
        full_name = self.register_full_name.get().strip()
        username = self.register_username.get().strip()
        password = self.register_password.get().strip()
        phone = self.register_phone.get().strip()
        email = self.register_email.get().strip()

        if not full_name or not username or not password:
            messagebox.showwarning(
                "Missing Information",
                "Full name, username, and password are required."
            )
            return

        success, message = self.db.register_tenant(
            full_name,
            username,
            password,
            phone,
            email
        )

        if success:
            messagebox.showinfo("Success", message)
            self.show_login()
        else:
            messagebox.showerror("Registration Error", message)

    # ======================================================
    # ADMIN LAYOUT
    # ======================================================

    def show_admin_layout(self):
        self.clear_window()

        self.sidebar = ctk.CTkFrame(
            self,
            width=245,
            corner_radius=0,
            fg_color=COLORS["sidebar"]
        )

        self.sidebar.pack(
            side="left",
            fill="y"
        )

        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.sidebar,
            text="🏠",
            font=ctk.CTkFont(size=42)
        ).pack(pady=(28, 0))

        ctk.CTkLabel(
            self.sidebar,
            text="APARTMENT\nMANAGEMENT",
            font=ctk.CTkFont(
                family="Segoe UI",
                size=18,
                weight="bold"
            ),
            text_color=COLORS["text"],
            justify="center"
        ).pack(
            pady=(5, 35)
        )

        self.sidebar_button(
            "Dashboard",
            self.show_admin_dashboard
        )

        self.sidebar_button(
            "Units Management",
            self.show_units
        )

        self.sidebar_button(
            "Tenant Management",
            self.show_tenants
        )

        self.sidebar_button(
            "Tenant Assignment",
            self.show_assignment
        )

        self.sidebar_button(
            "Payments",
            self.show_payments
        )

        self.sidebar_button(
            "Rent Due Dates",
            self.show_due_dates
        )

        self.sidebar_button(
            "Concerns",
            self.show_concerns
        )

        self.sidebar_button(
            "Contact Updates",
            self.show_contact_updates
        )

        self.sidebar_button(
            "Reports",
            self.show_reports
        )

        ctk.CTkButton(
            self.sidebar,
            text="Logout",
            command=self.show_login,
            fg_color="#a83939",
            hover_color="#c44949",
            height=40
        ).pack(
            side="bottom",
            fill="x",
            padx=20,
            pady=25
        )

        self.content = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color="#0e171f"
        )

        self.content.pack(
            side="right",
            fill="both",
            expand=True
        )

        self.show_admin_dashboard()

    def sidebar_button(self, text, command):
        button = ctk.CTkButton(
            self.sidebar,
            text=text,
            command=command,
            anchor="w",
            height=44,
            corner_radius=10,
            fg_color="transparent",
            hover_color="#1E3A5F",
            text_color=COLORS["text"],
            font=ctk.CTkFont(
                family="Segoe UI",
                size=13
            )
        )

        button.pack(
            fill="x",
            padx=14,
            pady=4
        )

        return button

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def page_title(self, title, subtitle=""):
        header = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )

        header.pack(
            fill="x",
            padx=32,
            pady=(28, 12)
        )

        ctk.CTkLabel(
            header,
            text=title,
            text_color=COLORS["text"],
            font=ctk.CTkFont(
                family="Segoe UI",
                size=29,
                weight="bold"
            )
        ).pack(
            anchor="w"
        )

        if subtitle:
            ctk.CTkLabel(
                header,
                text=subtitle,
                text_color=COLORS["muted"],
                font=ctk.CTkFont(
                    family="Segoe UI",
                    size=13
                )
            ).pack(
                anchor="w",
                pady=(5, 0)
            )

        ctk.CTkFrame(
            header,
            height=3,
            width=70,
            fg_color=COLORS["primary"],
            corner_radius=3
        ).pack(
            anchor="w",
            pady=(14, 0)
        )

    # ======================================================
    # ADMIN DASHBOARD
    # ======================================================

    def show_admin_dashboard(self):
        self.clear_content()

        self.page_title(
            "Admin Dashboard",
            f"Welcome, {self.current_user['full_name']}"
        )

        stats = self.db.get_statistics()

        cards_frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )
        cards_frame.pack(
            fill="x",
            padx=25,
            pady=10
        )

        self.stat_card(
            cards_frame,
            "Total Units",
            stats["total_units"],
            "#246b9e",
            0
        )

        self.stat_card(
            cards_frame,
            "Occupied Units",
            stats["occupied_units"],
            "#21885f",
            1
        )

        self.stat_card(
            cards_frame,
            "Vacant Units",
            stats["vacant_units"],
            "#8c6823",
            2
        )

        self.stat_card(
            cards_frame,
            "Collected",
            self.money(stats["collected"]),
            "#80509b",
            3
        )

        self.stat_card(
            cards_frame,
            "Unpaid Balance",
            self.money(stats["unpaid"]),
            "#9b4040",
            4
        )

        lower_frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )
        lower_frame.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=20
        )

        left = ctk.CTkFrame(
            lower_frame,
            fg_color="#172635",
            corner_radius=12
        )
        left.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 10)
        )

        ctk.CTkLabel(
            left,
            text="Quick Actions",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(
            anchor="w",
            padx=20,
            pady=(20, 15)
        )

        self.create_button(
            left,
            "Manage Units",
            self.show_units,
            220
        ).pack(pady=7)

        self.create_button(
            left,
            "Manage Tenants",
            self.show_tenants,
            220
        ).pack(pady=7)

        self.create_button(
            left,
            "Assign Tenant",
            self.show_assignment,
            220
        ).pack(pady=7)

        self.create_button(
            left,
            "View Tenant Payments",
            self.show_payments,
            220
        ).pack(pady=7)

        right = ctk.CTkFrame(
            lower_frame,
            fg_color="#172635",
            corner_radius=12
        )
        right.pack(
            side="right",
            fill="both",
            expand=True,
            padx=(10, 0)
        )

        ctk.CTkLabel(
            right,
            text="System Information",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(
            anchor="w",
            padx=20,
            pady=(20, 15)
        )

        ctk.CTkLabel(
            right,
            text=(
                "The system is connected to SQLite.\n\n"
                f"Total apartment units: {stats['total_units']}\n"
                f"Occupied units: {stats['occupied_units']}\n"
                f"Vacant units: {stats['vacant_units']}\n\n"
                "Use the sidebar to manage tenants,\n"
                "units, assignments, and payments."
            ),
            justify="left",
            text_color="#b9c4ce",
            font=ctk.CTkFont(size=14)
        ).pack(
            anchor="w",
            padx=20,
            pady=5
        )

    def stat_card(self, parent, title, value, color, column):
        card = ctk.CTkFrame(
            parent,
            height=125,
            corner_radius=16,
            fg_color=COLORS["surface_light"],
            border_width=1,
            border_color=COLORS["border"]
        )

        card.grid(
            row=0,
            column=column,
            padx=7,
            pady=5,
            sticky="nsew"
        )

        parent.grid_columnconfigure(
            column,
            weight=1
        )

        ctk.CTkFrame(
            card,
            width=5,
            height=80,
            corner_radius=3,
            fg_color=color
        ).pack(
            side="left",
            padx=(14, 10),
            pady=20
        )

        details = ctk.CTkFrame(
            card,
            fg_color="transparent"
        )

        details.pack(
            side="left",
            fill="both",
            expand=True,
            pady=20
        )

        ctk.CTkLabel(
            details,
            text=title,
            text_color=COLORS["muted"],
            font=ctk.CTkFont(
                family="Segoe UI",
                size=12
            )
        ).pack(
            anchor="w"
        )

        ctk.CTkLabel(
            details,
            text=str(value),
            text_color=COLORS["text"],
            font=ctk.CTkFont(
                family="Segoe UI",
                size=23,
                weight="bold"
            )
        ).pack(
            anchor="w",
            pady=(5, 0)
        )

    # ======================================================
    # TREEVIEW HELPER
    # ======================================================

    def create_tree(self, parent, columns, headings):
        frame = ctk.CTkFrame(
            parent,
            fg_color="transparent"
        )
        frame.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=10
        )

        tree = ttk.Treeview(
            frame,
            columns=columns,
            show="headings"
        )

        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            tree.column(column, width=130, anchor="center")

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=tree.yview
        )

        tree.configure(
            yscrollcommand=scrollbar.set
        )

        tree.pack(
            side="left",
            fill="both",
            expand=True
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        return tree

    # ======================================================
    # UNITS
    # ======================================================

    def show_units(self):
        self.clear_content()

        self.page_title(
            "Apartment Units",
            "10 units per page"
        )

        if not hasattr(self, "checked_units"):
            self.checked_units = set()

        self.unit_check_vars = {}
        self.current_unit_page = 0
        self.units_per_page = 10

        # Create toolbar BEFORE using toolbar
        toolbar = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )

        toolbar.pack(
            fill="x",
            padx=30,
            pady=(5, 8)
        )

        self.create_button(
            toolbar,
            "+ Add Unit",
            self.add_unit_window,
            150
        ).pack(
            side="left"
        )

        ctk.CTkButton(
            toolbar,
            text="Delete Selected",
            width=170,
            height=38,
            fg_color=COLORS["danger"],
            hover_color=COLORS["danger_hover"],
            command=self.delete_checked_units
        ).pack(
            side="left",
            padx=8
        )

        # Unit filter dropdown
        self.unit_filter_combo = ctk.CTkComboBox(
            toolbar,
            width=170,
            height=38,
            values=[
                "All Units",
                "Occupied",
                "Vacant"
            ],
            command=self.apply_unit_filter
        )

        self.unit_filter_combo.set(
            "All Units"
        )

        self.unit_filter_combo.pack(
            side="left",
            padx=15
        )

        ctk.CTkLabel(
            toolbar,
            text="🔐 Occupied    🏠 Vacant",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=13)
        ).pack(
            side="right",
            padx=10
        )

        # Unit card area
        self.units_grid = ctk.CTkScrollableFrame(
            self.content,
            fg_color=COLORS["background"],
            corner_radius=12
        )

        self.units_grid.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=8
        )

        for column in range(5):
            self.units_grid.grid_columnconfigure(
                column,
                weight=1
            )

        # Pagination area
        self.pagination_frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )

        self.pagination_frame.pack(
            fill="x",
            padx=30,
            pady=(5, 20)
        )

        ctk.CTkButton(
            self.pagination_frame,
            text="← Previous",
            width=130,
            height=38,
            command=self.previous_unit_page
        ).pack(
            side="left"
        )

        self.unit_page_label = ctk.CTkLabel(
            self.pagination_frame,
            text="Page 1",
            font=ctk.CTkFont(
                size=14,
                weight="bold"
            )
        )

        self.unit_page_label.pack(
            side="left",
            expand=True
        )

        ctk.CTkButton(
            self.pagination_frame,
            text="Next →",
            width=130,
            height=38,
            command=self.next_unit_page
        ).pack(
            side="right"
        )

        self.refresh_units()

    def refresh_units(self):
        for widget in self.units_grid.winfo_children():
            widget.destroy()

        self.unit_check_vars = {}

        all_units = self.db.get_units()

        selected_filter = "All Units"

        if hasattr(self, "unit_filter_combo"):
            selected_filter = self.unit_filter_combo.get()

        if selected_filter == "Occupied":
            units = [
                unit
                for unit in all_units
                if unit["status"] == "Occupied"
            ]

        elif selected_filter == "Vacant":
            units = [
                unit
                for unit in all_units
                if unit["status"] == "Vacant"
            ]

        else:
            units = all_units

        total_units = len(units)

        if total_units == 0:
            self.unit_page_label.configure(
                text="No units found"
            )
            return

        total_pages = (
            total_units + self.units_per_page - 1
        ) // self.units_per_page

        if self.current_unit_page >= total_pages:
            self.current_unit_page = total_pages - 1

        start_index = (
            self.current_unit_page *
            self.units_per_page
        )

        end_index = start_index + self.units_per_page

        current_page_units = units[
            start_index:end_index
        ]

        for index, unit in enumerate(current_page_units):
            row = index // 5
            column = index % 5

            self.create_unit_card(
                self.units_grid,
                unit,
                row,
                column
            )

        self.unit_page_label.configure(
            text=(
                f"Page {self.current_unit_page + 1} "
                f"of {total_pages} "
                f"({total_units} units)"
            )
        )

    def add_unit_window(self):
        window = ctk.CTkToplevel(self)
        window.title("Add Unit")
        window.geometry("380x300")
        window.transient(self)
        window.grab_set()

        ctk.CTkLabel(
            window,
            text="Add New Unit",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=25)

        unit_entry = ctk.CTkEntry(
            window,
            width=280,
            placeholder_text="Example: Unit 201"
        )
        unit_entry.pack(pady=8)

        rent_entry = ctk.CTkEntry(
            window,
            width=280,
            placeholder_text="Monthly rent"
        )
        rent_entry.pack(pady=8)

        def save_unit():
            unit_number = unit_entry.get().strip()
            rent_text = rent_entry.get().strip()

            if not unit_number or not rent_text:
                messagebox.showwarning(
                    "Missing Information",
                    "Enter unit number and rent.",
                    parent=window
                )
                return

            try:
                rent = float(rent_text)
            except ValueError:
                messagebox.showerror(
                    "Invalid Rent",
                    "Enter a valid number.",
                    parent=window
                )
                return

            success, message = self.db.add_unit(
                unit_number,
                rent
            )

            if success:
                messagebox.showinfo(
                    "Success",
                    message,
                    parent=window
                )
                window.destroy()
                self.refresh_units()
            else:
                messagebox.showerror(
                    "Error",
                    message,
                    parent=window
                )

        self.create_button(
            window,
            "SAVE UNIT",
            save_unit,
            280
        ).pack(pady=25)

    def delete_selected_unit(self):
        selected = self.units_tree.selection()

        if not selected:
            messagebox.showwarning(
                "No Selection",
                "Select a unit first."
            )
            return

        values = self.units_tree.item(
            selected[0],
            "values"
        )

        unit_number = values[0]

        confirm = messagebox.askyesno(
            "Delete Unit",
            f"Delete {unit_number}?"
        )

        if not confirm:
            return

        success, message = self.db.delete_unit_by_number(
            unit_number
        )

        if success:
            messagebox.showinfo(
                "Success",
                message
            )
            self.refresh_units()
        else:
            messagebox.showerror(
                "Error",
                message
            )

    # ======================================================
    # TENANTS
    # ======================================================

    def show_tenants(self):
        self.clear_content()

        self.page_title(
            "Tenant Management",
            "Select a tenant to view their profile"
        )

        search_frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )

        search_frame.pack(
            fill="x",
            padx=25,
            pady=(0, 8)
        )

        self.tenant_search_entry = ctk.CTkEntry(
            search_frame,
            width=350,
            height=40,
            placeholder_text=(
                "Search tenant name, username, phone, email, or unit"
            )
        )

        self.tenant_search_entry.pack(
            side="left"
        )

        self.tenant_search_entry.bind(
            "<KeyRelease>",
            lambda event: self.refresh_tenants()
        )

        ctk.CTkButton(
            search_frame,
            text="Clear Search",
            width=130,
            height=40,
            command=self.clear_tenant_search
        ).pack(
            side="left",
            padx=8
        )

        main_frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )

        main_frame.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=10
        )

        table_frame = ctk.CTkFrame(
            main_frame,
            fg_color="transparent"
        )

        table_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 15)
        )

        profile_frame = ctk.CTkFrame(
            main_frame,
            width=250,
            corner_radius=15,
            fg_color="#172635"
        )

        profile_frame.pack(
            side="right",
            fill="y"
        )

        profile_frame.pack_propagate(False)

        ctk.CTkLabel(
            profile_frame,
            text="Tenant Profile",
            font=ctk.CTkFont(
                size=19,
                weight="bold"
            )
        ).pack(pady=(20, 15))

        empty_image = self.create_profile_image(
            "",
            (145, 145)
        )

        self.tenant_preview_image = ctk.CTkLabel(
            profile_frame,
            text="",
            image=empty_image
        )

        self.tenant_preview_image.pack(
            pady=10
        )

        self.tenant_preview_name = ctk.CTkLabel(
            profile_frame,
            text="Select a tenant",
            font=ctk.CTkFont(
                size=16,
                weight="bold"
            ),
            wraplength=210
        )

        self.tenant_preview_name.pack(
            pady=10
        )

        self.tenant_preview_details = ctk.CTkLabel(
            profile_frame,
            text="",
            justify="left",
            text_color="#b8c5cf"
        )

        self.tenant_preview_details.pack(
            anchor="w",
            padx=20,
            pady=10
        )

        self.tenants_tree = self.create_tree(
            table_frame,
            (
                "id",
                "name",
                "username",
                "phone",
                "email",
                "unit",
                "rent"
            ),
            (
                "ID",
                "Full Name",
                "Username",
                "Phone",
                "Email",
                "Assigned Unit",
                "Monthly Rent"
            )
        )

        self.tenants_tree.bind(
            "<<TreeviewSelect>>",
            self.preview_selected_tenant
        )

        self.refresh_tenants()

    def refresh_tenants(self):
        for row in self.tenants_tree.get_children():
            self.tenants_tree.delete(row)

        search_text = ""

        if hasattr(self, "tenant_search_entry"):
            search_text = (
                self.tenant_search_entry.get()
                .strip()
                .lower()
            )

        tenants = self.db.get_tenants()

        for tenant in tenants:
            searchable_text = " ".join([
                tenant["full_name"] or "",
                tenant["username"] or "",
                tenant["phone"] or "",
                tenant["email"] or "",
                tenant["assigned_unit"] or ""
            ]).lower()

            if search_text and search_text not in searchable_text:
                continue

            self.tenants_tree.insert(
                "",
                "end",
                values=(
                    tenant["id"],
                    tenant["full_name"],
                    tenant["username"],
                    tenant["phone"],
                    tenant["email"],
                    tenant["assigned_unit"] or "Not assigned",
                    self.money(tenant["monthly_rent"])
                )
            )

    # ======================================================
    # TENANT ASSIGNMENT
    # ======================================================

    def show_assignment(self):
        self.clear_content()

        self.page_title(
            "Tenant Assignment",
            "Assign or remove a tenant from an apartment unit"
        )

        form = ctk.CTkFrame(
            self.content,
            width=500,
            corner_radius=15,
            fg_color="#172635"
        )
        form.pack(
            padx=30,
            pady=20,
            anchor="nw"
        )

        ctk.CTkLabel(
            form,
            text="Assign Tenant to Unit",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(
            anchor="w",
            padx=25,
            pady=(25, 20)
        )

        tenants = self.db.get_tenants()
        vacant_units = self.db.get_vacant_units()

        tenant_values = [
            f"{tenant['id']} - {tenant['full_name']}"
            for tenant in tenants
            if not tenant["assigned_unit"]
        ]

        unit_values = [
            f"{unit['id']} - {unit['unit_number']}"
            for unit in vacant_units
        ]

        self.assignment_tenant = ctk.CTkComboBox(
            form,
            width=400,
            values=tenant_values or ["No available tenants"],
            command=self.preview_assignment_tenant
        )
        self.assignment_tenant.pack(pady=8)

        empty_image = self.create_profile_image(
            "",
            (100, 100)
        )

        self.assignment_profile_image = ctk.CTkLabel(
            form,
            text="",
            image=empty_image
        )

        self.assignment_profile_image.pack(
            pady=(8, 4)
        )

        self.assignment_profile_name = ctk.CTkLabel(
            form,
            text="Select a tenant to view profile picture",
            text_color="#b8c5cf"
        )

        self.assignment_profile_name.pack(
            pady=(0, 8)
        )

        self.assignment_unit = ctk.CTkComboBox(
            form,
            width=400,
            values=unit_values or ["No vacant units"]
        )
        self.assignment_unit.pack(pady=8)

        self.assignment_rent = ctk.CTkEntry(
            form,
            width=400,
            placeholder_text="Monthly rent"
        )
        self.assignment_rent.pack(pady=8)

        self.create_button(
            form,
            "ASSIGN TENANT",
            self.assign_selected_tenant,
            400
        ).pack(pady=(20, 8))

        self.create_button(
            form,
            "REMOVE TENANT ASSIGNMENT",
            self.remove_assignment_window,
            400
        ).pack(pady=(0, 25))

    def assign_selected_tenant(self):
        tenant_value = self.assignment_tenant.get()
        unit_value = self.assignment_unit.get()
        rent_text = self.assignment_rent.get().strip()

        if "-" not in tenant_value or "-" not in unit_value:
            messagebox.showwarning(
                "Invalid Selection",
                "Select a tenant and a vacant unit."
            )
            return

        if not rent_text:
            messagebox.showwarning(
                "Missing Rent",
                "Enter monthly rent."
            )
            return

        try:
            rent = float(rent_text)
        except ValueError:
            messagebox.showerror(
                "Invalid Rent",
                "Enter a valid amount."
            )
            return

        tenant_id = tenant_value.split(" - ")[0]
        unit_id = unit_value.split(" - ")[0]

        success, message = self.db.assign_tenant(
            tenant_id,
            unit_id,
            rent
        )

        if success:
            messagebox.showinfo("Success", message)
            self.show_assignment()
        else:
            messagebox.showerror("Error", message)

    def remove_assignment_window(self):
        window = ctk.CTkToplevel(self)
        window.title("Remove Assignment")
        window.geometry("400x300")
        window.transient(self)
        window.grab_set()

        ctk.CTkLabel(
            window,
            text="Remove Tenant Assignment",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=25)

        tenants = self.db.get_tenants()

        tenant_values = [
            f"{tenant['id']} - {tenant['full_name']} - "
            f"{tenant['assigned_unit']}"
            for tenant in tenants
            if tenant["assigned_unit"]
        ]

        combo = ctk.CTkComboBox(
            window,
            width=320,
            values=tenant_values or ["No assigned tenants"]
        )
        combo.pack(pady=15)

        def remove():
            value = combo.get()

            if "-" not in value:
                messagebox.showwarning(
                    "Invalid Selection",
                    "Select an assigned tenant.",
                    parent=window
                )
                return

            tenant_id = value.split(" - ")[0]

            success, message = self.db.unassign_tenant(
                tenant_id
            )

            if success:
                messagebox.showinfo(
                    "Success",
                    message,
                    parent=window
                )
                window.destroy()
                self.show_assignment()
            else:
                messagebox.showerror(
                    "Error",
                    message,
                    parent=window
                )

        self.create_button(
            window,
            "REMOVE ASSIGNMENT",
            remove,
            320
        ).pack(pady=20)

    # ======================================================
    # PAYMENTS
    # ======================================================

    def show_payments(self):
        self.clear_content()

        self.page_title(
            "Payment Management",
            "Review payments submitted by tenants"
        )

        toolbar = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )

        toolbar.pack(
            fill="x",
            padx=25,
            pady=5
        )

        ctk.CTkButton(
            toolbar,
            text="Approve Selected",
            width=170,
            height=38,
            fg_color="#21885f",
            hover_color="#2da873",
            command=self.approve_selected_payment
        ).pack(
            side="left",
            padx=(0, 8)
        )

        ctk.CTkButton(
            toolbar,
            text="Reject Selected",
            width=160,
            height=38,
            fg_color="#a83e3e",
            hover_color="#c34e4e",
            command=self.reject_selected_payment
        ).pack(
            side="left",
            padx=8
        )

        ctk.CTkButton(
            toolbar,
            text="Refresh",
            width=110,
            height=38,
            command=self.refresh_payments
        ).pack(
            side="left",
            padx=8
        )

        self.payments_tree = self.create_tree(
            self.content,
            (
                "id",
                "tenant",
                "unit",
                "amount",
                "month",
                "date",
                "reference",
                "status"
            ),
            (
                "ID",
                "Tenant",
                "Unit",
                "Amount",
                "Payment Month",
                "Date",
                "Reference",
                "Status"
            )
        )

        self.refresh_payments()

    def refresh_payments(self):
        for row in self.payments_tree.get_children():
            self.payments_tree.delete(row)

        for payment in self.db.get_payments():
            self.payments_tree.insert(
                "",
                "end",
                values=(
                    payment["id"],
                    payment["tenant_name"],
                    payment["unit_number"],
                    self.money(payment["amount"]),
                    payment["payment_month"],
                    payment["payment_date"],
                    payment["reference"],
                    payment["status"]
                )
            )

    # ======================================================
    # REPORTS
    # ======================================================

    def show_reports(self):
        self.clear_content()

        self.page_title(
            "Reports",
            "Apartment and payment summary"
        )

        stats = self.db.get_statistics()
        tenants = self.db.get_tenants()
        units = self.db.get_units()
        payments = self.db.get_payments()

        report_frame = ctk.CTkFrame(
            self.content,
            fg_color="#172635",
            corner_radius=15
        )
        report_frame.pack(
            fill="x",
            padx=30,
            pady=20
        )

        report_text = (
            f"Total registered tenants: {len(tenants)}\n"
            f"Total apartment units: {stats['total_units']}\n"
            f"Occupied units: {stats['occupied_units']}\n"
            f"Vacant units: {stats['vacant_units']}\n"
            f"Total payment transactions: {len(payments)}\n"
            f"Total collected payments: {self.money(stats['collected'])}\n"
            f"Total unpaid balance: {self.money(stats['unpaid'])}"
        )

        ctk.CTkLabel(
            report_frame,
            text=report_text,
            justify="left",
            font=ctk.CTkFont(size=16)
        ).pack(
            anchor="w",
            padx=25,
            pady=25
        )

        occupied_frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent"
        )
        occupied_frame.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=5
        )

        ctk.CTkLabel(
            occupied_frame,
            text="Occupied Units",
            font=ctk.CTkFont(size=19, weight="bold")
        ).pack(
            anchor="w",
            pady=(0, 8)
        )

        tree = self.create_tree(
            occupied_frame,
            (
                "unit",
                "tenant",
                "rent"
            ),
            (
                "Unit",
                "Tenant",
                "Monthly Rent"
            )
        )

        for unit in units:
            if unit["status"] == "Occupied":
                tree.insert(
                    "",
                    "end",
                    values=(
                        unit["unit_number"],
                        unit["tenant_name"],
                        self.money(unit["monthly_rent"])
                    )
                )

    # ======================================================
    # TENANT DASHBOARD
    # ======================================================

    def show_tenant_dashboard(self):
        self.clear_window()

        self.configure(fg_color="#0d171f")

        tenant = self.db.get_tenant(
            self.current_user["id"]
        )

        self.check_tenant_due_notifications(
            tenant["id"]
        )

        self.notify_tenant_concerns(
            tenant["id"]
        )

        # ----------------------------
        # Header
        # ----------------------------

        header = ctk.CTkFrame(
            self,
            height=75,
            corner_radius=0,
            fg_color="#1d3448"
        )

        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Tenant Portal",
            font=ctk.CTkFont(size=25, weight="bold")
        ).pack(
            side="left",
            padx=30
        )

        ctk.CTkButton(
            header,
            text="Logout",
            width=110,
            fg_color="#a83e3e",
            hover_color="#c34e4e",
            command=self.show_login
        ).pack(
            side="right",
            padx=25
        )

        # ----------------------------
        # Main layout
        # ----------------------------

        main = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        main.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=25
        )

        # ----------------------------
        # Left profile card
        # ----------------------------

        profile_card = ctk.CTkFrame(
            main,
            width=280,
            corner_radius=18,
            fg_color="#1a2b3a"
        )

        profile_card.pack(
            side="left",
            fill="y",
            padx=(0, 15)
        )

        profile_card.pack_propagate(False)

        profile_image = self.create_profile_image(
            tenant["profile_picture"],
            (125, 125)
        )

        profile_image_label = ctk.CTkLabel(
            profile_card,
            text="",
            image=profile_image
        )

        profile_image_label.pack(pady=(35, 15))

        ctk.CTkLabel(
            profile_card,
            text=tenant["full_name"],
            font=ctk.CTkFont(size=19, weight="bold"),
            wraplength=220
        ).pack(pady=5)

        ctk.CTkLabel(
            profile_card,
            text=f"@{tenant['username']}",
            text_color="#aebcc8"
        ).pack(pady=2)

        ctk.CTkButton(
            profile_card,
            text="Change Profile Picture",
            width=220,
            command=self.choose_profile_picture
        ).pack(pady=(25, 10))

        ctk.CTkLabel(
            profile_card,
            text=(
                f"Phone: {tenant['phone'] or 'Not provided'}\n\n"
                f"Email: {tenant['email'] or 'Not provided'}"
            ),
            justify="left",
            text_color="#b8c5cf"
        ).pack(
            anchor="w",
            padx=25,
            pady=20
        )

        # ----------------------------
        # Right side
        # ----------------------------

        right = ctk.CTkFrame(
            main,
            fg_color="transparent"
        )

        right.pack(
            side="right",
            fill="both",
            expand=True
        )

        ctk.CTkLabel(
            right,
            text=f"Welcome back, {tenant['full_name']}",
            font=ctk.CTkFont(size=25, weight="bold")
        ).pack(
            anchor="w",
            pady=(0, 18)
        )

        # Information cards

        cards = ctk.CTkFrame(
            right,
            fg_color="transparent"
        )

        cards.pack(
            fill="x",
            pady=5
        )

        assigned_unit = tenant["assigned_unit"] or "Not assigned"
        monthly_rent = tenant["monthly_rent"] or 0

        self.tenant_info_card(
            cards,
            "Assigned Unit",
            assigned_unit,
            "#246b9e",
            0
        )

        self.tenant_info_card(
            cards,
            "Monthly Rent",
            self.money(monthly_rent),
            "#80509b",
            1
        )

        self.tenant_info_card(
            cards,
            "Account Status",
            "Active",
            "#21885f",
            2
        )

        # Action buttons

        actions = ctk.CTkFrame(
            right,
            fg_color="#172635",
            corner_radius=15
        )

        actions.pack(
            fill="x",
            pady=20
        )

        ctk.CTkButton(
            actions,
            text="View Rent Due Dates",
            height=42,
            command=self.show_tenant_due_dates
        ).pack(
            fill="x",
            padx=20,
            pady=6
        )

        ctk.CTkLabel(
            actions,
            text="Tenant Services",
            font=ctk.CTkFont(size=19, weight="bold")
        ).pack(
            anchor="w",
            padx=20,
            pady=(18, 10)
        )

        ctk.CTkButton(
            actions,
            text="Submit Rent Payment",
            height=42,
            command=self.tenant_payment_window
        ).pack(
            fill="x",
            padx=20,
            pady=6
        )

        ctk.CTkButton(
        actions,
            text="Submit Apartment Concern",
            height=42,
            command=self.tenant_concern_window
        ).pack(
            fill="x",
            padx=20,
            pady=6
        )

        ctk.CTkButton(
            actions,
            text="View My Concerns",
            height=42,
            fg_color="#31536d",
            hover_color="#3c6a89",
            command=self.show_tenant_concerns
        ).pack(
            fill="x",
            padx=20,
            pady=6
        )

        ctk.CTkButton(
            actions,
            text="Update Contact Number",
            height=42,
            command=self.update_contact_number_window
        ).pack(
            fill="x",
            padx=20,
            pady=6
        )

        ctk.CTkButton(
            actions,
            text="Refresh Dashboard",
            height=42,
            fg_color="#31536d",
            hover_color="#3c6a89",
            command=self.show_tenant_dashboard
        ).pack(
            fill="x",
            padx=20,
            pady=(6, 20)
        )

        # Payment history

        ctk.CTkLabel(
            right,
            text="My Payment History",
            font=ctk.CTkFont(size=19, weight="bold")
        ).pack(
            anchor="w",
            pady=(5, 8)
        )

        tree_frame = ctk.CTkFrame(
            right,
            fg_color="transparent"
        )

        tree_frame.pack(
            fill="both",
            expand=True
        )

        tree = self.create_tree(
            tree_frame,
            (
                "unit",
                "amount",
                "month",
                "date",
                "reference",
                "status"
            ),
            (
                "Unit",
                "Amount",
                "Month",
                "Date",
                "Reference",
                "Status"
            )
        )

        for payment in self.db.get_tenant_payments(
            tenant["id"]
        ):
            tree.insert(
                "",
                "end",
                values=(
                    payment["unit_number"],
                    self.money(payment["amount"]),
                    payment["payment_month"],
                    payment["payment_date"],
                    payment["reference"],
                    payment["status"]
                )
            )

    def show_tenant_due_dates(self):
        self.clear_window()

        tenant = self.db.get_tenant(
            self.current_user["id"]
        )

        header = ctk.CTkFrame(
            self,
            height=75,
            corner_radius=0,
            fg_color="#203346"
        )

        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="My Rent Due Dates",
            font=ctk.CTkFont(
                size=24,
                weight="bold"
            )
        ).pack(
            side="left",
            padx=30
        )

        ctk.CTkButton(
            header,
            text="Back to Dashboard",
            width=150,
            command=self.show_tenant_dashboard
        ).pack(
            side="right",
            padx=25
        )

        tree_frame = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        tree_frame.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=30
        )

        tree = self.create_tree(
            tree_frame,
            (
                "unit",
                "amount",
                "due_date",
                "month",
                "status"
            ),
            (
                "Unit",
                "Amount",
                "Due Date",
                "Payment Month",
                "Status"
            )
        )

        for due in self.db.get_tenant_due_dates(
            tenant["id"]
        ):
            tree.insert(
                "",
                "end",
                values=(
                    due["unit_number"],
                    self.money(due["amount"]),
                    due["due_date"],
                    due["payment_month"],
                    due["status"]
                )
            )

    def tenant_concern_window(self):
        window = ctk.CTkToplevel(self)

        window.title("Submit Apartment Concern")
        window.geometry("520x560")
        window.transient(self)
        window.grab_set()

        ctk.CTkLabel(
            window,
            text="Submit Apartment Concern",
            font=ctk.CTkFont(
                size=23,
                weight="bold"
            )
        ).pack(
            pady=(25, 15)
        )

        ctk.CTkLabel(
            window,
            text=(
                "Describe a problem or concern in your apartment.\n"
                "The administrator will receive your message."
            ),
            text_color="#b8c5cf",
            justify="center"
        ).pack(
            pady=5
        )

        subject_entry = ctk.CTkEntry(
            window,
            width=400,
            height=42,
            placeholder_text="Concern subject"
        )

        subject_entry.pack(
            pady=(25, 10)
        )

        message_textbox = ctk.CTkTextbox(
            window,
            width=400,
            height=220
        )

        message_textbox.pack(
            pady=10
        )

        ctk.CTkLabel(
            window,
            text="Example: leaking faucet, broken light, or noisy neighbor",
            text_color="#9eabb7"
        ).pack(
            pady=5
        )

        def submit_concern():
            subject = subject_entry.get().strip()

            message = message_textbox.get(
                "1.0",
                "end"
            ).strip()

            if not subject or not message:
                messagebox.showwarning(
                    "Missing Information",
                    "Enter a subject and describe your concern.",
                    parent=window
                )
                return

            success, result = self.db.submit_concern(
                self.current_user["id"],
                subject,
                message
            )

            if success:
                messagebox.showinfo(
                    "Concern Submitted",
                    result,
                    parent=window
                )

                window.destroy()
                self.show_tenant_dashboard()

            else:
                messagebox.showerror(
                    "Submission Error",
                    result,
                    parent=window
                )

        ctk.CTkButton(
            window,
            text="SUBMIT CONCERN",
            width=400,
            height=45,
            command=submit_concern
        ).pack(
            pady=25
        )


# ==========================================================
# START APPLICATION
# ==========================================================

if __name__ == "__main__":
    app = ApartmentManagementApp()
    app.mainloop()
