"""
main.py — GridCare-Lite entry point.
Run:  python main.py
"""

import tkinter as tk
import database as db
from app import LoginWindow, GridCareApp


def main():
    conn = db.init_db()
    db.seed_data(conn)

    root = tk.Tk()
    root._conn = conn          # stash connection for LoginWindow

    def on_login(user):
        for w in root.winfo_children():
            w.destroy()
        GridCareApp(root, conn, user)

    LoginWindow(root, on_success=on_login)
    root.protocol("WM_DELETE_WINDOW", lambda: (conn.close(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()