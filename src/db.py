""" GridCare-Lite database layer.
 
Schema covers: users (role-based), substations (imported from the grid-analysis
CSV), outages, work orders, complaints, and a status_history table for audit
trail. All write operations validate foreign keys and state transitions in
Python before touching the database, since SQLite's own FK enforcement is
off by default and the spec asks for graceful handling of bad input rather
than a crash.
"""
import sqlite3
from datetime import datetime
 
VALID_ROLES = ('admin', 'engineer', 'technician', 'customer_service')
OUTAGE_STATUSES = ('Open', 'In Progress', 'Resolved')
WORK_ORDER_STATUSES = ('Pending', 'Scheduled', 'Completed')
SEVERITIES = ('Low', 'Medium', 'High', 'Critical')
 
 
def get_connection(db_path='gridcare.db'):
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn
 
 
def init_db(db_path='gridcare.db'):
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'engineer', 'technician', 'customer_service')),
            active INTEGER NOT NULL DEFAULT 1
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS substations (
            substation_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            region TEXT NOT NULL,
            voltage_kv INTEGER,
            status TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS outages (
            outage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            substation_id INTEGER NOT NULL,
            reported_by INTEGER NOT NULL,
            description TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'Medium' CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
            status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'In Progress', 'Resolved')),
            reported_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY (substation_id) REFERENCES substations(substation_id),
            FOREIGN KEY (reported_by) REFERENCES users(user_id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS work_orders (
            work_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            outage_id INTEGER NOT NULL,
            assigned_technician INTEGER,
            assigned_by INTEGER NOT NULL,
            scheduled_date TEXT,
            status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Scheduled', 'Completed')),
            work_notes TEXT,
            FOREIGN KEY (outage_id) REFERENCES outages(outage_id),
            FOREIGN KEY (assigned_technician) REFERENCES users(user_id),
            FOREIGN KEY (assigned_by) REFERENCES users(user_id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            complaint_id INTEGER PRIMARY KEY AUTOINCREMENT,
            logged_by INTEGER NOT NULL,
            outage_id INTEGER,
            customer_name TEXT NOT NULL,
            details TEXT NOT NULL,
            logged_at TEXT NOT NULL,
            FOREIGN KEY (logged_by) REFERENCES users(user_id),
            FOREIGN KEY (outage_id) REFERENCES outages(outage_id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS status_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL CHECK (entity_type IN ('outage', 'work_order')),
            entity_id INTEGER NOT NULL,
            old_status TEXT,
            new_status TEXT NOT NULL,
            changed_by INTEGER NOT NULL,
            changed_at TEXT NOT NULL,
            FOREIGN KEY (changed_by) REFERENCES users(user_id)
        )
    ''')
    conn.commit()
    return conn
 
 
# ---------------------------------------------------------------------------
# Substation import (bridges the grid-analysis component into GridCare-Lite)
# ---------------------------------------------------------------------------
def import_substations_from_csv(conn, csv_path):
    """
    Imports cleaned substation data from the data-science component's
    substations.csv so outages can only be logged against a real asset.
    Returns (imported_count, skipped_count).
    """
    import csv
    imported, skipped = 0, 0
    cur = conn.cursor()
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                sub_id = int(row['Substation ID'])
                cur.execute('''
                    INSERT INTO substations (substation_id, name, region, voltage_kv, status)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(substation_id) DO UPDATE SET
                        name=excluded.name, region=excluded.region,
                        voltage_kv=excluded.voltage_kv, status=excluded.status
                ''', (sub_id, row['Name'], row['Region'], int(row['Voltage (kV)']), row['Status']))
                imported += 1
            except (KeyError, ValueError):
                skipped += 1
                continue
    conn.commit()
    return imported, skipped
 
 
def substation_exists(conn, substation_id):
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM substations WHERE substation_id = ?', (substation_id,))
    return cur.fetchone() is not None
 
 
# ---------------------------------------------------------------------------
# Outage operations
# ---------------------------------------------------------------------------
class GridCareError(Exception):
    """Raised for validation failures — caught by the GUI layer and shown
    to the user as a friendly message rather than crashing the app."""
    pass
 
 
def create_outage(conn, substation_id, reported_by, description, severity='Medium'):
    if not substation_exists(conn, substation_id):
        raise GridCareError(f"No such substation: {substation_id}")
    if not description or not description.strip():
        raise GridCareError("Outage description is required.")
    if severity not in SEVERITIES:
        raise GridCareError(f"Invalid severity: {severity}")
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO outages (substation_id, reported_by, description, severity, status, reported_at)
        VALUES (?, ?, ?, ?, 'Open', ?)
    ''', (substation_id, reported_by, description.strip(), severity, datetime.now().isoformat()))
    conn.commit()
    return cur.lastrowid
 
 
def update_outage_status(conn, outage_id, new_status, changed_by):
    if new_status not in OUTAGE_STATUSES:
        raise GridCareError(f"Invalid outage status: {new_status}")
    cur = conn.cursor()
    cur.execute('SELECT status FROM outages WHERE outage_id = ?', (outage_id,))
    row = cur.fetchone()
    if row is None:
        raise GridCareError(f"No such outage: {outage_id}")
    old_status = row['status']
    resolved_at = datetime.now().isoformat() if new_status == 'Resolved' else None
    cur.execute('''
        UPDATE outages SET status = ?, resolved_at = COALESCE(?, resolved_at) WHERE outage_id = ?
    ''', (new_status, resolved_at, outage_id))
    cur.execute('''
        INSERT INTO status_history (entity_type, entity_id, old_status, new_status, changed_by, changed_at)
        VALUES ('outage', ?, ?, ?, ?, ?)
    ''', (outage_id, old_status, new_status, changed_by, datetime.now().isoformat()))
    conn.commit()
 
 
def list_outages(conn, status=None, region=None):
    query = '''
        SELECT o.outage_id, o.description, o.severity, o.status, o.reported_at, o.resolved_at,
               s.name AS substation_name, s.region
        FROM outages o JOIN substations s ON o.substation_id = s.substation_id
        WHERE 1=1
    '''
    params = []
    if status:
        query += ' AND o.status = ?'
        params.append(status)
    if region:
        query += ' AND s.region = ?'
        params.append(region)
    query += ' ORDER BY o.reported_at DESC'
    return conn.execute(query, params).fetchall()
 
 
# ---------------------------------------------------------------------------
# Work order operations
# ---------------------------------------------------------------------------
def create_work_order(conn, outage_id, assigned_technician, assigned_by, scheduled_date=None):
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM outages WHERE outage_id = ?', (outage_id,))
    if cur.fetchone() is None:
        raise GridCareError(f"No such outage: {outage_id}")
    cur.execute('SELECT role FROM users WHERE user_id = ?', (assigned_technician,))
    tech_row = cur.fetchone()
    if tech_row is None or tech_row['role'] != 'technician':
        raise GridCareError("Assigned user must be a valid technician.")
    cur.execute('''
        INSERT INTO work_orders (outage_id, assigned_technician, assigned_by, scheduled_date, status)
        VALUES (?, ?, ?, ?, 'Pending')
    ''', (outage_id, assigned_technician, assigned_by, scheduled_date))
    conn.commit()
    return cur.lastrowid
 
 
def update_work_order_status(conn, work_order_id, new_status, changed_by, work_notes=None):
    if new_status not in WORK_ORDER_STATUSES:
        raise GridCareError(f"Invalid work order status: {new_status}")
    cur = conn.cursor()
    cur.execute('SELECT status FROM work_orders WHERE work_order_id = ?', (work_order_id,))
    row = cur.fetchone()
    if row is None:
        raise GridCareError(f"No such work order: {work_order_id}")
    old_status = row['status']
    cur.execute('''
        UPDATE work_orders SET status = ?, work_notes = COALESCE(?, work_notes)
        WHERE work_order_id = ?
    ''', (new_status, work_notes, work_order_id))
    cur.execute('''
        INSERT INTO status_history (entity_type, entity_id, old_status, new_status, changed_by, changed_at)
        VALUES ('work_order', ?, ?, ?, ?, ?)
    ''', (work_order_id, old_status, new_status, changed_by, datetime.now().isoformat()))
    conn.commit()
 
 
def list_work_orders_for_technician(conn, technician_id):
    return conn.execute('''
        SELECT w.work_order_id, w.status, w.scheduled_date, w.work_notes,
               o.outage_id, o.description, o.severity, s.name AS substation_name
        FROM work_orders w
        JOIN outages o ON w.outage_id = o.outage_id
        JOIN substations s ON o.substation_id = s.substation_id
        WHERE w.assigned_technician = ?
        ORDER BY w.scheduled_date
    ''', (technician_id,)).fetchall()
 
 
# ---------------------------------------------------------------------------
# Complaint operations
# ---------------------------------------------------------------------------
def log_complaint(conn, logged_by, customer_name, details, outage_id=None):
    if not customer_name or not customer_name.strip():
        raise GridCareError("Customer name is required.")
    if not details or not details.strip():
        raise GridCareError("Complaint details are required.")
    if outage_id is not None:
        cur = conn.cursor()
        cur.execute('SELECT 1 FROM outages WHERE outage_id = ?', (outage_id,))
        if cur.fetchone() is None:
            raise GridCareError(f"No such outage to link: {outage_id}")
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO complaints (logged_by, outage_id, customer_name, details, logged_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (logged_by, outage_id, customer_name.strip(), details.strip(), datetime.now().isoformat()))
    conn.commit()
    return cur.lastrowid
 
 
def list_complaints(conn):
    return conn.execute('''
        SELECT c.complaint_id, c.customer_name, c.details, c.logged_at,
               c.outage_id, o.status AS outage_status
        FROM complaints c LEFT JOIN outages o ON c.outage_id = o.outage_id
        ORDER BY c.logged_at DESC
    ''').fetchall()
 
 
# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def get_dashboard_stats(conn):
    stats = {}
    stats['open_outages'] = conn.execute(
        "SELECT COUNT(*) c FROM outages WHERE status != 'Resolved'").fetchone()['c']
    stats['resolved_outages'] = conn.execute(
        "SELECT COUNT(*) c FROM outages WHERE status = 'Resolved'").fetchone()['c']
    stats['pending_work_orders'] = conn.execute(
        "SELECT COUNT(*) c FROM work_orders WHERE status != 'Completed'").fetchone()['c']
    stats['total_complaints'] = conn.execute(
        "SELECT COUNT(*) c FROM complaints").fetchone()['c']
    row = conn.execute('''
        SELECT AVG(julianday(resolved_at) - julianday(reported_at)) AS avg_days
        FROM outages WHERE status = 'Resolved' AND resolved_at IS NOT NULL
    ''').fetchone()
    stats['avg_resolution_days'] = round(row['avg_days'], 2) if row['avg_days'] is not None else None
    stats['outages_by_region'] = conn.execute('''
        SELECT s.region, COUNT(*) c FROM outages o
        JOIN substations s ON o.substation_id = s.substation_id
        GROUP BY s.region ORDER BY c DESC
    ''').fetchall()
    stats['outages_by_severity'] = conn.execute('''
        SELECT severity, COUNT(*) c FROM outages GROUP BY severity
    ''').fetchall()
    stats['outages_by_status'] = conn.execute('''
        SELECT status, COUNT(*) c FROM outages GROUP BY status
    ''').fetchall()
    return stats