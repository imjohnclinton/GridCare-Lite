import sqlite3
 
def init_db(db_path='gridcare.db'):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'engineer', 'technician', 'customer_service'))
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS substations (
            substation_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            region TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS outages (
            outage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            substation_id INTEGER NOT NULL,
            reported_by INTEGER NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'Open' CHECK (status IN ('Open', 'In Progress', 'Resolved')),
            reported_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            scheduled_date TEXT,
            status TEXT DEFAULT 'Pending' CHECK (status IN ('Pending', 'Scheduled', 'Completed')),
            FOREIGN KEY (outage_id) REFERENCES outages(outage_id),
            FOREIGN KEY (assigned_technician) REFERENCES users(user_id)
        )
    ''')
    conn.commit()
    return conn
