# GridCare-Lite — User Guide

## Default Login Credentials

| Username  | Password | Role             | Full Name    |
|-----------|----------|------------------|--------------|
| admin     | admin123 | Administrator    | Admin User   |
| engineer1 | pass123  | Engineer         | Kwame Asante |
| tech1     | pass123  | Technician       | Ama Serwaa   |
| cs1       | pass123  | Customer Service | Esi Mensah   |

---

## Administrator
1. Log in as `admin`.
2. **Dashboard** — view open/resolved counts and recent outages.
3. **Outages** — filter by status or region; mark outages "In Progress".
4. **Assign Work Order** — pick an open outage, choose a technician, set a date, click Create.
5. **Complaints** — view all logged complaints.
6. **Reports** — see statistics and a bar chart of outages by region.
7. **Import CSV** — load `substations.csv` or `lines.csv` from the data-science team.

## Engineer
1. Log in as `engineer1`.
2. **Dashboard** — overview of system status.
3. **Outages** — browse and filter all outages; mark as "In Progress".
4. **New Outage** — select a substation, set severity, describe the fault, submit.
5. **Reports** — view statistics and regional chart.

## Technician
1. Log in as `tech1`.
2. **My Work Orders** — see only your assigned work orders.
3. Select a work order and click **Mark Selected → Completed**.
   This automatically sets the linked outage to **Resolved** and records the resolution timestamp.

## Customer Service
1. Log in as `cs1`.
2. **Log Complaint** — enter customer name, contact, description; optionally link to a known outage.
3. **Outages** — view all outages (read-only).
4. **Complaints** — view all complaints logged by the team.