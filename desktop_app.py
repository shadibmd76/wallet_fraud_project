"""Mobile Wallet Fraud Detection - Desktop Application (Tkinter, kono pip package lage na)
Chalanor niyom:  python desktop_app.py
"""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import services as sv
from database import init_db
FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
FONT_H = ("Segoe UI", 16, "bold")
FONT_BIG = ("Segoe UI", 26, "bold")
BLUE, LIGHT = "#1f4e8c", "#eaf2fb"
TX_COLUMNS = [("id", "ID", 50), ("date", "Date", 140), ("type", "Type", 70),
              ("sender", "Sender", 90), ("receiver", "Receiver", 90),
              ("amount", "Amount (Tk)", 100), ("device", "Device", 90),
              ("status", "Status", 100), ("score", "Score", 55), ("level", "Risk", 70)]

def money(x):
    return f"{x:,.2f}"

def parse_amount(text):
    try:
        return float(text.replace(",", "").strip())
    except ValueError:
        return 0.0
def make_tree(parent, columns, height=12):
    """columns: [(key, heading, width)] -> (tree, frame with scrollbar)"""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height)
    for key, head, width in columns:
        tree.heading(key, text=head)
        tree.column(key, width=width, anchor="w")
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    tree.tag_configure("HIGH", background="#fde2e2")
    tree.tag_configure("MEDIUM", background="#fff3cd")
    tree.tag_configure("FRAUD", background="#f8b4b4")
    return tree, frame
def fill_tx_tree(tree, rows):
    tree.delete(*tree.get_children())
    for t in rows:
        tag = "FRAUD" if t["status"] == "FRAUD" else t["risk_level"]
        tree.insert("", "end", tags=(tag,), values=(
            t["id"], t["created_at"], t["type"], t["sender"] or "-", t["receiver"] or "-",
            money(t["amount"]), t["device"] or "-", t["status"], t["risk_score"], t["risk_level"]))

# ---------------------------------------------------------------- Login / Register
class LoginFrame(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.container)
        self.app = app
        card = ttk.Frame(self, padding=30, relief="ridge")
        card.place(relx=0.5, rely=0.45, anchor="center")

        ttk.Label(card, text="Mobile Wallet", font=FONT_H, foreground=BLUE).grid(columnspan=2, pady=(0, 2))
        ttk.Label(card, text="Fraud Detection System", font=FONT).grid(columnspan=2, pady=(0, 18))

        ttk.Label(card, text="Username").grid(row=2, column=0, sticky="w", pady=4)
        self.user = ttk.Entry(card, width=26)
        self.user.grid(row=2, column=1, pady=4)
        ttk.Label(card, text="Password").grid(row=3, column=0, sticky="w", pady=4)
        self.pw = ttk.Entry(card, width=26, show="*")
        self.pw.grid(row=3, column=1, pady=4)

        ttk.Button(card, text="Login", command=self.login).grid(row=4, columnspan=2, sticky="ew", pady=(14, 4))
        ttk.Button(card, text="New account (Register)", command=lambda: RegisterWindow(app)
                   ).grid(row=5, columnspan=2, sticky="ew")
        self.user.focus()
        app.bind("<Return>", lambda e: self.login())

    def login(self):
        user = sv.authenticate(self.user.get(), self.pw.get())
        if not user:
            messagebox.showerror("Login", "Wrong username or password.")
            return
        self.app.unbind("<Return>")
        self.app.show_main(user)
class RegisterWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.title("Register")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        body = ttk.Frame(self, padding=20)
        body.pack()
        self.entries = {}
        fields = [("full_name", "Full name", ""), ("username", "Username", ""), ("phone", "Phone", ""),
                  ("email", "Email", ""), ("password", "Password (min 6)", "*"), ("device", "Device name", "")]
        for i, (key, label, show) in enumerate(fields):
            ttk.Label(body, text=label).grid(row=i, column=0, sticky="w", pady=4)
            e = ttk.Entry(body, width=28, show=show)
            e.grid(row=i, column=1, pady=4, padx=(10, 0))
            self.entries[key] = e
        self.entries["device"].insert(0, "Phone-1")
        ttk.Button(body, text="Register", command=self.submit).grid(row=len(fields), columnspan=2,
                                                                    sticky="ew", pady=(12, 0))

    def submit(self):
        v = {k: e.get() for k, e in self.entries.items()}
        try:
            sv.register(v["full_name"], v["username"], v["phone"], v["email"], v["password"], v["device"])
        except sv.WalletError as err:
            messagebox.showerror("Register", str(err), parent=self)
            return
        messagebox.showinfo("Register", "Registration successful! Please log in.", parent=self)
        self.destroy()


# ---------------------------------------------------------------- Shared: report tab
class ReportTab(ttk.Frame):
    """Transaction report: risk/status filter + CSV export. Admin = shob, Customer = nijer."""

    def __init__(self, parent, user_id=None):
        super().__init__(parent, padding=10)
        self.user_id = user_id
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Risk:").pack(side="left")
        self.risk = ttk.Combobox(bar, values=["All", "LOW", "MEDIUM", "HIGH"], width=10, state="readonly")
        self.risk.set("All")
        self.risk.pack(side="left", padx=(4, 12))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.status = ttk.Combobox(bar, values=["All", "COMPLETED", "HELD", "CANCELLED", "FRAUD"],
                                   width=12, state="readonly")
        self.status.set("All")
        self.status.pack(side="left", padx=(4, 12))
        ttk.Button(bar, text="Filter", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Export CSV", command=self.export).pack(side="right")
        self.tree, frame = make_tree(self, TX_COLUMNS, height=16)
        frame.pack(fill="both", expand=True)
        self.rows = []

    def refresh(self):
        risk = None if self.risk.get() == "All" else self.risk.get()
        status = None if self.status.get() == "All" else self.status.get()
        self.rows = sv.fetch_transactions(self.user_id, risk, status)
        fill_tx_tree(self.tree, self.rows)

    def export(self):
        self.refresh()
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="transactions.csv",
                                            filetypes=[("CSV file", "*.csv")])
        if path:
            sv.export_csv(path, self.rows)
            messagebox.showinfo("Export", f"{len(self.rows)} transactions exported.\n{path}")


# ---------------------------------------------------------------- Customer
class CustomerView(ttk.Frame):
    def __init__(self, app, user):
        super().__init__(app.container)
        self.app, self.user = app, user
        self.uid = user["id"]
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # --- Dashboard
        dash = ttk.Frame(self.nb, padding=14)
        self.nb.add(dash, text="  Dashboard  ")
        box = tk.Frame(dash, bg=LIGHT, padx=20, pady=12, highlightbackground="#9cc0e8", highlightthickness=1)
        box.pack(fill="x")
        tk.Label(box, text="Wallet Balance", bg=LIGHT, font=FONT).pack(anchor="w")
        self.balance = tk.Label(box, text="0.00 Tk", bg=LIGHT, fg=BLUE, font=FONT_BIG)
        self.balance.pack(anchor="w")
        dep = ttk.Frame(dash)
        dep.pack(fill="x", pady=10)
        ttk.Label(dep, text="Add money (Tk):").pack(side="left")
        self.dep_amount = ttk.Entry(dep, width=14)
        self.dep_amount.pack(side="left", padx=6)
        ttk.Button(dep, text="Add Money", command=self.deposit).pack(side="left")
        ttk.Label(dash, text="Recent transactions", font=FONT_B).pack(anchor="w", pady=(6, 4))
        self.recent, frame = make_tree(dash, TX_COLUMNS, height=10)
        frame.pack(fill="both", expand=True)

        # --- Send money
        send = ttk.Frame(self.nb, padding=24)
        self.nb.add(send, text="  Send Money  ")
        self.send_entries = {}
        ttk.Label(send, text="Send Money", font=FONT_H, foreground=BLUE).grid(columnspan=2, sticky="w", pady=(0, 12))
        self.send_bal = ttk.Label(send, text="")
        self.send_bal.grid(columnspan=2, sticky="w", pady=(0, 8))
        for i, (key, label) in enumerate([("receiver", "Receiver username"), ("amount", "Amount (Tk)"),
                                          ("device", "Device"), ("note", "Note (optional)")], start=2):
            ttk.Label(send, text=label).grid(row=i, column=0, sticky="w", pady=5)
            if key == "device":
                w = ttk.Combobox(send, width=28)
            else:
                w = ttk.Entry(send, width=31)
            w.grid(row=i, column=1, pady=5, padx=(12, 0), sticky="w")
            self.send_entries[key] = w
        ttk.Button(send, text="Send", command=self.send).grid(row=6, column=1, sticky="w", padx=12, pady=14)
        ttk.Label(send, foreground="#666", justify="left",
                  text="Tip: Device list e nei emon nam dile 'new device' hishebe risk score barbe.\n"
                       "Amount 50,000 Tk er beshi hole o risk score barbe."
                  ).grid(row=7, columnspan=2, sticky="w")

        # --- Transactions
        self.report = ReportTab(self.nb, user_id=self.uid)
        self.nb.add(self.report, text="  Transactions  ")

        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.refresh())
        self.refresh()

    def refresh(self):
        bal = sv.get_balance(self.uid)
        self.balance.config(text=f"{money(bal)} Tk")
        self.send_bal.config(text=f"Available balance: {money(bal)} Tk")
        fill_tx_tree(self.recent, sv.fetch_transactions(self.uid, limit=10))
        self.send_entries["device"].config(values=sv.get_devices(self.uid))
        self.report.refresh()

    def deposit(self):
        try:
            sv.deposit(self.uid, parse_amount(self.dep_amount.get()))
        except sv.WalletError as err:
            messagebox.showerror("Add Money", str(err))
            return
        self.dep_amount.delete(0, "end")
        self.refresh()
        messagebox.showinfo("Add Money", "Money added to your wallet.")

    def send(self):
        e = self.send_entries
        try:
            level, score = sv.send_money(self.uid, e["receiver"].get(), parse_amount(e["amount"].get()),
                                         e["device"].get(), e["note"].get())
        except sv.WalletError as err:
            messagebox.showerror("Send Money", str(err))
            return
        if level == "HIGH":
            messagebox.showwarning("Send Money", f"High risk (Score {score}).\n"
                                   "The transaction is held for Admin review.")
        elif level == "MEDIUM":
            messagebox.showwarning("Send Money", f"Transaction completed, but a fraud alert was created (Score {score}).")
        else:
            messagebox.showinfo("Send Money", "Transaction successful.")
        for key in ("receiver", "amount", "note"):
            e[key].delete(0, "end")
        self.refresh()


# ---------------------------------------------------------------- Admin
class AdminView(ttk.Frame):
    def __init__(self, app, user):
        super().__init__(app.container)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # --- Alerts
        alerts = ttk.Frame(self.nb, padding=10)
        self.nb.add(alerts, text="  Fraud Alerts  ")
        self.stat_labels = {}
        stats = ttk.Frame(alerts)
        stats.pack(fill="x", pady=(0, 8))
        for key, title in [("customers", "Customers"), ("transactions", "Transactions"),
                           ("volume", "Volume (Tk)"), ("pending", "Pending alerts"), ("high", "HIGH alerts")]:
            card = tk.Frame(stats, bg=LIGHT, padx=14, pady=6, highlightbackground="#9cc0e8", highlightthickness=1)
            card.pack(side="left", padx=(0, 8))
            tk.Label(card, text=title, bg=LIGHT, font=("Segoe UI", 9)).pack(anchor="w")
            lbl = tk.Label(card, text="0", bg=LIGHT, fg=BLUE, font=("Segoe UI", 15, "bold"))
            lbl.pack(anchor="w")
            self.stat_labels[key] = lbl

        cols = [("id", "Alert", 50), ("date", "Date", 140), ("user", "User", 80), ("amount", "Amount", 90),
                ("device", "Device", 80), ("score", "Score", 50), ("level", "Risk", 70),
                ("status", "Status", 80), ("reasons", "Reasons", 330)]
        self.alert_tree, frame = make_tree(alerts, cols, height=14)
        frame.pack(fill="both", expand=True)
        self.alert_tree.bind("<<TreeviewSelect>>", self.on_select)
        self.alert_meta = {}

        btns = ttk.Frame(alerts)
        btns.pack(fill="x", pady=(8, 0))
        self.btn_ok = ttk.Button(btns, text="Approve / Mark Safe", command=lambda: self.review("approve"))
        self.btn_ok.pack(side="left")
        self.btn_no = ttk.Button(btns, text="Reject / Mark Fraud", command=lambda: self.review("reject"))
        self.btn_no.pack(side="left", padx=8)
        ttk.Button(btns, text="Refresh", command=self.refresh).pack(side="right")
        ttk.Label(btns, foreground="#666", text="HIGH = HELD (Approve/Reject)   MEDIUM = Safe/Fraud"
                  ).pack(side="right", padx=12)

        # --- Customers
        cust = ttk.Frame(self.nb, padding=10)
        self.nb.add(cust, text="  Customers  ")
        ccols = [("id", "ID", 50), ("username", "Username", 110), ("name", "Full name", 170),
                 ("phone", "Phone", 120), ("email", "Email", 190), ("balance", "Balance (Tk)", 110),
                 ("created", "Joined", 140)]
        self.cust_tree, frame = make_tree(cust, ccols, height=16)
        frame.pack(fill="both", expand=True)

        # --- Report
        self.report = ReportTab(self.nb)
        self.nb.add(self.report, text="  Transaction Report  ")

        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.refresh())
        self.refresh()

    def refresh(self):
        for key, value in sv.admin_stats().items():
            self.stat_labels[key].config(text=money(value) if key == "volume" else str(value))
        tree = self.alert_tree
        tree.delete(*tree.get_children())
        self.alert_meta = {}
        for a in sv.fetch_alerts():
            iid = tree.insert("", "end", tags=(a["risk_level"],), values=(
                a["id"], a["created_at"], a["username"], money(a["amount"]), a["device"] or "-",
                a["risk_score"], a["risk_level"], a["status"], a["reasons"]))
            self.alert_meta[iid] = a
        self.on_select()
        self.cust_tree.delete(*self.cust_tree.get_children())
        for c in sv.fetch_customers():
            self.cust_tree.insert("", "end", values=(
                c["id"], c["username"], c["full_name"], c["phone"], c["email"],
                money(c["balance"] or 0), c["created_at"]))
        self.report.refresh()

    def on_select(self, _event=None):
        sel = self.alert_tree.selection()
        a = self.alert_meta.get(sel[0]) if sel else None
        if a and a["tx_status"] == "HELD":
            self.btn_ok.config(text="Approve (money moves)")
            self.btn_no.config(text="Reject (cancel)")
        else:
            self.btn_ok.config(text="Mark Safe")
            self.btn_no.config(text="Mark Fraud")
        state = "normal" if a and a["status"] == "PENDING" else "disabled"
        self.btn_ok.config(state=state)
        self.btn_no.config(state=state)

    def review(self, action):
        sel = self.alert_tree.selection()
        if not sel:
            return
        a = self.alert_meta[sel[0]]
        try:
            msg = sv.review_alert(a["id"], action)
        except sv.WalletError as err:
            messagebox.showerror("Review", str(err))
        else:
            messagebox.showinfo("Review", msg)
        self.refresh()


# ---------------------------------------------------------------- Main window
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mobile Wallet Fraud Detection")
        self.geometry("1020x660")
        self.minsize(900, 560)
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=FONT)
        style.configure("Treeview", rowheight=24, font=FONT)
        style.configure("Treeview.Heading", font=FONT_B)
        style.configure("TNotebook.Tab", padding=(10, 5), font=FONT_B)
        self.header = tk.Frame(self, bg=BLUE)
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.show_login()

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def show_login(self):
        self.header.pack_forget()
        self._clear()
        LoginFrame(self).pack(fill="both", expand=True)

    def show_main(self, user):
        self._clear()
        for w in self.header.winfo_children():
            w.destroy()
        header_text = "  Admin" if user["role"] == "admin" else f"  {user['full_name']}  (Customer)"
        tk.Label(self.header, text=header_text, bg=BLUE, fg="white",
                 font=("Segoe UI", 12, "bold"), pady=8).pack(side="left")
        ttk.Button(self.header, text="Logout", command=self.show_login).pack(side="right", padx=10, pady=6)
        self.header.pack(fill="x", before=self.container)
        view = AdminView(self, user) if user["role"] == "admin" else CustomerView(self, user)
        view.pack(fill="both", expand=True, pady=(8, 0))
if __name__ == "__main__":
    init_db()
    App().mainloop()
