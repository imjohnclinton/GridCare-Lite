import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
 
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
 
import db
import auth
from db import GridCareError
 
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gridcare.db')
SUBSTATIONS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'substations.csv')
 
DEMO_USERS = [
    ('admin', 'Password1!', 'Ama Admin', 'admin'),
    ('engineer', 'Password1!', 'Kofi Engineer', 'engineer'),
    ('technician', 'Password1!', 'Yaw Technician', 'technician'),
    ('customerservice', 'Password1!', 'Efua Service', 'customer_service'),
]
 
 
def seed_demo_users(conn):
    for username, password, name, role in DEMO_USERS:
        existing = conn.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone()
        if not existing:
            try:
                auth.register_user(conn, username, password, name, role)
            except GridCareError:
                pass
 
 
# ---------------------------------------------------------------------------
# Login screen
# ---------------------------------------------------------------------------
class LoginScreen(tk.Frame):
    def __init__(self, master, conn, on_login_success):
        super().__init__(master)
        self.conn = conn
        self.on_login_success = on_login_success
        master.title('GridCare-Lite — Login')
 
        ttk.Label(self, text='GridCare-Lite', font=('Segoe UI', 16, 'bold')).grid(
            row=0, column=0, columnspan=2, pady=(0, 15))
        ttk.Label(self, text='Username:').grid(row=1, column=0, padx=8, pady=8, sticky='e')
        self.username_entry = ttk.Entry(self)
        self.username_entry.grid(row=1, column=1, padx=8, pady=8)
 
        ttk.Label(self, text='Password:').grid(row=2, column=0, padx=8, pady=8, sticky='e')
        self.password_entry = ttk.Entry(self, show='*')
        self.password_entry.grid(row=2, column=1, padx=8, pady=8)
        self.password_entry.bind('<Return>', lambda e: self.attempt_login())
 
        ttk.Button(self, text='Log In', command=self.attempt_login).grid(
            row=3, column=0, columnspan=2, pady=10)
        ttk.Label(self, text='Demo accounts: admin / engineer / technician / customerservice\n'
                              'Password: Password1!', foreground='gray', justify='center').grid(
            row=4, column=0, columnspan=2, pady=(10, 0))
        self.pack(padx=30, pady=30)
 
    def attempt_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        try:
            user = auth.authenticate(self.conn, username, password)
        except GridCareError as e:
            messagebox.showerror('Login Failed', str(e))
            return
        self.on_login_success(user)
 
 
# ---------------------------------------------------------------------------
# Shared dashboard shell — builds role-appropriate tabs
# ---------------------------------------------------------------------------
class Dashboard(tk.Frame):
    def __init__(self, master, conn, user, on_logout):
        super().__init__(master)
        self.conn = conn
        self.user = user
        self.on_logout = on_logout
        master.title(f"GridCare-Lite — {user['full_name']} ({user['role']})")
 
        top = ttk.Frame(self)
        top.pack(fill='x', padx=10, pady=5)
        ttk.Label(top, text=f"Logged in as {user['full_name']} — {user['role']}",
                  font=('Segoe UI', 10, 'bold')).pack(side='left')
        ttk.Button(top, text='Log Out', command=self.logout).pack(side='right')
 
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        self._build_tabs()
        self.pack(fill='both', expand=True)
 
    def logout(self):
        self.destroy()
        self.on_logout()
 
    def _build_tabs(self):
        role = self.user['role']
 
        overview = OverviewTab(self.notebook, self.conn)
        self.notebook.add(overview, text='Overview')
 
        if role in ('engineer', 'admin'):
            new_outage = NewOutageTab(self.notebook, self.conn, self.user)
            self.notebook.add(new_outage, text='Report Outage')
 
        outages_tab = OutagesTab(self.notebook, self.conn, self.user)
        self.notebook.add(outages_tab, text='Outages')
 
        if role == 'admin':
            work_orders_tab = WorkOrderAssignmentTab(self.notebook, self.conn)
            self.notebook.add(work_orders_tab, text='Assign Work Orders')
 
        if role == 'technician':
            tech_tab = TechnicianTab(self.notebook, self.conn, self.user)
            self.notebook.add(tech_tab, text='My Work Orders')
 
        if role == 'customer_service':
            complaints_tab = ComplaintsTab(self.notebook, self.conn, self.user)
            self.notebook.add(complaints_tab, text='Complaints')
 
        if role == 'admin':
            all_complaints_tab = ComplaintsViewTab(self.notebook, self.conn)
            self.notebook.add(all_complaints_tab, text='All Complaints')
 
 
# ---------------------------------------------------------------------------
# Overview / reporting tab
# ---------------------------------------------------------------------------
class OverviewTab(tk.Frame):
    SEVERITY_COLORS = {'Low': '#8ecae6', 'Medium': '#ffb703', 'High': '#fb8500', 'Critical': '#d00000'}
 
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self.canvas_widget = None  # tracks the embedded chart canvas so refresh() can replace it
 
        top = ttk.Frame(self)
        top.pack(fill='x', padx=10, pady=(10, 0))
        self.stats_frame = ttk.Frame(top)
        self.stats_frame.pack(anchor='w')
        ttk.Button(self, text='Refresh', command=self.refresh).pack(anchor='w', padx=10, pady=5)
 
        self.chart_container = ttk.Frame(self)
        self.chart_container.pack(fill='both', expand=True, padx=10, pady=10)
 
        self.refresh()
 
    def refresh(self):
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        stats = db.get_dashboard_stats(self.conn)
        rows = [
            ('Open / In-Progress Outages', stats['open_outages']),
            ('Resolved Outages', stats['resolved_outages']),
            ('Pending Work Orders', stats['pending_work_orders']),
            ('Total Complaints', stats['total_complaints']),
            ('Avg Resolution Time (days)', stats['avg_resolution_days'] or '—'),
        ]
        for i, (label, value) in enumerate(rows):
            ttk.Label(self.stats_frame, text=label + ':').grid(row=0, column=2 * i, sticky='e', padx=5, pady=3)
            ttk.Label(self.stats_frame, text=str(value), font=('Segoe UI', 10, 'bold')).grid(
                row=0, column=2 * i + 1, sticky='w', padx=(0, 15), pady=3)
 
        self._draw_charts(stats)
 
    def _draw_charts(self, stats):
        if self.canvas_widget is not None:
            self.canvas_widget.get_tk_widget().destroy()
 
        fig, (ax_region, ax_severity) = plt.subplots(1, 2, figsize=(9, 3.5))
 
        regions = [r['region'] for r in stats['outages_by_region']]
        counts = [r['c'] for r in stats['outages_by_region']]
        if regions:
            ax_region.bar(regions, counts, color='#219ebc')
            ax_region.set_title('Outages by Region')
            ax_region.tick_params(axis='x', rotation=45, labelsize=7)
        else:
            ax_region.text(0.5, 0.5, 'No outages logged yet', ha='center', va='center')
            ax_region.set_title('Outages by Region')
            ax_region.set_xticks([])
            ax_region.set_yticks([])
 
        sev_rows = {r['severity']: r['c'] for r in stats['outages_by_severity']}
        severities = list(db.SEVERITIES)
        sev_counts = [sev_rows.get(s, 0) for s in severities]
        if sum(sev_counts) > 0:
            colors = [self.SEVERITY_COLORS[s] for s in severities]
            ax_severity.bar(severities, sev_counts, color=colors)
            ax_severity.set_title('Outages by Severity')
        else:
            ax_severity.text(0.5, 0.5, 'No outages logged yet', ha='center', va='center')
            ax_severity.set_title('Outages by Severity')
            ax_severity.set_xticks([])
            ax_severity.set_yticks([])
 
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.chart_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
        self.canvas_widget = canvas
        plt.close(fig)  # the canvas holds its own reference; release matplotlib's global figure registry
 
 
# ---------------------------------------------------------------------------
# Report a new outage (engineer / admin)
# ---------------------------------------------------------------------------
class NewOutageTab(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn = conn
        self.user = user
 
        ttk.Label(self, text='Substation ID:').grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.sub_id_entry = ttk.Entry(self)
        self.sub_id_entry.grid(row=0, column=1, padx=5, pady=5)
 
        ttk.Label(self, text='Description:').grid(row=1, column=0, sticky='ne', padx=5, pady=5)
        self.desc_text = tk.Text(self, width=40, height=4)
        self.desc_text.grid(row=1, column=1, padx=5, pady=5)
 
        ttk.Label(self, text='Severity:').grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.severity_combo = ttk.Combobox(self, values=list(db.SEVERITIES), state='readonly')
        self.severity_combo.set('Medium')
        self.severity_combo.grid(row=2, column=1, sticky='w', padx=5, pady=5)
 
        ttk.Button(self, text='Log Outage', command=self.submit).grid(row=3, column=0, columnspan=2, pady=10)
        self.status_label = ttk.Label(self, text='', foreground='green')
        self.status_label.grid(row=4, column=0, columnspan=2)
 
    def submit(self):
        try:
            sub_id = int(self.sub_id_entry.get())
        except ValueError:
            messagebox.showerror('Invalid Input', 'Substation ID must be a number.')
            return
        description = self.desc_text.get('1.0', 'end').strip()
        severity = self.severity_combo.get()
        try:
            outage_id = db.create_outage(self.conn, sub_id, self.user['user_id'], description, severity)
        except GridCareError as e:
            messagebox.showerror('Could Not Log Outage', str(e))
            return
        self.status_label.config(text=f'Outage #{outage_id} logged successfully.')
        self.sub_id_entry.delete(0, 'end')
        self.desc_text.delete('1.0', 'end')
 
 
# ---------------------------------------------------------------------------
# Outage list / status view (all roles)
# ---------------------------------------------------------------------------
class OutagesTab(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn = conn
        self.user = user
 
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(filter_frame, text='Filter by status:').pack(side='left')
        self.status_filter = ttk.Combobox(
            filter_frame, values=['All'] + list(db.OUTAGE_STATUSES), state='readonly')
        self.status_filter.set('All')
        self.status_filter.pack(side='left', padx=5)
        ttk.Button(filter_frame, text='Refresh', command=self.refresh).pack(side='left', padx=5)
 
        columns = ('outage_id', 'substation_name', 'region', 'severity', 'status', 'reported_at')
        self.tree = ttk.Treeview(self, columns=columns, show='headings', height=12)
        for col in columns:
            self.tree.heading(col, text=col.replace('_', ' ').title())
            self.tree.column(col, width=120)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)
 
        if user['role'] in ('admin', 'technician'):
            action_frame = ttk.Frame(self)
            action_frame.pack(fill='x', padx=5, pady=5)
            ttk.Label(action_frame, text='Set status of selected outage:').pack(side='left')
            self.new_status = ttk.Combobox(action_frame, values=list(db.OUTAGE_STATUSES), state='readonly')
            self.new_status.pack(side='left', padx=5)
            ttk.Button(action_frame, text='Update', command=self.update_status).pack(side='left')
 
        self.refresh()
 
    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        status = None if self.status_filter.get() == 'All' else self.status_filter.get()
        for o in db.list_outages(self.conn, status=status):
            self.tree.insert('', 'end', iid=o['outage_id'], values=(
                o['outage_id'], o['substation_name'], o['region'], o['severity'],
                o['status'], o['reported_at']))
 
    def update_status(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning('No Selection', 'Select an outage first.')
            return
        outage_id = int(selected[0])
        new_status = self.new_status.get()
        if not new_status:
            messagebox.showwarning('No Status', 'Choose a new status first.')
            return
        try:
            db.update_outage_status(self.conn, outage_id, new_status, self.user['user_id'])
        except GridCareError as e:
            messagebox.showerror('Update Failed', str(e))
            return
        self.refresh()
 
 
# ---------------------------------------------------------------------------
# Work order assignment (admin)
# ---------------------------------------------------------------------------
class WorkOrderAssignmentTab(tk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self.admin_user_id = None  # set by caller context if needed
 
        ttk.Label(self, text='Outage ID:').grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.outage_id_entry = ttk.Entry(self)
        self.outage_id_entry.grid(row=0, column=1, padx=5, pady=5)
 
        ttk.Label(self, text='Technician username:').grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.tech_username_entry = ttk.Entry(self)
        self.tech_username_entry.grid(row=1, column=1, padx=5, pady=5)
 
        ttk.Label(self, text='Scheduled date (YYYY-MM-DD):').grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.date_entry = ttk.Entry(self)
        self.date_entry.grid(row=2, column=1, padx=5, pady=5)
 
        ttk.Button(self, text='Create Work Order', command=self.submit).grid(
            row=3, column=0, columnspan=2, pady=10)
        self.status_label = ttk.Label(self, text='', foreground='green')
        self.status_label.grid(row=4, column=0, columnspan=2)
 
    def submit(self):
        try:
            outage_id = int(self.outage_id_entry.get())
        except ValueError:
            messagebox.showerror('Invalid Input', 'Outage ID must be a number.')
            return
        tech_row = self.conn.execute(
            "SELECT user_id FROM users WHERE username=? AND role='technician'",
            (self.tech_username_entry.get().strip(),)).fetchone()
        if tech_row is None:
            messagebox.showerror('Invalid Technician', 'No technician with that username.')
            return
        current_admin = self.conn.execute(
            "SELECT user_id FROM users WHERE role='admin' LIMIT 1").fetchone()
        try:
            wo_id = db.create_work_order(
                self.conn, outage_id, tech_row['user_id'], current_admin['user_id'],
                self.date_entry.get().strip() or None)
        except GridCareError as e:
            messagebox.showerror('Could Not Assign', str(e))
            return
        self.status_label.config(text=f'Work order #{wo_id} created and assigned.')
 
 
# ---------------------------------------------------------------------------
# Technician's own work orders
# ---------------------------------------------------------------------------
class TechnicianTab(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn = conn
        self.user = user
 
        columns = ('work_order_id', 'outage_id', 'substation_name', 'severity', 'status', 'scheduled_date')
        self.tree = ttk.Treeview(self, columns=columns, show='headings', height=10)
        for col in columns:
            self.tree.heading(col, text=col.replace('_', ' ').title())
            self.tree.column(col, width=120)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)
 
        action_frame = ttk.Frame(self)
        action_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(action_frame, text='Set status:').pack(side='left')
        self.status_combo = ttk.Combobox(action_frame, values=list(db.WORK_ORDER_STATUSES), state='readonly')
        self.status_combo.pack(side='left', padx=5)
        ttk.Label(action_frame, text='Notes:').pack(side='left', padx=(10, 0))
        self.notes_entry = ttk.Entry(action_frame, width=30)
        self.notes_entry.pack(side='left', padx=5)
        ttk.Button(action_frame, text='Update', command=self.update_status).pack(side='left')
        ttk.Button(self, text='Refresh', command=self.refresh).pack(anchor='w', padx=5)
 
        self.refresh()
 
    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for w in db.list_work_orders_for_technician(self.conn, self.user['user_id']):
            self.tree.insert('', 'end', iid=w['work_order_id'], values=(
                w['work_order_id'], w['outage_id'], w['substation_name'], w['severity'],
                w['status'], w['scheduled_date']))
 
    def update_status(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning('No Selection', 'Select a work order first.')
            return
        wo_id = int(selected[0])
        new_status = self.status_combo.get()
        if not new_status:
            messagebox.showwarning('No Status', 'Choose a new status first.')
            return
        try:
            db.update_work_order_status(
                self.conn, wo_id, new_status, self.user['user_id'],
                work_notes=self.notes_entry.get().strip() or None)
        except GridCareError as e:
            messagebox.showerror('Update Failed', str(e))
            return
        self.refresh()
 
 
# ---------------------------------------------------------------------------
# Complaint logging (customer service)
# ---------------------------------------------------------------------------
class ComplaintsTab(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn = conn
        self.user = user
 
        ttk.Label(self, text='Customer name:').grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.name_entry = ttk.Entry(self)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)
 
        ttk.Label(self, text='Related outage ID (optional):').grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.outage_id_entry = ttk.Entry(self)
        self.outage_id_entry.grid(row=1, column=1, padx=5, pady=5)
 
        ttk.Label(self, text='Details:').grid(row=2, column=0, sticky='ne', padx=5, pady=5)
        self.details_text = tk.Text(self, width=40, height=4)
        self.details_text.grid(row=2, column=1, padx=5, pady=5)
 
        ttk.Button(self, text='Log Complaint', command=self.submit).grid(row=3, column=0, columnspan=2, pady=10)
        self.status_label = ttk.Label(self, text='', foreground='green')
        self.status_label.grid(row=4, column=0, columnspan=2)
 
    def submit(self):
        outage_id = None
        raw = self.outage_id_entry.get().strip()
        if raw:
            try:
                outage_id = int(raw)
            except ValueError:
                messagebox.showerror('Invalid Input', 'Outage ID must be a number.')
                return
        try:
            complaint_id = db.log_complaint(
                self.conn, self.user['user_id'], self.name_entry.get(),
                self.details_text.get('1.0', 'end'), outage_id=outage_id)
        except GridCareError as e:
            messagebox.showerror('Could Not Log Complaint', str(e))
            return
        self.status_label.config(text=f'Complaint #{complaint_id} logged.')
        self.name_entry.delete(0, 'end')
        self.details_text.delete('1.0', 'end')
 
 
class ComplaintsViewTab(tk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        columns = ('complaint_id', 'customer_name', 'details', 'outage_id', 'outage_status', 'logged_at')
        self.tree = ttk.Treeview(self, columns=columns, show='headings', height=12)
        for col in columns:
            self.tree.heading(col, text=col.replace('_', ' ').title())
            self.tree.column(col, width=120)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)
        ttk.Button(self, text='Refresh', command=self.refresh).pack(anchor='w', padx=5)
        self.refresh()
 
    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for c in db.list_complaints(self.conn):
            self.tree.insert('', 'end', iid=c['complaint_id'], values=(
                c['complaint_id'], c['customer_name'], c['details'], c['outage_id'],
                c['outage_status'] or '—', c['logged_at']))
 
 
# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------
def main():
    conn = db.init_db(DB_PATH)
    seed_demo_users(conn)
    if os.path.exists(SUBSTATIONS_CSV) and conn.execute('SELECT COUNT(*) c FROM substations').fetchone()['c'] == 0:
        imported, skipped = db.import_substations_from_csv(conn, SUBSTATIONS_CSV)
        print(f'Imported {imported} substations ({skipped} skipped).')
 
    root = tk.Tk()
    root.geometry('800x600')
 
    def show_login():
        for widget in root.winfo_children():
            widget.destroy()
        LoginScreen(root, conn, show_dashboard)
 
    def show_dashboard(user):
        for widget in root.winfo_children():
            widget.destroy()
        Dashboard(root, conn, user, show_login)
 
    show_login()
    root.mainloop()
 
 
if __name__ == '__main__':
    main()
 