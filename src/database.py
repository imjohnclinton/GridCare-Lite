"""
database.py — GridCare-Lite
Schema creation, password hashing, seeding, and all query helpers.
"""

import sqlite3
import hashlib
import os
import csv
import re
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
    ("admin", "admin123", "admin", "Admin User"),
    ("engineer1", "pass123", "engineer", "Kwame Asante"),
    ("engineer2", "pass123", "engineer", "Akosua Owusu"),
    ("tech1", "pass123", "technician", "Ama Serwaa"),
    ("tech2", "pass123", "technician", "Kojo Mensah"),
    ("tech3", "pass123", "technician", "Yaw Boateng"),
    ("cs1", "pass123", "customer_service", "Esi Mensah"),
    ("cs2", "pass123", "customer_service", "Adwoa Nyarko"),
]


_SEED_SUBSTATIONS = [
    (101, "Achimota Substation", "Greater Accra"),
    (102, "Accra Central Substation", "Greater Accra"),
    (103, "Tema Main Substation", "Greater Accra"),
    (104, "Kumasi Central Substation", "Ashanti"),
    (105, "Takoradi Main Substation", "Western"),
    (106, "Cape Coast Substation", "Central"),
    (107, "Tamale Main Substation", "Northern"),
    (108, "Ho Central Substation", "Volta"),
    (109, "Koforidua Substation", "Eastern"),
    (110, "Sunyani Main Substation", "Bono"),
]


_SEED_LINES = [
    ("Achimota Feeder A", "33kV", "Greater Accra", 101),
    ("Achimota Feeder B", "11kV", "Greater Accra", 101),
    ("Accra Central Feeder", "11kV", "Greater Accra", 102),
    ("Tema Industrial Line", "33kV", "Greater Accra", 103),
    ("Kumasi North Feeder", "33kV", "Ashanti", 104),
    ("Kumasi South Feeder", "11kV", "Ashanti", 104),
    ("Takoradi Feeder A", "11kV", "Western", 105),
    ("Cape Coast Feeder", "11kV", "Central", 106),
    ("Tamale Northern Line", "33kV", "Northern", 107),
    ("Ho Distribution Feeder", "11kV", "Volta", 108),
    ("Koforidua Feeder", "11kV", "Eastern", 109),
    ("Sunyani Feeder A", "33kV", "Bono", 110),
]


def seed_data(conn: sqlite3.Connection):
    """
    Populate a new GridCare-Lite database with demonstration data.

    Existing databases are not duplicated because each section is only
    populated when its corresponding table is empty.
    """
    cur = conn.cursor()

    # ---------------------------------------------------------------
    # Users
    # ---------------------------------------------------------------

    if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        for username, password, role, full_name in _SEED_USERS:
            cur.execute(
                """
                INSERT INTO users
                    (username, password_hash, role, full_name)
                VALUES (?, ?, ?, ?)
                """,
                (
                    username,
                    hash_password(password),
                    role,
                    full_name
                ),
            )

    # ---------------------------------------------------------------
    # Substations
    # ---------------------------------------------------------------

    if cur.execute(
        "SELECT COUNT(*) FROM substations"
    ).fetchone()[0] == 0:

        cur.executemany(
            """
            INSERT INTO substations
                (substation_id, name, region)
            VALUES (?, ?, ?)
            """,
            _SEED_SUBSTATIONS,
        )

    # ---------------------------------------------------------------
    # Lines
    # ---------------------------------------------------------------

    if cur.execute(
        "SELECT COUNT(*) FROM lines"
    ).fetchone()[0] == 0:

        cur.executemany(
            """
            INSERT INTO lines
                (name, voltage, region, substation_id)
            VALUES (?, ?, ?, ?)
            """,
            _SEED_LINES,
        )

    # ---------------------------------------------------------------
    # Look up seeded users
    # ---------------------------------------------------------------

    engineer1 = cur.execute(
        "SELECT user_id FROM users WHERE username='engineer1'"
    ).fetchone()[0]

    engineer2 = cur.execute(
        "SELECT user_id FROM users WHERE username='engineer2'"
    ).fetchone()[0]

    tech1 = cur.execute(
        "SELECT user_id FROM users WHERE username='tech1'"
    ).fetchone()[0]

    tech2 = cur.execute(
        "SELECT user_id FROM users WHERE username='tech2'"
    ).fetchone()[0]

    tech3 = cur.execute(
        "SELECT user_id FROM users WHERE username='tech3'"
    ).fetchone()[0]

    cs1 = cur.execute(
        "SELECT user_id FROM users WHERE username='cs1'"
    ).fetchone()[0]

    cs2 = cur.execute(
        "SELECT user_id FROM users WHERE username='cs2'"
    ).fetchone()[0]

    # ---------------------------------------------------------------
    # Outages
    # ---------------------------------------------------------------

    if cur.execute(
        "SELECT COUNT(*) FROM outages"
    ).fetchone()[0] == 0:

        sample_outages = [
            (
                101,
                engineer1,
                "Transformer overheating reported at Achimota Substation.",
                "High",
                "Open",
                "2026-08-26 08:15:00",
                None,
            ),

            (
                102,
                engineer1,
                "Protection relay trip causing partial supply interruption.",
                "Critical",
                "In Progress",
                "2026-08-25 14:30:00",
                None,
            ),

            (
                103,
                engineer2,
                "Industrial feeder interruption affecting customers in Tema.",
                "High",
                "In Progress",
                "2026-08-25 10:20:00",
                None,
            ),

            (
                104,
                engineer2,
                "Damaged distribution cable detected during inspection.",
                "Medium",
                "Open",
                "2026-08-24 16:45:00",
                None,
            ),

            (
                105,
                engineer1,
                "Breaker failure caused temporary feeder outage.",
                "Critical",
                "Resolved",
                "2026-08-20 07:30:00",
                "2026-08-20 12:45:00",
            ),

            (
                106,
                engineer2,
                "Voltage instability reported on Cape Coast feeder.",
                "Medium",
                "Resolved",
                "2026-08-19 11:00:00",
                "2026-08-19 15:30:00",
            ),

            (
                107,
                engineer1,
                "Lightning-related fault detected on northern transmission line.",
                "High",
                "Resolved",
                "2026-08-18 20:10:00",
                "2026-08-19 03:20:00",
            ),

            (
                108,
                engineer2,
                "Scheduled inspection identified deteriorating switchgear.",
                "Low",
                "Open",
                "2026-08-27 09:00:00",
                None,
            ),

            (
                109,
                engineer1,
                "Feeder protection system repeatedly tripping.",
                "Medium",
                "Open",
                "2026-08-27 13:20:00",
                None,
            ),

            (
                110,
                engineer2,
                "Transformer cooling fan failure detected.",
                "High",
                "Resolved",
                "2026-08-21 06:40:00",
                "2026-08-21 10:15:00",
            ),
        ]

        cur.executemany(
            """
            INSERT INTO outages
            (
                substation_id,
                reported_by,
                description,
                severity,
                status,
                reported_at,
                resolved_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            sample_outages,
        )

    # ---------------------------------------------------------------
    # Work Orders
    # ---------------------------------------------------------------

    if cur.execute(
        "SELECT COUNT(*) FROM work_orders"
    ).fetchone()[0] == 0:

        # Get outage IDs using their descriptions/substations.
        outages = {
            row[1]: row[0]
            for row in cur.execute(
                """
                SELECT outage_id, substation_id
                FROM outages
                """
            ).fetchall()
        }

        sample_work_orders = [
            (
                outages[102],
                tech1,
                "2026-08-28",
                "Scheduled",
            ),

            (
                outages[103],
                tech2,
                "2026-08-28",
                "Scheduled",
            ),

            (
                outages[105],
                tech1,
                "2026-08-20",
                "Completed",
            ),

            (
                outages[106],
                tech2,
                "2026-08-19",
                "Completed",
            ),

            (
                outages[107],
                tech3,
                "2026-08-18",
                "Completed",
            ),

            (
                outages[110],
                tech3,
                "2026-08-21",
                "Completed",
            ),
        ]

        cur.executemany(
            """
            INSERT INTO work_orders
                (
                    outage_id,
                    assigned_technician,
                    scheduled_date,
                    status
                )
            VALUES (?, ?, ?, ?)
            """,
            sample_work_orders,
        )

    # ---------------------------------------------------------------
    # Complaints
    # ---------------------------------------------------------------

    if cur.execute(
        "SELECT COUNT(*) FROM complaints"
    ).fetchone()[0] == 0:

        outages = {
            row[1]: row[0]
            for row in cur.execute(
                """
                SELECT outage_id, substation_id
                FROM outages
                """
            ).fetchall()
        }

        sample_complaints = [
            (
                cs1,
                outages[102],
                "Daniel Mensah",
                "0240001001",
                "Customer reports no electricity since afternoon.",
                "2026-08-25 15:10:00",
                "Open",
            ),

            (
                cs2,
                outages[103],
                "Akua Boateng",
                "0200001002",
                "Factory has experienced complete power interruption.",
                "2026-08-25 11:05:00",
                "Open",
            ),

            (
                cs1,
                outages[105],
                "Joseph Arthur",
                "0540001003",
                "Customer reported prolonged outage in residential area.",
                "2026-08-20 08:45:00",
                "Resolved",
            ),

            (
                cs2,
                outages[107],
                "Fatima Ibrahim",
                "0550001004",
                "Customer reported loss of supply after thunderstorm.",
                "2026-08-18 21:00:00",
                "Resolved",
            ),

            (
                cs1,
                None,
                "Grace Osei",
                "0270001005",
                "Customer reports intermittent low voltage. No known outage.",
                "2026-08-27 17:25:00",
                "Open",
            ),
        ]

        cur.executemany(
            """
            INSERT INTO complaints
            (
                logged_by,
                outage_id,
                customer_name,
                contact,
                description,
                logged_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            sample_complaints,
        )

    conn.commit()


# ---------------------------------------------------------------------------
# Robust CSV import
# ---------------------------------------------------------------------------

def _normalise_header(value):
    """
    Convert headers such as:

        Substation ID
        substation-id
        SUBSTATION_ID
        ﻿Substation_ID

    into:

        substation_id
    """
    text = str(value or "")
    text = text.replace("\ufeff", "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _read_csv_rows(filepath):
    """
    Read a CSV file and return rows with normalised column names.

    Supports:
    - UTF-8 files
    - Excel UTF-8 BOM files
    - comma-separated files
    - semicolon-separated files
    - tab-separated files
    - pipe-separated files
    """
    with open(filepath, "r", newline="", encoding="utf-8-sig") as file:
        sample = file.read(8192)
        file.seek(0)

        try:
            dialect = csv.Sniffer().sniff(
                sample,
                delimiters=",;\t|"
            )
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(file, dialect=dialect)

        if not reader.fieldnames:
            raise ValueError("The CSV file does not contain a header row.")

        rows = []

        for raw_row in reader:
            row = {}

            for raw_key, raw_value in raw_row.items():
                if raw_key is None:
                    continue

                key = _normalise_header(raw_key)

                if isinstance(raw_value, list):
                    raw_value = ",".join(raw_value)

                row[key] = str(raw_value or "").strip()

            if any(row.values()):
                rows.append(row)

        return rows


def _pick(columns, *candidates):
    """Return the first matching column name."""
    normalised_candidates = [
        _normalise_header(candidate)
        for candidate in candidates
    ]

    for candidate in normalised_candidates:
        if candidate in columns:
            return candidate

    return None


def _to_integer(value):
    """Convert values such as 12, 12.0, or '12' to an integer."""
    value = str(value or "").strip()

    if not value:
        return None

    try:
        return int(float(value.replace(",", "")))
    except (ValueError, TypeError, OverflowError):
        return None


def import_substations_csv(conn, filepath):
    """
    Import a substations CSV.

    Accepted examples:

        substation_id,name,region
        Substation ID,Substation Name,Region
        id,station,area

    The ID column is optional. If it is missing, IDs are generated.
    """
    rows = _read_csv_rows(filepath)

    if not rows:
        raise ValueError("The CSV file contains no data rows.")

    columns = set(rows[0].keys())

    id_col = _pick(
        columns,
        "substation_id",
        "substationid",
        "sub_id",
        "station_id",
        "substation_code",
        "station_code",
        "id",
        "code"
    )

    name_col = _pick(
        columns,
        "name",
        "substation",
        "substation_name",
        "station",
        "station_name"
    )

    region_col = _pick(
        columns,
        "region",
        "region_name",
        "area",
        "zone",
        "location",
        "district"
    )

    if not name_col or not region_col:
        raise ValueError(
            "The substations CSV must contain a name and region column.\n\n"
            f"Columns detected:\n{', '.join(sorted(columns))}\n\n"
            "Accepted name columns: name, substation, substation_name\n"
            "Accepted region columns: region, area, zone, location"
        )

    next_id = conn.execute(
        "SELECT COALESCE(MAX(substation_id), 0) + 1 FROM substations"
    ).fetchone()[0]

    imported = 0

    try:
        for row in rows:
            name = (row.get(name_col) or "").strip()
            region = (row.get(region_col) or "").strip()

            if not name:
                continue

            if not region:
                region = "Unknown"

            substation_id = None

            if id_col:
                substation_id = _to_integer(row.get(id_col))

            if substation_id is None or substation_id <= 0:
                while conn.execute(
                    "SELECT 1 FROM substations WHERE substation_id=?",
                    (next_id,)
                ).fetchone():
                    next_id += 1

                substation_id = next_id
                next_id += 1

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO substations
                    (substation_id, name, region)
                VALUES (?, ?, ?)
                """,
                (substation_id, name, region)
            )

            if cursor.rowcount == 1:
                imported += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    return imported


def _find_substation_id(conn, value):
    """
    Resolve a substation reference that may be either:
    - a numeric substation ID
    - a substation name
    """
    value = str(value or "").strip()

    if not value:
        return None

    numeric_id = _to_integer(value)

    if numeric_id is not None:
        exists = conn.execute(
            "SELECT substation_id FROM substations WHERE substation_id=?",
            (numeric_id,)
        ).fetchone()

        return exists[0] if exists else None

    result = conn.execute(
        """
        SELECT substation_id
        FROM substations
        WHERE name = ? COLLATE NOCASE
        """,
        (value,)
    ).fetchone()

    return result[0] if result else None


def import_lines_csv(conn, filepath):
    """
    Import lines.csv.

    Supports examples such as:

        line_id,name,voltage,region,substation_id
        Line ID,Line Name,Voltage,Region,Substation ID
        id,feeder,kv,area,station
    """
    rows = _read_csv_rows(filepath)

    if not rows:
        raise ValueError("The CSV file contains no data rows.")

    columns = set(rows[0].keys())

    line_id_col = _pick(
        columns,
        "line_id",
        "lineid",
        "line_code",
        "line_number",
        "id"
    )

    name_col = _pick(
        columns,
        "name",
        "line",
        "line_name",
        "feeder",
        "feeder_name"
    )

    voltage_col = _pick(
        columns,
        "voltage",
        "voltage_kv",
        "kv",
        "voltage_level"
    )

    region_col = _pick(
        columns,
        "region",
        "region_name",
        "area",
        "zone",
        "location",
        "district"
    )

    substation_col = _pick(
        columns,
        "substation_id",
        "substationid",
        "sub_id",
        "station_id",
        "substation",
        "substation_name",
        "from_substation",
        "from_substation_id"
    )

    if not name_col and not line_id_col:
        raise ValueError(
            "The lines CSV must contain either a line name or line ID column.\n\n"
            f"Columns detected:\n{', '.join(sorted(columns))}"
        )

    imported = 0

    try:
        for row in rows:
            raw_line_id = row.get(line_id_col, "") if line_id_col else ""
            line_id = _to_integer(raw_line_id)

            if name_col:
                line_name = (row.get(name_col) or "").strip()
            else:
                line_name = ""

            if not line_name:
                line_name = f"Line {raw_line_id}".strip()

            if not line_name or line_name == "Line":
                continue

            voltage = (
                (row.get(voltage_col) or "").strip()
                if voltage_col else ""
            )

            region = (
                (row.get(region_col) or "").strip()
                if region_col else ""
            )

            substation_id = _find_substation_id(
                conn,
                row.get(substation_col) if substation_col else ""
            )

            if line_id is not None:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO lines
                        (line_id, name, voltage, region, substation_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        line_id,
                        line_name,
                        voltage,
                        region,
                        substation_id
                    )
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO lines
                        (name, voltage, region, substation_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        line_name,
                        voltage,
                        region,
                        substation_id
                    )
                )

            if cursor.rowcount == 1:
                imported += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    return imported


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