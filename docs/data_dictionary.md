# GridCare-Lite — Data Dictionary

## users
| Column        | Type    | Constraints                          | Description                  |
|---------------|---------|--------------------------------------|------------------------------|
| user_id       | INTEGER | PK, AUTOINCREMENT                    | Unique user identifier       |
| username      | TEXT    | UNIQUE, NOT NULL                     | Login username               |
| password_hash | TEXT    | NOT NULL                             | PBKDF2-SHA256 hashed password|
| role          | TEXT    | NOT NULL, CHECK IN (4 values)        | admin / engineer / technician / customer_service |
| full_name     | TEXT    | NOT NULL                             | Display name                 |

## substations
| Column        | Type    | Constraints       | Description              |
|---------------|---------|-------------------|--------------------------|
| substation_id | INTEGER | PK                | Unique substation ID     |
| name          | TEXT    | NOT NULL          | Substation name          |
| region        | TEXT    | NOT NULL          | Geographic region        |

## lines
| Column        | Type    | Constraints       | Description              |
|---------------|---------|-------------------|--------------------------|
| line_id       | INTEGER | PK, AUTOINCREMENT | Unique line ID           |
| name          | TEXT    | NOT NULL          | Line name                |
| voltage       | TEXT    |                   | Voltage level            |
| region        | TEXT    |                   | Geographic region        |
| substation_id | INTEGER | FK → substations  | Parent substation        |

## outages
| Column        | Type    | Constraints                          | Description                  |
|---------------|---------|--------------------------------------|------------------------------|
| outage_id     | INTEGER | PK, AUTOINCREMENT                    | Unique outage ID             |
| substation_id | INTEGER | FK → substations, NOT NULL           | Affected substation          |
| reported_by   | INTEGER | FK → users, NOT NULL                 | User who reported            |
| description   | TEXT    |                                      | Fault description            |
| severity      | TEXT    | CHECK IN (Low,Medium,High,Critical)  | Severity level               |
| status        | TEXT    | DEFAULT 'Open', CHECK IN (3 values)  | Open / In Progress / Resolved|
| reported_at   | TEXT    | DEFAULT current timestamp            | When reported                |
| resolved_at   | TEXT    |                                      | When resolved (nullable)     |

## work_orders
| Column              | Type    | Constraints                     | Description                |
|---------------------|---------|---------------------------------|----------------------------|
| work_order_id       | INTEGER | PK, AUTOINCREMENT               | Unique work order ID       |
| outage_id           | INTEGER | FK → outages, NOT NULL          | Linked outage              |
| assigned_technician | INTEGER | FK → users                      | Assigned technician        |
| scheduled_date      | TEXT    |                                 | Planned date (YYYY-MM-DD)  |
| status              | TEXT    | DEFAULT 'Pending', CHECK (3)    | Pending / Scheduled / Completed |
| created_at          | TEXT    | DEFAULT current timestamp       | Creation time              |

## complaints
| Column        | Type    | Constraints              | Description                  |
|---------------|---------|--------------------------|------------------------------|
| complaint_id  | INTEGER | PK, AUTOINCREMENT        | Unique complaint ID          |
| logged_by     | INTEGER | FK → users, NOT NULL     | CS staff who logged it       |
| outage_id     | INTEGER | FK → outages (nullable)  | Linked outage if known       |
| customer_name | TEXT    | NOT NULL                 | Customer name                |
| contact       | TEXT    |                          | Phone / email                |
| description   | TEXT    |                          | Complaint details            |
| logged_at     | TEXT    | DEFAULT current timestamp| When logged                  |
| status        | TEXT    | DEFAULT 'Open', CHECK(2) | Open / Resolved              |