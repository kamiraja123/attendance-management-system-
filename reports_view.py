"""
Reports & Analytics Interactive GUI Page.
Provides multi-tab reporting:
1. Daily Attendance Report (Present/Absent roster for any selected date)
2. Monthly Attendance Report (Attendance percentage & days present across the month)
3. Individual Attendance Report (Complete attendance record history for a student or employee)
Supports real-time filtering, summary KPI cards, and one-click export to CSV & Excel (.xlsx).
"""

from datetime import datetime
from typing import Optional
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd

from utils import get_current_date, open_folder_in_explorer, REPORTS_DIR
from reports import ReportGenerator
import database


class ReportsPage(ttk.Frame):
    """Reports generation and export interface."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.daily_df: pd.DataFrame = pd.DataFrame()
        self.monthly_df: pd.DataFrame = pd.DataFrame()
        self.individual_df: pd.DataFrame = pd.DataFrame()

        self.setup_ui()

    def setup_ui(self):
        """Constructs tabbed analytics dashboard."""
        self.configure(style="TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Top Bar: Title & Open Reports Directory
        top_bar = ttk.Frame(self)
        top_bar.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))

        lbl_title = ttk.Label(
            top_bar,
            text="Attendance Reports & Analytics",
            font=("Segoe UI", 13, "bold"),
            foreground="#1e293b"
        )
        lbl_title.pack(side="left")

        btn_open_folder = ttk.Button(
            top_bar,
            text="📂 Open Reports Folder",
            command=lambda: open_folder_in_explorer(REPORTS_DIR)
        )
        btn_open_folder.pack(side="right")

        # Notebook for Report Sub-Tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))

        self.tab_daily = ttk.Frame(self.notebook)
        self.tab_monthly = ttk.Frame(self.notebook)
        self.tab_individual = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_daily, text="  📅 Daily Attendance Report  ")
        self.notebook.add(self.tab_monthly, text="  📊 Monthly Attendance Summary  ")
        self.notebook.add(self.tab_individual, text="  👤 Individual Attendance Log  ")

        self.build_daily_tab()
        self.build_monthly_tab()
        self.build_individual_tab()

    # ============================================================
    # 1. DAILY REPORT TAB
    # ============================================================
    def build_daily_tab(self):
        self.tab_daily.columnconfigure(0, weight=1)
        self.tab_daily.rowconfigure(2, weight=1)

        # Controls Card
        ctrl = ttk.LabelFrame(self.tab_daily, text="  Daily Report Parameters  ", padding=10)
        ctrl.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ttk.Label(ctrl, text="Select Date (YYYY-MM-DD):", font=("Segoe UI", 9, "bold")).pack(side="left", padx=5)
        self.ent_daily_date = ttk.Entry(ctrl, font=("Segoe UI", 9), width=13)
        self.ent_daily_date.insert(0, get_current_date())
        self.ent_daily_date.pack(side="left", padx=5)

        ttk.Button(ctrl, text="Today", width=6, command=lambda: self.set_daily_today()).pack(side="left", padx=2)
        ttk.Button(ctrl, text="Generate Daily Report", command=self.load_daily_report).pack(side="left", padx=10)

        ttk.Button(ctrl, text="Export Excel", command=lambda: self.export_report("daily", "xlsx")).pack(side="right", padx=5)
        ttk.Button(ctrl, text="Export CSV", command=lambda: self.export_report("daily", "csv")).pack(side="right", padx=5)

        # KPI Summary Cards Frame
        self.daily_kpi_frame = ttk.Frame(self.tab_daily)
        self.daily_kpi_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.lbl_daily_total = self.create_kpi_card(self.daily_kpi_frame, "Total Enrolled", "0", "#3b82f6", 0)
        self.lbl_daily_present = self.create_kpi_card(self.daily_kpi_frame, "Present Today", "0", "#10b981", 1)
        self.lbl_daily_absent = self.create_kpi_card(self.daily_kpi_frame, "Absent Today", "0", "#ef4444", 2)
        self.lbl_daily_rate = self.create_kpi_card(self.daily_kpi_frame, "Attendance Rate", "0.0%", "#8b5cf6", 3)

        # Data Table
        table_frame = ttk.Frame(self.tab_daily)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        cols = ("id", "name", "dept", "date", "time", "status", "phone", "email")
        self.daily_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")

        self.daily_tree.heading("id", text="Person ID")
        self.daily_tree.heading("name", text="Full Name")
        self.daily_tree.heading("dept", text="Department")
        self.daily_tree.heading("date", text="Date")
        self.daily_tree.heading("time", text="Check-in Time")
        self.daily_tree.heading("status", text="Status")
        self.daily_tree.heading("phone", text="Phone")
        self.daily_tree.heading("email", text="Email")

        self.daily_tree.column("id", width=90, anchor="center")
        self.daily_tree.column("name", width=160, anchor="w")
        self.daily_tree.column("dept", width=140, anchor="w")
        self.daily_tree.column("date", width=95, anchor="center")
        self.daily_tree.column("time", width=100, anchor="center")
        self.daily_tree.column("status", width=85, anchor="center")
        self.daily_tree.column("phone", width=110, anchor="center")
        self.daily_tree.column("email", width=150, anchor="w")

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.daily_tree.yview)
        self.daily_tree.configure(yscrollcommand=sb.set)

        self.daily_tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

    def set_daily_today(self):
        self.ent_daily_date.delete(0, tk.END)
        self.ent_daily_date.insert(0, get_current_date())
        self.load_daily_report()

    def load_daily_report(self):
        date_str = self.ent_daily_date.get().strip()
        df, summary = ReportGenerator.generate_daily_report(date_str)
        self.daily_df = df

        self.lbl_daily_total.config(text=str(summary["total"]))
        self.lbl_daily_present.config(text=str(summary["present"]))
        self.lbl_daily_absent.config(text=str(summary["absent"]))
        self.lbl_daily_rate.config(text=f"{summary['rate']}%")

        for item in self.daily_tree.get_children():
            self.daily_tree.delete(item)

        for _, row in df.iterrows():
            self.daily_tree.insert(
                "",
                tk.END,
                values=(
                    row["Person ID"],
                    row["Full Name"],
                    row["Department"],
                    row["Date"],
                    row["Check-in Time"],
                    row["Attendance Status"],
                    row["Phone Number"],
                    row["Email"]
                )
            )

    # ============================================================
    # 2. MONTHLY REPORT TAB
    # ============================================================
    def build_monthly_tab(self):
        self.tab_monthly.columnconfigure(0, weight=1)
        self.tab_monthly.rowconfigure(2, weight=1)

        ctrl = ttk.LabelFrame(self.tab_monthly, text="  Monthly Report Parameters  ", padding=10)
        ctrl.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        now = datetime.now()
        ttk.Label(ctrl, text="Month:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=5)
        self.combo_month = ttk.Combobox(ctrl, values=[f"{i:02d}" for i in range(1, 13)], width=5, state="readonly")
        self.combo_month.set(f"{now.month:02d}")
        self.combo_month.pack(side="left", padx=5)

        ttk.Label(ctrl, text="Year:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=5)
        self.combo_year = ttk.Combobox(ctrl, values=[str(y) for y in range(now.year - 3, now.year + 2)], width=7, state="readonly")
        self.combo_year.set(str(now.year))
        self.combo_year.pack(side="left", padx=5)

        ttk.Button(ctrl, text="Generate Monthly Report", command=self.load_monthly_report).pack(side="left", padx=15)

        ttk.Button(ctrl, text="Export Excel", command=lambda: self.export_report("monthly", "xlsx")).pack(side="right", padx=5)
        ttk.Button(ctrl, text="Export CSV", command=lambda: self.export_report("monthly", "csv")).pack(side="right", padx=5)

        # KPI Summary Cards
        self.monthly_kpi_frame = ttk.Frame(self.tab_monthly)
        self.monthly_kpi_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.lbl_month_period = self.create_kpi_card(self.monthly_kpi_frame, "Report Period", f"{now.strftime('%B %Y')}", "#3b82f6", 0)
        self.lbl_month_persons = self.create_kpi_card(self.monthly_kpi_frame, "Total Registered", "0", "#10b981", 1)
        self.lbl_month_active_days = self.create_kpi_card(self.monthly_kpi_frame, "Active Working Days", "0", "#8b5cf6", 2)

        # Data Table
        table_frame = ttk.Frame(self.tab_monthly)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        cols = ("id", "name", "dept", "days_present", "total_days", "rate")
        self.monthly_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")

        self.monthly_tree.heading("id", text="Person ID")
        self.monthly_tree.heading("name", text="Full Name")
        self.monthly_tree.heading("dept", text="Department")
        self.monthly_tree.heading("days_present", text="Days Present")
        self.monthly_tree.heading("total_days", text="Total Working Days")
        self.monthly_tree.heading("rate", text="Attendance Rate (%)")

        self.monthly_tree.column("id", width=110, anchor="center")
        self.monthly_tree.column("name", width=180, anchor="w")
        self.monthly_tree.column("dept", width=160, anchor="w")
        self.monthly_tree.column("days_present", width=120, anchor="center")
        self.monthly_tree.column("total_days", width=140, anchor="center")
        self.monthly_tree.column("rate", width=140, anchor="center")

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.monthly_tree.yview)
        self.monthly_tree.configure(yscrollcommand=sb.set)

        self.monthly_tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

    def load_monthly_report(self):
        try:
            year = int(self.combo_year.get())
            month = int(self.combo_month.get())
        except ValueError:
            messagebox.showwarning("Input Error", "Please select a valid month and year.")
            return

        df, summary = ReportGenerator.generate_monthly_report(year, month)
        self.monthly_df = df

        self.lbl_month_period.config(text=f"{summary['month']}")
        self.lbl_month_persons.config(text=str(summary["total_persons"]))
        self.lbl_month_active_days.config(text=str(summary["active_days"]))

        for item in self.monthly_tree.get_children():
            self.monthly_tree.delete(item)

        for _, row in df.iterrows():
            self.monthly_tree.insert(
                "",
                tk.END,
                values=(
                    row["Person ID"],
                    row["Full Name"],
                    row["Department"],
                    row["Days Present"],
                    row["Total Working Days"],
                    f"{row['Attendance Rate (%)']}%"
                )
            )

    # ============================================================
    # 3. INDIVIDUAL REPORT TAB
    # ============================================================
    def build_individual_tab(self):
        self.tab_individual.columnconfigure(0, weight=1)
        self.tab_individual.rowconfigure(2, weight=1)

        ctrl = ttk.LabelFrame(self.tab_individual, text="  Individual Person Selection  ", padding=10)
        ctrl.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ttk.Label(ctrl, text="Select Person:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=5)
        self.combo_ind_person = ttk.Combobox(ctrl, font=("Segoe UI", 9), width=32, state="readonly")
        self.combo_ind_person.pack(side="left", padx=5)

        ttk.Button(ctrl, text="Generate History", command=self.load_individual_report).pack(side="left", padx=10)

        ttk.Button(ctrl, text="Export Excel", command=lambda: self.export_report("individual", "xlsx")).pack(side="right", padx=5)
        ttk.Button(ctrl, text="Export CSV", command=lambda: self.export_report("individual", "csv")).pack(side="right", padx=5)

        # Profile Summary Card
        self.ind_kpi_frame = ttk.Frame(self.tab_individual)
        self.ind_kpi_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.lbl_ind_name = self.create_kpi_card(self.ind_kpi_frame, "Individual Name", "---", "#3b82f6", 0)
        self.lbl_ind_id = self.create_kpi_card(self.ind_kpi_frame, "Person ID", "---", "#64748b", 1)
        self.lbl_ind_dept = self.create_kpi_card(self.ind_kpi_frame, "Department", "---", "#8b5cf6", 2)
        self.lbl_ind_present = self.create_kpi_card(self.ind_kpi_frame, "Total Days Present", "0", "#10b981", 3)

        # Data Table
        table_frame = ttk.Frame(self.tab_individual)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        cols = ("date", "time", "status")
        self.ind_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")

        self.ind_tree.heading("date", text="Attendance Date")
        self.ind_tree.heading("time", text="Check-In Time")
        self.ind_tree.heading("status", text="Recorded Status")

        self.ind_tree.column("date", width=180, anchor="center")
        self.ind_tree.column("time", width=180, anchor="center")
        self.ind_tree.column("status", width=180, anchor="center")

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.ind_tree.yview)
        self.ind_tree.configure(yscrollcommand=sb.set)

        self.ind_tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

    def load_individual_report(self):
        selection = self.combo_ind_person.get().strip()
        if not selection:
            messagebox.showwarning("Selection Required", "Please select a registered person from the dropdown.")
            return

        person_id = selection.split(" - ")[0].strip()
        df, summary = ReportGenerator.generate_individual_report(person_id)
        self.individual_df = df

        if not summary.get("found"):
            messagebox.showinfo("Not Found", f"No record found for ID {person_id}")
            return

        person = summary["person"]
        self.lbl_ind_name.config(text=person["name"])
        self.lbl_ind_id.config(text=person["id"])
        self.lbl_ind_dept.config(text=person.get("department", "General"))
        self.lbl_ind_present.config(text=str(summary["total_present_days"]))

        for item in self.ind_tree.get_children():
            self.ind_tree.delete(item)

        for _, row in df.iterrows():
            self.ind_tree.insert(
                "",
                tk.END,
                values=(
                    row["Date"],
                    row["Time Marked"],
                    row["Status"]
                )
            )

    # ============================================================
    # SHARED HELPERS
    # ============================================================
    def create_kpi_card(self, parent, title: str, initial_val: str, color_accent: str, col_idx: int) -> ttk.Label:
        """Creates a clean KPI stat card."""
        parent.columnconfigure(col_idx, weight=1)
        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        card.grid(row=0, column=col_idx, padx=5, sticky="ew")

        ttk.Label(card, text=title, font=("Segoe UI", 9, "bold"), foreground="#64748b").pack(anchor="w")
        val_lbl = ttk.Label(card, text=initial_val, font=("Segoe UI", 14, "bold"), foreground=color_accent)
        val_lbl.pack(anchor="w", pady=(3, 0))
        return val_lbl

    def export_report(self, report_type: str, export_format: str):
        """Dispatches export request for daily, monthly, or individual dataframes."""
        if report_type == "daily":
            df = self.daily_df
            prefix = f"daily_attendance_{self.ent_daily_date.get()}"
        elif report_type == "monthly":
            df = self.monthly_df
            prefix = f"monthly_attendance_{self.combo_year.get()}_{self.combo_month.get()}"
        else:
            df = self.individual_df
            person_part = self.lbl_ind_id.cget("text")
            prefix = f"individual_attendance_{person_part}"

        if df.empty:
            messagebox.showwarning("No Data", "Please generate the report before exporting.")
            return

        ext = ".xlsx" if export_format == "xlsx" else ".csv"
        filetypes = [("Excel Files", "*.xlsx")] if export_format == "xlsx" else [("CSV Files", "*.csv")]

        filepath = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=filetypes,
            initialfile=f"{prefix}{ext}"
        )
        if not filepath:
            return

        ok, msg, path = ReportGenerator.export_dataframe(
            df=df,
            filename_prefix=prefix,
            export_format=export_format,
            custom_filepath=filepath
        )

        if ok:
            messagebox.showinfo("Export Successful", f"File saved:\n{path}")
        else:
            messagebox.showerror("Export Failed", msg)

    def refresh(self):
        """Called when opening the Reports tab to sync people dropdown and generate daily report."""
        persons = database.get_all_persons()
        person_options = [f"{p['id']} - {p['name']}" for p in persons]
        self.combo_ind_person["values"] = person_options
        if person_options and not self.combo_ind_person.get():
            self.combo_ind_person.set(person_options[0])

        self.load_daily_report()
