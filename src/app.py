"""
app.py — GridCare-Lite
All Tkinter GUI screens: login, dashboards, forms, reports.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date

import database as db

# Optional matplotlib for charts
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ===================================================================
#  LOGIN
# ===================================================================

class LoginWindow(tk.Frame):
    def __init__(self, master, on_success):
        super().__init__(master)
        self.on_success = on_success
        master.title("GridCare-Lite — Login")
        master.geometry("380x220")
        master.resizable(False, False)

        ttk.Label(self, text="GridCare-Lite", font=("Helvetica", 16, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(15, 10)
        )
        ttk.Label(self, text="Username:").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        self.u_entry = ttk.Entry(self, width=22)
        self.u_entry.grid(row=1, column=1, padx=8, pady=4)

        ttk.Label(self, text="Password:").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        self.p_entry = ttk.Entry(self, show="*", width=22)
        self.p_entry.grid(row=2, column=1, padx=8, pady=4)
        self.p_entry.bind("<Return>", lambda e: self.attempt_login())

        ttk.Button(self, text="Log In", command=self.attempt_login).grid(
            row=3, column=0, columnspan=2, pady=14
        )
        self.pack(padx=20, pady=10)

    def attempt_login(self):
        user = db.authenticate(self.master._conn, self.u_entry.get(), self.p_entry.get())
        if user:
            self.on_success(user)
        else:
            messagebox.showerror("Login Failed", "Invalid username or password.")


# ===================================================================
#  MAIN APP SHELL (sidebar + content area)
# ===================================================================

class GridCareApp:
    """Post-login window with a sidebar and swappable content area."""
    
    NAV_ITEMS = {
        "admin":            ["Dashboard", "Outages", "Assign Work Order", "Complaints", "Reports", "Import CSV"],
        "engineer":         ["Dashboard", "Outages", "New Outage", "Reports"],
        "technician":       ["My Work Orders"],
        "customer_service": ["Log Complaint", "Outages", "Complaints"],
    }

    def __init__(self, root, conn, user):
        self.root = root
        self.conn = conn
        self.user = user
        root.title(f"GridCare-Lite — {user['full_name']}  [{user['role']}]")
        root.geometry("1050x650")
        root.minsize(800, 500)

        # --- top bar ---
        top = tk.Frame(root, bg="#2c3e50", height=38)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="  GridCare-Lite", bg="#2c3e50", fg="white",
                 font=("Helvetica", 12, "bold")).pack(side="left")
        tk.Label(top, text=f"Logged in as {user['full_name']} ({user['role']})  ",
                 bg="#2c3e50", fg="#bdc3c7").pack(side="right")
        ttk.Button(top, text="Logout", command=self._logout).pack(side="right", padx=6)

        # --- body ---
        body = tk.Frame(root)
        body.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(body, bg="#34495e", width=190)
        self.sidebar.pack(fill="y", side="left")
        self.sidebar.pack_propagate(False)

        self.content = tk.Frame(body)
        self.content.pack(fill="both", expand=True, side="left")

        self._build_sidebar()
        self.show_screen("Dashboard")

    # ---- sidebar ----
    def _build_sidebar(self):
        for w in self.sidebar.winfo_children():
            w.destroy()
        tk.Label(self.sidebar, text="  Navigation", bg="#34495e", fg="white",
                 font=("Helvetica", 10, "bold")).pack(anchor="w", pady=(12, 6))
        for item in self.NAV_ITEMS.get(self.user["role"], []):
            btn = tk.Button(self.sidebar, text=f"  {item}", anchor="w",
                            bg="#34495e", fg="white", relief="flat",
                            font=("Helvetica", 10),
                            command=lambda i=item: self.show_screen(i))
            btn.pack(fill="x", pady=1)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#2c3e50"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#34495e"))

    # ---- screen router ----
    def show_screen(self, name):
        for w in self.content.winfo_children():
            w.destroy()
        mapping = {
            "Dashboard":        DashboardFrame,
            "Outages":          OutageListFrame,
            "New Outage":       NewOutageFrame,
            "Assign Work Order": WorkOrderAssignFrame,
            "My Work Orders":   TechnicianFrame,
            "Log Complaint":    ComplaintFormFrame,
            "Complaints":       ComplaintListFrame,
            "Reports":          ReportsFrame,
            "Import CSV":       ImportCSVFrame,
        }
        cls = mapping.get(name, DashboardFrame)
        cls(self.content, self.conn, self.user)

    def _logout(self):
        for w in self.root.winfo_children():
            w.destroy()
        LoginWindow(self.root, on_success=lambda u: GridCareApp(self.root, self.conn, u))


# ===================================================================
#  DASHBOARD (role-aware summary)
# ===================================================================

class DashboardFrame(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn, self.user = conn, user
        self.pack(fill="both", expand=True, padx=15, pady=10)

        ttk.Label(self, text=f"Welcome, {user['full_name']}",
                  font=("Helvetica", 14, "bold")).pack(anchor="w")
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=8)

        stats = db.get_report_stats(conn)
        info = tk.Frame(self)
        info.pack(fill="x")
        for i, (label, val) in enumerate([
            ("Open Outages", stats["open_count"]),
            ("Resolved", stats["total_resolved"]),
            ("Avg Resolution (hrs)", stats["avg_resolution_hours"]),
        ]):
            card = tk.LabelFrame(info, text=label, padx=18, pady=10)
            card.grid(row=0, column=i, padx=8, pady=4, sticky="nsew")
            tk.Label(card, text=str(val), font=("Helvetica", 22, "bold")).pack()
        info.columnconfigure((0, 1, 2), weight=1)

        # Recent outages
        ttk.Label(self, text="Recent Outages", font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(14, 4))
        cols = ("id", "substation", "region", "severity", "status", "reported")
        tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (50, 140, 120, 70, 90, 150)):
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=w)
        tree.pack(fill="both", expand=True)
        for row in db.get_outages(conn)[:50]:
            tree.insert("", "end", values=(row[0], row[1], row[2], row[3], row[5], row[7]))


# ===================================================================
#  OUTAGE LIST (filterable)
# ===================================================================

class OutageListFrame(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn, self.user = conn, user
        self.pack(fill="both", expand=True, padx=15, pady=10)

        ttk.Label(self, text="All Outages", font=("Helvetica", 13, "bold")).pack(anchor="w")

        # Filters
        filt = tk.Frame(self)
        filt.pack(fill="x", pady=6)
        ttk.Label(filt, text="Status:").pack(side="left")
        self.status_var = tk.StringVar(value="All")
        ttk.Combobox(filt, textvariable=self.status_var,
                     values=["All", "Open", "In Progress", "Resolved"],
                     state="readonly", width=12).pack(side="left", padx=4)
        ttk.Label(filt, text="Region:").pack(side="left", padx=(12, 0))
        self.region_var = tk.StringVar(value="All")
        regions = ["All"] + db.get_regions(conn)
        ttk.Combobox(filt, textvariable=self.region_var,
                     values=regions, state="readonly", width=16).pack(side="left", padx=4)
        ttk.Button(filt, text="Filter", command=self.load).pack(side="left", padx=8)

        cols = ("id", "substation", "region", "severity", "desc", "status", "reported_by", "reported", "resolved")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
        self.tree.pack(fill="both", expand=True, pady=4)

        # Action buttons for engineers / admins
        btn_row = tk.Frame(self)
        btn_row.pack(fill="x")
        if user["role"] in ("admin", "engineer"):
            ttk.Button(btn_row, text="Mark Selected → In Progress", command=self._mark_in_progress).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Refresh", command=self.load).pack(side="right", padx=4)
        self.load()

    def load(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for row in db.get_outages(self.conn, self.status_var.get(), self.region_var.get()):
            self.tree.insert("", "end", values=row)

    def _mark_in_progress(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select an outage first.")
            return
        oid = self.tree.item(sel[0])["values"][0]
        db.update_outage_status(self.conn, oid, "In Progress")
        self.load()


# ===================================================================
#  NEW OUTAGE FORM (engineer)
# ===================================================================

class NewOutageFrame(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn, self.user = conn, user
        self.pack(fill="both", expand=True, padx=15, pady=10)

        ttk.Label(self, text="Report New Outage", font=("Helvetica", 13, "bold")).pack(anchor="w")
        form = ttk.LabelFrame(self, text="Details", padding=12)
        form.pack(fill="x", pady=10)

        # Substation
        ttk.Label(form, text="Substation:").grid(row=0, column=0, sticky="e", pady=4)
        self.subs = db.get_all_substations(conn)
        self.sub_var = tk.StringVar()
        sub_names = [f"{s[0]} — {s[1]} ({s[2]})" for s in self.subs]
        ttk.Combobox(form, textvariable=self.sub_var, values=sub_names,
                     state="readonly", width=36).grid(row=0, column=1, padx=6, pady=4)

        # Severity
        ttk.Label(form, text="Severity:").grid(row=1, column=0, sticky="e", pady=4)
        self.sev_var = tk.StringVar(value="Medium")
        ttk.Combobox(form, textvariable=self.sev_var,
                     values=["Low", "Medium", "High", "Critical"],
                     state="readonly", width=12).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        # Description
        ttk.Label(form, text="Description:").grid(row=2, column=0, sticky="ne", pady=4)
        self.desc = tk.Text(form, width=40, height=4)
        self.desc.grid(row=2, column=1, padx=6, pady=4)

        ttk.Button(form, text="Submit Outage", command=self.submit).grid(
            row=3, column=0, columnspan=2, pady=10
        )

    def submit(self):
        raw = self.sub_var.get()
        if not raw:
            messagebox.showwarning("Missing", "Select a substation.")
            return
        sub_id = int(raw.split(" — ")[0])
        desc = self.desc.get("1.0", "end").strip()
        if not desc:
            messagebox.showwarning("Missing", "Enter a description.")
            return
        oid = db.create_outage(self.conn, sub_id, self.user["user_id"], desc, self.sev_var.get())
        messagebox.showinfo("Success", f"Outage #{oid} logged successfully.")
        self.desc.delete("1.0", "end")
        self.sub_var.set("")


# ===================================================================
#  WORK ORDER ASSIGNMENT (admin)
# ===================================================================

class WorkOrderAssignFrame(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn, self.user = conn, user
        self.pack(fill="both", expand=True, padx=15, pady=10)

        ttk.Label(self, text="Assign Work Order", font=("Helvetica", 13, "bold")).pack(anchor="w")

        form = ttk.LabelFrame(self, text="New Work Order", padding=12)
        form.pack(fill="x", pady=8)

        # Open outage picker
        ttk.Label(form, text="Outage:").grid(row=0, column=0, sticky="e", pady=4)
        self.open_outages = db.get_open_outages(conn)
        outage_labels = [f"#{o[0]} — Stn {o[1]}: {o[2][:40]}  [{o[3]}]" for o in self.open_outages]
        self.outage_var = tk.StringVar()
        ttk.Combobox(form, textvariable=self.outage_var, values=outage_labels,
                     state="readonly", width=52).grid(row=0, column=1, padx=6, pady=4)

        # Technician picker
        ttk.Label(form, text="Technician:").grid(row=1, column=0, sticky="e", pady=4)
        self.techs = db.get_technicians(conn)
        tech_labels = [f"{t[0]} — {t[1]}" for t in self.techs]
        self.tech_var = tk.StringVar()
        ttk.Combobox(form, textvariable=self.tech_var, values=tech_labels,
                     state="readonly", width=30).grid(row=1, column=1, sticky="w", padx=6, pady=4)

        # Scheduled date
        ttk.Label(form, text="Scheduled Date:").grid(row=2, column=0, sticky="e", pady=4)
        self.date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(form, textvariable=self.date_var, width=14).grid(row=2, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(form, text="(YYYY-MM-DD)").grid(row=2, column=1, sticky="e", padx=6)

        ttk.Button(form, text="Create Work Order", command=self.submit).grid(
            row=3, column=0, columnspan=2, pady=10
        )

        # Existing work orders
        ttk.Label(self, text="Existing Work Orders", font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(10, 4))
        cols = ("wo_id", "outage_id", "substation", "technician", "scheduled", "status")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
        self.tree.pack(fill="both", expand=True)
        self.load()

    def submit(self):
        if not self.outage_var.get() or not self.tech_var.get():
            messagebox.showwarning("Missing", "Select an outage and a technician.")
            return
        oid = int(self.outage_var.get().split(" — ")[0].replace("#", ""))
        tid = int(self.tech_var.get().split(" — ")[0])
        db.create_work_order(self.conn, oid, tid, self.date_var.get())
        messagebox.showinfo("Success", "Work order created.")
        self.load()

    def load(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for row in db.get_all_work_orders(self.conn):
            self.tree.insert("", "end", values=row)


# ===================================================================
#  TECHNICIAN VIEW
# ===================================================================

class TechnicianFrame(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn, self.user = conn, user
        self.pack(fill="both", expand=True, padx=15, pady=10)

        ttk.Label(self, text="My Assigned Work Orders",
                  font=("Helvetica", 13, "bold")).pack(anchor="w")

        cols = ("wo_id", "outage_id", "substation", "desc", "scheduled", "status", "severity")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
        self.tree.pack(fill="both", expand=True, pady=8)

        btns = tk.Frame(self)
        btns.pack(fill="x")
        ttk.Button(btns, text="Mark Selected → Completed", command=self._complete).pack(side="left", padx=4)
        ttk.Button(btns, text="Refresh", command=self.load).pack(side="right", padx=4)
        self.load()

    def load(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for row in db.get_work_orders_for_technician(self.conn, self.user["user_id"]):
            self.tree.insert("", "end", values=row)

    def _complete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a work order first.")
            return
        wo_id = self.tree.item(sel[0])["values"][0]
        status = self.tree.item(sel[0])["values"][5]
        if status == "Completed":
            messagebox.showinfo("Info", "Already completed.")
            return
        db.complete_work_order(self.conn, wo_id)
        messagebox.showinfo("Done", f"Work order #{wo_id} completed. Linked outage marked Resolved.")
        self.load()


# ===================================================================
#  COMPLAINT FORM (customer_service)
# ===================================================================

class ComplaintFormFrame(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn, self.user = conn, user
        self.pack(fill="both", expand=True, padx=15, pady=10)

        ttk.Label(self, text="Log Customer Complaint",
                  font=("Helvetica", 13, "bold")).pack(anchor="w")
        form = ttk.LabelFrame(self, text="Complaint Details", padding=12)
        form.pack(fill="x", pady=10)

        ttk.Label(form, text="Customer Name:").grid(row=0, column=0, sticky="e", pady=4)
        self.name_entry = ttk.Entry(form, width=30)
        self.name_entry.grid(row=0, column=1, padx=6, pady=4)

        ttk.Label(form, text="Contact:").grid(row=1, column=0, sticky="e", pady=4)
        self.contact_entry = ttk.Entry(form, width=30)
        self.contact_entry.grid(row=1, column=1, padx=6, pady=4)

        ttk.Label(form, text="Link to Outage:").grid(row=2, column=0, sticky="e", pady=4)
        self.open_outages = db.get_open_outages(conn)
        opts = ["(none)"] + [f"#{o[0]} — Stn {o[1]}: {o[2][:35]}" for o in self.open_outages]
        self.outage_var = tk.StringVar(value="(none)")
        ttk.Combobox(form, textvariable=self.outage_var, values=opts,
                     state="readonly", width=42).grid(row=2, column=1, padx=6, pady=4)

        ttk.Label(form, text="Description:").grid(row=3, column=0, sticky="ne", pady=4)
        self.desc = tk.Text(form, width=40, height=4)
        self.desc.grid(row=3, column=1, padx=6, pady=4)

        ttk.Button(form, text="Submit Complaint", command=self.submit).grid(
            row=4, column=0, columnspan=2, pady=10
        )

    def submit(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Enter customer name.")
            return
        outage_id = None
        raw = self.outage_var.get()
        if raw != "(none)":
            outage_id = int(raw.split(" — ")[0].replace("#", ""))
        desc = self.desc.get("1.0", "end").strip()
        db.create_complaint(self.conn, self.user["user_id"], outage_id,
                            name, self.contact_entry.get().strip(), desc)
        messagebox.showinfo("Success", "Complaint logged.")
        self.name_entry.delete(0, "end")
        self.contact_entry.delete(0, "end")
        self.desc.delete("1.0", "end")
        self.outage_var.set("(none)")


# ===================================================================
#  COMPLAINT LIST
# ===================================================================

class ComplaintListFrame(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn, self.user = conn, user
        self.pack(fill="both", expand=True, padx=15, pady=10)

        ttk.Label(self, text="All Complaints", font=("Helvetica", 13, "bold")).pack(anchor="w")
        cols = ("id", "customer", "contact", "desc", "outage_id", "status", "logged", "logged_by")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
        self.tree.pack(fill="both", expand=True, pady=6)
        ttk.Button(self, text="Refresh", command=self.load).pack(anchor="e")
        self.load()

    def load(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for row in db.get_all_complaints(self.conn):
            self.tree.insert("", "end", values=row)


# ===================================================================
#  REPORTS
# ===================================================================

class ReportsFrame(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn, self.user = conn, user
        self.pack(fill="both", expand=True, padx=15, pady=10)

        ttk.Label(self, text="Reports", font=("Helvetica", 13, "bold")).pack(anchor="w")
        stats = db.get_report_stats(conn)

        info = tk.Frame(self)
        info.pack(fill="x", pady=6)
        for i, (lbl, val) in enumerate([
            ("Open Outages", stats["open_count"]),
            ("Resolved", stats["total_resolved"]),
            ("Avg Resolution (hrs)", stats["avg_resolution_hours"]),
        ]):
            card = tk.LabelFrame(info, text=lbl, padx=16, pady=8)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            tk.Label(card, text=str(val), font=("Helvetica", 20, "bold")).pack()
        info.columnconfigure((0, 1, 2), weight=1)

        # Chart or text fallback
        if HAS_MPL and stats["by_region"]:
            fig = Figure(figsize=(7, 3.5), dpi=90)
            ax = fig.add_subplot(111)
            regions = [r[0] for r in stats["by_region"]]
            counts  = [r[1] for r in stats["by_region"]]
            ax.bar(regions, counts, color="#3498db")
            ax.set_ylabel("Outages")
            ax.set_title("Outages by Region")
            fig.autofmt_xdate(rotation=30)
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, pady=8)
        else:
            ttk.Label(self, text="Outages by Region:").pack(anchor="w", pady=(10, 2))
            for region, count in stats["by_region"]:
                ttk.Label(self, text=f"  {region}: {count}").pack(anchor="w")
            if not HAS_MPL:
                ttk.Label(self, text="(Install matplotlib for charts)",
                          foreground="gray").pack(anchor="w", pady=4)


# ===================================================================
#  IMPORT CSV (admin)
# ===================================================================

class ImportCSVFrame(tk.Frame):
    def __init__(self, master, conn, user):
        super().__init__(master)
        self.conn, self.user = conn, user
        self.pack(fill="both", expand=True, padx=15, pady=10)

        ttk.Label(self, text="Import CSV Data", font=("Helvetica", 13, "bold")).pack(anchor="w")
        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=8)

        for label, fn in [("Substations CSV", self._import_subs), ("Lines CSV", self._import_lines)]:
            row = tk.Frame(self)
            row.pack(fill="x", pady=6)
            ttk.Button(row, text=f"Import {label}", command=fn).pack(side="left")
            self.lbl = ttk.Label(row, text="")
            self.lbl.pack(side="left", padx=10)

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=12)
        ttk.Label(self, text="Expected columns:\n"
                  "  substations.csv → substation_id, name, region\n"
                  "  lines.csv       → line_id, name, voltage, region, substation_id",
                  foreground="gray").pack(anchor="w")

    def _import_subs(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = db.import_substations_csv(self.conn, path)
            messagebox.showinfo("Done", f"Imported {n} substations.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _import_lines(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = db.import_lines_csv(self.conn, path)
            messagebox.showinfo("Done", f"Imported {n} lines.")
        except Exception as e:
            messagebox.showerror("Error", str(e))