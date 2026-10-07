"""
Attendance Records and Person Directory Management Views.
Provides:
1. AttendanceRecordsPage: Filter, search, and delete attendance records, with direct export.
2. PersonsDirectoryPage: Manage registered students/employees, inspect profile info, and securely delete records and facial data.
"""

from typing import Optional
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from utils import get_current_date, open_folder_in_explorer, DATASET_DIR
import database
from face_recognition_module import face_manager
from reports import ReportGenerator
import pandas as pd


class AttendanceRecordsPage(ttk.Frame):
    """View, search, filter, and manage historical attendance logs."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.current_data = []

        self.setup_ui()

    def setup_ui(self):
        """Builds filtering toolbar and data Treeview."""
        self.configure(style="TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ----------------- TOOLBAR / FILTER CARD -----------------
        filter_card = ttk.LabelFrame(self, text="  Search & Filter Attendance Logs  ", padding=12)
        filter_card.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))

        # Search Query
        ttk.Label(filter_card, text="Search (Name / ID):", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=(5, 5), sticky="w")
        self.ent_search = ttk.Entry(filter_card, font=("Segoe UI", 9), width=18)
        self.ent_search.grid(row=0, column=1, padx=(0, 15), sticky="w")
        self.ent_search.bind("<KeyRelease>", lambda e: self.load_records())

        # Date Filter
        ttk.Label(filter_card, text="Date (YYYY-MM-DD):", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, padx=(5, 5), sticky="w")
        self.ent_date = ttk.Entry(filter_card, font=("Segoe UI", 9), width=13)
        self.ent_date.grid(row=0, column=3, padx=(0, 5), sticky="w")

        btn_today = ttk.Button(filter_card, text="Today", width=6, command=self.set_filter_today)
        btn_today.grid(row=0, column=4, padx=(0, 5), sticky="w")

        btn_all_dates = ttk.Button(filter_card, text="All", width=5, command=self.clear_date_filter)
        btn_all_dates.grid(row=0, column=5, padx=(0, 15), sticky="w")

        # Department Filter
        ttk.Label(filter_card, text="Department:", font=("Segoe UI", 9, "bold")).grid(row=0, column=6, padx=(5, 5), sticky="w")
        self.combo_dept = ttk.Combobox(filter_card, font=("Segoe UI", 9), width=18, state="readonly")
        self.combo_dept.grid(row=0, column=7, padx=(0, 15), sticky="w")
        self.combo_dept.bind("<<ComboboxSelected>>", lambda e: self.load_records())

        # Filter Action Buttons
        btn_apply = ttk.Button(filter_card, text="Apply Filter", command=self.load_records)
        btn_apply.grid(row=0, column=8, padx=5)

        btn_reset = ttk.Button(filter_card, text="Reset", command=self.reset_filters)
        btn_reset.grid(row=0, column=9, padx=5)

        # ----------------- DATA TABLE & ACTION BAR -----------------
        table_card = ttk.Frame(self)
        table_card.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(0, weight=1)

        # Treeview
        columns = ("id", "person_id", "name", "dept", "date", "time", "status")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("id", text="# ID")
        self.tree.heading("person_id", text="Person ID")
        self.tree.heading("name", text="Full Name")
        self.tree.heading("dept", text="Department / Class")
        self.tree.heading("date", text="Date")
        self.tree.heading("time", text="Time")
        self.tree.heading("status", text="Status")

        self.tree.column("id", width=60, anchor="center")
        self.tree.column("person_id", width=110, anchor="center")
        self.tree.column("name", width=180, anchor="w")
        self.tree.column("dept", width=160, anchor="w")
        self.tree.column("date", width=110, anchor="center")
        self.tree.column("time", width=100, anchor="center")
        self.tree.column("status", width=90, anchor="center")

        tree_scroll_y = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(table_card, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        # Bottom Bar: Summary and Actions
        bottom_bar = ttk.Frame(self)
        bottom_bar.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))

        self.lbl_count = ttk.Label(bottom_bar, text="Total Records: 0", font=("Segoe UI", 10, "bold"))
        self.lbl_count.pack(side="left")

        btn_export_excel = ttk.Button(bottom_bar, text="Export to Excel", command=lambda: self.export_current_view("xlsx"))
        btn_export_excel.pack(side="right", padx=(5, 0))

        btn_export_csv = ttk.Button(bottom_bar, text="Export to CSV", command=lambda: self.export_current_view("csv"))
        btn_export_csv.pack(side="right", padx=(5, 0))

        btn_delete = ttk.Button(bottom_bar, text="Delete Selected Record", command=self.delete_selected_record)
        btn_delete.pack(side="right", padx=(5, 10))

    def refresh(self):
        """Called when opening this tab to populate departments and load data."""
        depts = ["All Departments"] + database.get_distinct_departments()
        self.combo_dept["values"] = depts
        if not self.combo_dept.get():
            self.combo_dept.set("All Departments")
        self.load_records()

    def set_filter_today(self):
        """Sets the date input to today and refreshes."""
        self.ent_date.delete(0, tk.END)
        self.ent_date.insert(0, get_current_date())
        self.load_records()

    def clear_date_filter(self):
        """Clears the date input and refreshes."""
        self.ent_date.delete(0, tk.END)
        self.load_records()

    def reset_filters(self):
        """Resets all filter controls to defaults."""
        self.ent_search.delete(0, tk.END)
        self.ent_date.delete(0, tk.END)
        self.combo_dept.set("All Departments")
        self.load_records()

    def load_records(self):
        """Fetches attendance records from database and displays them in Treeview."""
        query = self.ent_search.get().strip()
        date_filter = self.ent_date.get().strip()
        dept_filter = self.combo_dept.get()

        records = database.get_attendance_records(
            search_query=query,
            date_filter=date_filter,
            department_filter=dept_filter
        )
        self.current_data = records

        # Clear existing rows
        for item in self.tree.get_children():
            self.tree.delete(item)

        for r in records:
            dept_text = r["department"] if r["department"] else "General"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    r["attendance_id"],
                    r["person_id"],
                    r["name"],
                    dept_text,
                    r["date"],
                    r["time"],
                    r["status"]
                )
            )

        self.lbl_count.config(text=f"Total Records: {len(records)}")

    def delete_selected_record(self):
        """Deletes the highlighted attendance record with confirmation."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select an attendance record from the table to delete.")
            return

        values = self.tree.item(selected[0], "values")
        att_id = int(values[0])
        person_name = values[2]
        date_val = values[4]

        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete attendance record #{att_id} for '{person_name}' on {date_val}?"
        )
        if confirm:
            ok, msg = database.delete_attendance_record(att_id)
            if ok:
                messagebox.showinfo("Success", msg)
                self.load_records()
                if hasattr(self.controller, "refresh_dashboard"):
                    self.controller.refresh_dashboard()
            else:
                messagebox.showerror("Error", msg)

    def export_current_view(self, export_format: str = "xlsx"):
        """Exports the currently filtered records into CSV or Excel."""
        if not self.current_data:
            messagebox.showwarning("No Data", "There are no attendance records to export.")
            return

        df = pd.DataFrame(self.current_data)
        df = df.rename(columns={
            "attendance_id": "Record ID",
            "person_id": "Person ID",
            "name": "Full Name",
            "department": "Department",
            "date": "Date",
            "time": "Time",
            "status": "Status"
        })

        ext = ".xlsx" if export_format == "xlsx" else ".csv"
        filetypes = [("Excel Files", "*.xlsx")] if export_format == "xlsx" else [("CSV Files", "*.csv")]

        filepath = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=filetypes,
            initialfile=f"attendance_records_{get_current_date()}{ext}"
        )
        if not filepath:
            return

        ok, msg, path = ReportGenerator.export_dataframe(
            df=df,
            filename_prefix="attendance_records",
            export_format=export_format,
            custom_filepath=filepath
        )

        if ok:
            messagebox.showinfo("Export Successful", f"Records successfully saved to:\n{path}")
        else:
            messagebox.showerror("Export Failed", msg)


class PersonsDirectoryPage(ttk.Frame):
    """Directory of all enrolled students and employees with secure deletion option."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.setup_ui()

    def setup_ui(self):
        """Constructs Directory UI."""
        self.configure(style="TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header toolbar
        hdr_card = ttk.LabelFrame(self, text="  Registered Students / Employees Directory  ", padding=12)
        hdr_card.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))

        ttk.Label(hdr_card, text="Search Persons:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(5, 5))
        self.ent_search = ttk.Entry(hdr_card, font=("Segoe UI", 9), width=25)
        self.ent_search.pack(side="left", padx=(0, 10))
        self.ent_search.bind("<KeyRelease>", lambda e: self.load_persons())

        btn_refresh = ttk.Button(hdr_card, text="Refresh", command=self.load_persons)
        btn_refresh.pack(side="left", padx=5)

        btn_new = ttk.Button(
            hdr_card,
            text="+ Register New Person",
            command=lambda: self.controller.show_frame("RegistrationPage")
        )
        btn_new.pack(side="right", padx=5)

        # Treeview
        table_frame = ttk.Frame(self)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        cols = ("id", "name", "father_name", "department", "phone", "email", "face_enrolled", "created_at")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")

        self.tree.heading("id", text="Person ID")
        self.tree.heading("name", text="Full Name")
        self.tree.heading("father_name", text="Father Name")
        self.tree.heading("department", text="Department / Class")
        self.tree.heading("phone", text="Phone Number")
        self.tree.heading("email", text="Email")
        self.tree.heading("face_enrolled", text="Facial Data")
        self.tree.heading("created_at", text="Registered On")

        self.tree.column("id", width=100, anchor="center")
        self.tree.column("name", width=160, anchor="w")
        self.tree.column("father_name", width=130, anchor="w")
        self.tree.column("department", width=150, anchor="w")
        self.tree.column("phone", width=120, anchor="center")
        self.tree.column("email", width=160, anchor="w")
        self.tree.column("face_enrolled", width=95, anchor="center")
        self.tree.column("created_at", width=130, anchor="center")

        sb_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        sb_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        sb_y.grid(row=0, column=1, sticky="ns")
        sb_x.grid(row=1, column=0, sticky="ew")

        # Bottom Action Bar
        bot_bar = ttk.Frame(self)
        bot_bar.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))

        self.lbl_count = ttk.Label(bot_bar, text="Enrolled: 0", font=("Segoe UI", 10, "bold"))
        self.lbl_count.pack(side="left")

        privacy_note = ttk.Label(
            bot_bar,
            text="🔒 Privacy Protection: Deleting an individual completely removes their database records, attendance logs, and facial dataset images.",
            font=("Segoe UI", 9, "italic"),
            foreground="#64748b"
        )
        privacy_note.pack(side="left", padx=20)

        btn_delete = ttk.Button(bot_bar, text="Delete Person & Face Data", command=self.delete_selected_person)
        btn_delete.pack(side="right")

    def refresh(self):
        """Called when displaying page."""
        self.load_persons()

    def load_persons(self):
        """Loads all persons from database into Treeview."""
        query = self.ent_search.get().strip()
        persons = database.get_all_persons(query)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for p in persons:
            has_face = "✓ Enrolled" if (p.get("face_data") and (DATASET_DIR / p["id"]).exists()) else "None"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    p["id"],
                    p["name"],
                    p.get("father_name", ""),
                    p.get("department", ""),
                    p.get("phone", ""),
                    p.get("email", ""),
                    has_face,
                    p.get("created_at", "")
                )
            )

        self.lbl_count.config(text=f"Total Enrolled: {len(persons)}")

    def delete_selected_person(self):
        """Deletes selected individual and cleans up dataset + retrains model."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a person from the directory to delete.")
            return

        values = self.tree.item(selected[0], "values")
        person_id = values[0]
        person_name = values[1]

        confirm = messagebox.askyesno(
            "Security & Privacy Deletion",
            f"Are you sure you want to permanently delete:\n\n"
            f"• ID: {person_id}\n"
            f"• Name: {person_name}\n\n"
            "This will delete their registration record, all past attendance entries, and all saved facial dataset files.",
            icon="warning"
        )
        if not confirm:
            return

        # 1. Delete person from SQLite database (cascades attendance)
        db_ok, db_msg = database.delete_person(person_id)

        # 2. Delete stored face dataset and retrain model
        face_manager.delete_person_face_data(person_id)

        if db_ok:
            messagebox.showinfo(
                "Deletion Successful",
                f"Person '{person_name}' and their facial biometric data have been completely purged from the system."
            )
            self.load_persons()
            if hasattr(self.controller, "refresh_dashboard"):
                self.controller.refresh_dashboard()
        else:
            messagebox.showerror("Error", db_msg)
