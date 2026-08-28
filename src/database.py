"""
database.py — GridCare-Lite
Schema creation, password hashing, seeding, and all query helpers.
"""

import sqlite3
import hashlib
import os
import csv
from datetime import datetime


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Return 'salt_hex:key_hex' using PBKDF2-SHA256."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored: str) -> bool:
    salt_hex, key_hex = stored.split(":")
    salt = bytes.fromhex(salt_hex)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return key.hex() == key_hex


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db(db_path: str = "gridcare.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            role          TEXT    NOT NULL CHECK (role IN
                            ('admin','engineer','technician','customer_service')),
            full_name     TEXT    NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS substations (
            substation_id INTEGER PRIMARY KEY,
            name          TEXT NOT NULL,
            region        TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lines (
            line_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            voltage       TEXT,
            region        TEXT,
            substation_id INTEGER,
            FOREIGN KEY (substation_id) REFERENCES substations(substation_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS outages (
            outage_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            substation_id INTEGER NOT NULL,
            reported_by   INTEGER NOT NULL,
            description   TEXT,
            severity      TEXT DEFAULT 'Medium'
                            CHECK (severity IN ('Low','Medium','High','Critical')),
            status        TEXT DEFAULT 'Open'
                            CHECK (status IN ('Open','In Progress','Resolved')),
            reported_at   TEXT DEFAULT (datetime('now','localtime')),
            resolved_at   TEXT,
            FOREIGN KEY (substation_id) REFERENCES substations(substation_id),
            FOREIGN KEY (reported_by)   REFERENCES users(user_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS work_orders (
            work_order_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            outage_id          INTEGER NOT NULL,
            assigned_technician INTEGER,
            scheduled_date     TEXT,
            status             TEXT DEFAULT 'Pending'
                                 CHECK (status IN ('Pending','Scheduled','Completed')),
            created_at         TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (outage_id)          REFERENCES outages(outage_id),
            FOREIGN KEY (assigned_technician) REFERENCES users(user_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            complaint_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            logged_by     INTEGER NOT NULL,
            outage_id     INTEGER,
            customer_name TEXT NOT NULL,
            contact       TEXT,
            description   TEXT,
            logged_at     TEXT DEFAULT (datetime('now','localtime')),
            status        TEXT DEFAULT 'Open'
                            CHECK (status IN ('Open','Resolved')),
            FOREIGN KEY (logged_by) REFERENCES users(user_id),
            FOREIGN KEY (outage_id) REFERENCES outages(outage_id)
        )
    """)

    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Seed data — runs once when tables are empty
# ---------------------------------------------------------------------------

_SEED_USERS = [
    ("admin",     "admin123", "admin",            "Admin User"),
    ("engineer1", "pass123",  "engineer",         "Kwame Asante"),
    ("tech1",     "pass123",  "technician",       "Ama Serwaa"),
    ("cs1",       "pass123",  "customer_service", "Esi Mensah"),
]

_SEED_SUBSTATIONS = [
    (1, "Accra Central",   "Greater Accra"),
    (2, "Kumasi Central",  "Ashanti"),
    (3, "Takoradi",        "Western"),
    (4, "Tamale",          "Northern"),
    (5, "Cape Coast",      "Central"),
    (6, "Ho",              "Volta"),
    (7, "Sunyani",         "Bono"),
    (8, "Bolgatanga",      "Upper East"),
    (9, "Wa",              "Upper West"),
    (10,"Koforidua",       "Eastern"),
]


def seed_data(conn: sqlite3.Connection):
    """Insert default users and substations only when the tables are empty."""
    cur = conn.cursor()

    if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        for uname, pw, role, name in _SEED_USERS:
            cur.execute(
                "INSERT INTO users (username, password_hash, role, full_name) VALUES (?,?,?,?)",
                (uname, hash_password(pw), role, name),
            )

    if cur.execute("SELECT COUNT(*) FROM substations").fetchone()[0] == 0:
        cur.executemany(
            "INSERT OR IGNORE INTO substations (substation_id, name, region) VALUES (?,?,?)",
            _SEED_SUBSTATIONS,
        )

    conn.commit()


# ---------------------------------------------------------------------------
# CSV import (for the data-science component's output)
# ---------------------------------------------------------------------------

def _read_csv_rows(filepath):
    """Read a CSV and return a list of dicts with normalised headers.
    encoding='utf-8-sig' strips the hidden BOM Excel adds."""
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Could not read any columns from this file.")
        reader.fieldnames = [
            (h or "").strip().lower().replace(" ", "_").replace("-", "_")
            for h in reader.fieldnames
        ]
        return list(reader)


def _pick(cols, *candidates):
    """Return the first candidate present in cols, else None."""
    for c in candidates:
        if c in cols:
            return c
    return None


def import_substations_csv(conn, filepath):
    rows = _read_csv_rows(filepath)
    if not rows:
        raise ValueError("The file has no data rows.")

    cols = set(rows[0].keys())
    id_col     = _pick(cols, "substation_id", "id", "sub_id", "station_id", "substationid")
    name_col   = _pick(cols, "name", "substation", "substation_name", "station", "station_name")
    region_col = _pick(cols, "region", "area", "zone", "location", "district")

    if not name_col or not region_col:
        raise ValueError(
            "Could not match the columns in this file.\n\n"
            f"Columns found: {', '.join(sorted(cols)) or '(none)'}\n\n"
            "Needed: a name column (name/substation) and a region column (region/zone/area)."
        )

    count = 0
    for row in rows:
        name   = (row.get(name_col) or "").strip()
        region = (row.get(region_col) or "").strip()
        if not name:
            continue
        sid = None
        if id_col and (row.get(id_col) or "").strip():
            try:
                sid = int(float(row[id_col].strip()))
            except ValueError:
                sid = None
        if sid is None:  # no usable ID in file → auto-assign
            sid = conn.execute(
                "SELECT COALESCE(MAX(substation_id),0)+1 FROM substations"
            ).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO substations (substation_id, name, region) VALUES (?,?,?)",
            (sid, name, region),
        )
        count += 1
    conn.commit()
    return count


def import_lines_csv(conn, filepath):
    rows = _read_csv_rows(filepath)
    if not rows:
        raise ValueError("The file has no data rows.")

    cols = set(rows[0].keys())
    name_col   = _pick(cols, "name", "line", "line_name", "feeder", "feeder_name")
    volt_col   = _pick(cols, "voltage", "voltage_kv", "kv", "voltage_level")
    region_col = _pick(cols, "region", "area", "zone", "location", "district")
    sub_col    = _pick(cols, "substation_id", "sub_id", "station_id",
                       "substation", "substation_name", "from_substation")

    if not name_col:
        raise ValueError(
            "Could not find a line-name column.\n\n"
            f"Columns found: {', '.join(sorted(cols)) or '(none)'}"
        )

    count = 0
    for row in rows:
        name = (row.get(name_col) or "").strip()
        if not name:
            continue
        sub_id = None
        if sub_col:
            raw = (row.get(sub_col) or "").strip()
            if raw:
                try:
                    sub_id = int(float(raw))          # numeric substation id
                except ValueError:                    # maybe it's a substation NAME
                    r = conn.execute(
                        "SELECT substation_id FROM substations WHERE name = ? COLLATE NOCASE",
                        (raw,),
                    ).fetchone()
                    sub_id = r[0] if r else None
        conn.execute(
            "INSERT INTO lines (name, voltage, region, substation_id) VALUES (?,?,?,?)",
            (name,
             (row.get(volt_col) or "") if volt_col else "",
             (row.get(region_col) or "") if region_col else "",
             sub_id),
        )
        count += 1
    conn.commit()
    return count


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def authenticate(conn: sqlite3.Connection, username: str, password: str) -> dict | None:
    row = conn.execute(
        "SELECT user_id, username, password_hash, role, full_name FROM users WHERE username=?",
        (username,),
    ).fetchone()
    if row and verify_password(password, row[2]):
        return {"user_id": row[0], "username": row[1], "role": row[3], "full_name": row[4]}
    return None


# ---------------------------------------------------------------------------
# Substations
# ---------------------------------------------------------------------------

def get_all_substations(conn):
    return conn.execute("SELECT substation_id, name, region FROM substations ORDER BY name").fetchall()


# ---------------------------------------------------------------------------
# Users / Technicians
# ---------------------------------------------------------------------------

def get_technicians(conn):
    return conn.execute(
        "SELECT user_id, full_name FROM users WHERE role='technician' ORDER BY full_name"
    ).fetchall()


# ---------------------------------------------------------------------------
# Outages
# ---------------------------------------------------------------------------

def get_outages(conn, status_filter=None, region_filter=None):
    q = """
        SELECT o.outage_id, s.name, s.region, o.severity, o.description,
               o.status, u.full_name, o.reported_at, o.resolved_at
        FROM outages o
        JOIN substations s ON o.substation_id = s.substation_id
        JOIN users u       ON o.reported_by   = u.user_id
        WHERE 1=1
    """
    params = []
    if status_filter and status_filter != "All":
        q += " AND o.status = ?"
        params.append(status_filter)
    if region_filter and region_filter != "All":
        q += " AND s.region = ?"
        params.append(region_filter)
    q += " ORDER BY o.reported_at DESC"
    return conn.execute(q, params).fetchall()


def create_outage(conn, substation_id, reported_by, description, severity):
    cur = conn.execute(
        "INSERT INTO outages (substation_id, reported_by, description, severity) VALUES (?,?,?,?)",
        (substation_id, reported_by, description, severity),
    )
    conn.commit()
    return cur.lastrowid


def update_outage_status(conn, outage_id, new_status):
    resolved = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == "Resolved" else None
    conn.execute(
        "UPDATE outages SET status=?, resolved_at=? WHERE outage_id=?",
        (new_status, resolved, outage_id),
    )
    conn.commit()


def get_open_outages(conn):
    return conn.execute(
        "SELECT outage_id, substation_id, description, status FROM outages WHERE status != 'Resolved' ORDER BY reported_at DESC"
    ).fetchall()


# ---------------------------------------------------------------------------
# Work Orders
# ---------------------------------------------------------------------------

def create_work_order(conn, outage_id, technician_id, scheduled_date):
    cur = conn.execute(
        "INSERT INTO work_orders (outage_id, assigned_technician, scheduled_date, status) VALUES (?,?,?,'Scheduled')",
        (outage_id, technician_id, scheduled_date),
    )
    conn.commit()
    return cur.lastrowid


def get_work_orders_for_technician(conn, technician_id):
    return conn.execute("""
        SELECT wo.work_order_id, o.outage_id, s.name, o.description,
               wo.scheduled_date, wo.status, o.severity
        FROM work_orders wo
        JOIN outages o     ON wo.outage_id = o.outage_id
        JOIN substations s ON o.substation_id = s.substation_id
        WHERE wo.assigned_technician = ?
        ORDER BY wo.scheduled_date
    """, (technician_id,)).fetchall()


def get_all_work_orders(conn):
    return conn.execute("""
        SELECT wo.work_order_id, o.outage_id, s.name, t.full_name,
               wo.scheduled_date, wo.status
        FROM work_orders wo
        JOIN outages o     ON wo.outage_id = o.outage_id
        JOIN substations s ON o.substation_id = s.substation_id
        LEFT JOIN users t  ON wo.assigned_technician = t.user_id
        ORDER BY wo.created_at DESC
    """).fetchall()


def complete_work_order(conn, work_order_id):
    """Mark work order Completed AND set the linked outage to Resolved."""
    row = conn.execute(
        "SELECT outage_id FROM work_orders WHERE work_order_id=?", (work_order_id,)
    ).fetchone()
    if not row:
        return
    outage_id = row[0]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE work_orders SET status='Completed' WHERE work_order_id=?", (work_order_id,))
    conn.execute("UPDATE outages SET status='Resolved', resolved_at=? WHERE outage_id=?", (now, outage_id))
    conn.commit()


# ---------------------------------------------------------------------------
# Complaints
# ---------------------------------------------------------------------------

def create_complaint(conn, logged_by, outage_id, customer_name, contact, description):
    cur = conn.execute(
        "INSERT INTO complaints (logged_by, outage_id, customer_name, contact, description) VALUES (?,?,?,?,?)",
        (logged_by, outage_id if outage_id else None, customer_name, contact, description),
    )
    conn.commit()
    return cur.lastrowid


def get_all_complaints(conn):
    return conn.execute("""
        SELECT c.complaint_id, c.customer_name, c.contact, c.description,
               c.outage_id, c.status, c.logged_at, u.full_name
        FROM complaints c
        JOIN users u ON c.logged_by = u.user_id
        ORDER BY c.logged_at DESC
    """).fetchall()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def get_report_stats(conn) -> dict:
    open_count = conn.execute(
        "SELECT COUNT(*) FROM outages WHERE status != 'Resolved'"
    ).fetchone()[0]

    avg_row = conn.execute("""
        SELECT AVG(
            (julianday(resolved_at) - julianday(reported_at)) * 24
        ) FROM outages WHERE status='Resolved' AND resolved_at IS NOT NULL
    """).fetchone()
    avg_hours = round(avg_row[0], 1) if avg_row[0] is not None else 0.0

    by_region = conn.execute("""
        SELECT s.region, COUNT(o.outage_id)
        FROM outages o JOIN substations s ON o.substation_id = s.substation_id
        GROUP BY s.region ORDER BY COUNT(o.outage_id) DESC
    """).fetchall()

    total_resolved = conn.execute(
        "SELECT COUNT(*) FROM outages WHERE status='Resolved'"
    ).fetchone()[0]

    return {
        "open_count": open_count,
        "avg_resolution_hours": avg_hours,
        "by_region": by_region,
        "total_resolved": total_resolved,
    }


def get_regions(conn):
    rows = conn.execute("SELECT DISTINCT region FROM substations ORDER BY region").fetchall()
    return [r[0] for r in rows]