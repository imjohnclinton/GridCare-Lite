import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
 
from db import init_db
 
class LoginWindow(tk.Frame):
    def __init__(self, master, on_success):
        super().__init__(master)
        self.on_success = on_success
        self.master = master
        master.title('GridCare-Lite — Login')
 
        ttk.Label(self, text='Username:').grid(row=0, column=0, padx=8, pady=8, sticky='e')
        self.username_entry = ttk.Entry(self)
        self.username_entry.grid(row=0, column=1, padx=8, pady=8)
 
        ttk.Label(self, text='Password:').grid(row=1, column=0, padx=8, pady=8, sticky='e')
        self.password_entry = ttk.Entry(self, show='*')
        self.password_entry.grid(row=1, column=1, padx=8, pady=8)
 
        ttk.Button(self, text='Log In', command=self.attempt_login).grid(row=2, column=0, columnspan=2, pady=10)
        self.pack(padx=20, pady=20)
 
    def attempt_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        if not username or not password:
            messagebox.showerror('Login Failed', 'Please enter both a username and password.')
            return
        # TODO: replace with a real password check against the users table
        self.on_success(username)
 
class OutageDashboard(tk.Frame):
    def __init__(self, master, conn, username):
        super().__init__(master)
        self.conn = conn
        master.title(f'GridCare-Lite — Outage Dashboard ({username})')
 
        columns = ('outage_id', 'substation_id', 'description', 'status', 'reported_at')
        self.tree = ttk.Treeview(self, columns=columns, show='headings')
        for col in columns:
            self.tree.heading(col, text=col.replace('_', ' ').title())
        self.tree.pack(fill='both', expand=True, padx=10, pady=10)
 
        ttk.Button(self, text='Refresh', command=self.load_outages).pack(pady=5)
        self.pack(fill='both', expand=True)
        self.load_outages()
 
    def load_outages(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        cur = self.conn.cursor()
        cur.execute('SELECT outage_id, substation_id, description, status, reported_at FROM outages')
        for row in cur.fetchall():
            self.tree.insert('', 'end', values=row)
 
def main():
    conn = init_db()
    root = tk.Tk()
 
    def show_dashboard(username):
        for widget in root.winfo_children():
            widget.destroy()
        OutageDashboard(root, conn, username)
 
    LoginWindow(root, on_success=show_dashboard)
    root.mainloop()
 
if __name__ == '__main__':
    main()
