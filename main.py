"""
Face Recognition Attendance Management System.
Main Application Entry Point.

Features:
- Professional Tkinter GUI with custom ttk modern styling
- Sidebar navigation with active indicators
- Interactive Dashboard with real-time KPI metrics and today's activity log
- Multi-page routing:
    1. Dashboard
    2. Students / Employees Directory
    3. Person Face Registration
    4. Take Attendance (Live Webcam)
    5. Attendance Records (Search, Filter, Delete, Export)
    6. Reports & Analytics (Daily, Monthly, Individual)
- Graceful camera resource teardown and thread safety
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# Project imports
from utils import (
    BASE_DIR,
    get_current_date,
    get_current_time,
    DATASET_DIR,
    ENCODINGS_DIR,
    REPORTS_DIR,
    DATABASE_DIR,
    open_folder_in_explorer
)
import database
from face_recognition_module import face_manager
from registration import RegistrationPage
from attendance import AttendancePage
from records_view import AttendanceRecordsPage, PersonsDirectoryPage
from reports_view import ReportsPage


class ModernThemeManager:
    """Configures modern colors and ttk widget styles."""

    BG_DARK = "#0f172a"          # Slate 900
    SIDEBAR_BG = "#1e293b"       # Slate 800
    SIDEBAR_HOVER = "#334155"    # Slate 700
    ACCENT_PRIMARY = "#2563eb"   # Royal Blue
    ACCENT_SUCCESS = "#10b981"   # Emerald Green
    ACCENT_WARNING = "#f59e0b"   # Amber
    ACCENT_DANGER = "#ef4444"    # Crimson Red
    BG_LIGHT = "#f8fafc"         # Slate 50
    TEXT_LIGHT = "#ffffff"
    TEXT_MUTED = "#94a3b8"

    @classmethod
    def apply_styles(cls, root: tk.Tk):
        style = ttk.Style(root)

        # Use 'clam' or 'alt' as cross-platform baseline
        available_themes = style.theme_names()
        if "clam" in available_themes:
            style.theme_use("clam")

        # Configure Root Styles
        root.configure(bg=cls.BG_LIGHT)

        # Generic Frame
        style.configure("TFrame", background=cls.BG_LIGHT)
        style.configure("Sidebar.TFrame", background=cls.SIDEBAR_BG)
        style.configure("Card.TFrame", background="#ffffff", relief="solid", borderwidth=1)

        # Label Styles
        style.configure("TLabel", background=cls.BG_LIGHT, font=("Segoe UI", 10), foreground="#1e293b")
        style.configure("Header.TLabel", background=cls.BG_LIGHT, font=("Segoe UI", 16, "bold"), foreground="#0f172a")
        style.configure("Subheader.TLabel", background=cls.BG_LIGHT, font=("Segoe UI", 10), foreground="#64748b")
        style.configure("SidebarTitle.TLabel", background=cls.SIDEBAR_BG, font=("Segoe UI", 12, "bold"), foreground=cls.TEXT_LIGHT)
        style.configure("SidebarMuted.TLabel", background=cls.SIDEBAR_BG, font=("Segoe UI", 9), foreground=cls.TEXT_MUTED)

        # LabelFrame
        style.configure(
            "TLabelframe",
            background=cls.BG_LIGHT,
            relief="solid",
            borderwidth=1,
            bordercolor="#cbd5e1"
        )
        style.configure(
            "TLabelframe.Label",
            background=cls.BG_LIGHT,
            font=("Segoe UI", 10, "bold"),
            foreground="#334155"
        )

        # Buttons
        style.configure(
            "TButton",
            font=("Segoe UI", 10),
            padding=(10, 6),
            background="#e2e8f0",
            foreground="#0f172a",
            borderwidth=1
        )
        style.map(
            "TButton",
            background=[("active", "#cbd5e1"), ("pressed", "#94a3b8")]
        )

        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 7),
            background=cls.ACCENT_PRIMARY,
            foreground="#ffffff"
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#1d4ed8"), ("pressed", "#1e40af")]
        )

        style.configure(
            "Success.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 7),
            background=cls.ACCENT_SUCCESS,
            foreground="#ffffff"
        )
        style.map(
            "Success.TButton",
            background=[("active", "#059669"), ("pressed", "#047857")]
        )

        # Navigation Buttons in Sidebar
        style.configure(
            "Nav.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(14, 10),
            background=cls.SIDEBAR_BG,
            foreground="#cbd5e1",
            anchor="w",
            borderwidth=0
        )
        style.map(
            "Nav.TButton",
            background=[("active", cls.SIDEBAR_HOVER), ("pressed", "#0f172a")],
            foreground=[("active", "#ffffff")]
        )

        style.configure(
            "NavActive.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(14, 10),
            background=cls.ACCENT_PRIMARY,
            foreground="#ffffff",
            anchor="w",
            borderwidth=0
        )

        # Treeview (Modern Table Design)
        style.configure(
            "Treeview",
            font=("Segoe UI", 9),
            rowheight=28,
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#1e293b",
            borderwidth=1
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background="#f1f5f9",
            foreground="#334155",
            relief="flat",
            padding=(6, 6)
        )
        style.map(
            "Treeview",
            background=[("selected", "#dbeafe")],
            foreground=[("selected", "#1e3a8a")]
        )

        # Notebook tabs
        style.configure(
            "TNotebook.Tab",
            font=("Segoe UI", 9, "bold"),
            padding=(14, 8),
            background="#e2e8f0",
            foreground="#475569"
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#ffffff")],
            foreground=[("selected", cls.ACCENT_PRIMARY)]
        )


class DashboardPage(ttk.Frame):
    """Main Analytics & Operational Overview Dashboard."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.setup_ui()

    def setup_ui(self):
        self.configure(style="TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # ----------------- 1. WELCOME BANNER -----------------
        welcome_frame = ttk.Frame(self, padding=(20, 15, 20, 10))
        welcome_frame.grid(row=0, column=0, sticky="ew")
        welcome_frame.columnconfigure(0, weight=1)

        lbl_greet = ttk.Label(
            welcome_frame,
            text="Attendance Dashboard",
            style="Header.TLabel"
        )
        lbl_greet.grid(row=0, column=0, sticky="w")

        lbl_desc = ttk.Label(
            welcome_frame,
            text="Real-time facial verification statistics and daily attendance operations.",
            style="Subheader.TLabel"
        )
        lbl_desc.grid(row=1, column=0, sticky="w", pady=(2, 0))

        btn_refresh = ttk.Button(welcome_frame, text="🔄 Refresh Stats", command=self.refresh)
        btn_refresh.grid(row=0, column=1, rowspan=2, sticky="e")

        # ----------------- 2. FOUR KPI STAT CARDS -----------------
        kpi_container = ttk.Frame(self, padding=(20, 0, 20, 15))
        kpi_container.grid(row=1, column=0, sticky="ew")
        for i in range(4):
            kpi_container.columnconfigure(i, weight=1)

        self.card_total = self.build_kpi_card(
            kpi_container, 0, "TOTAL REGISTERED", "0", "Students & Employees", "#3b82f6", "👥"
        )
        self.card_today_att = self.build_kpi_card(
            kpi_container, 1, "TODAY'S ATTENDANCE", "0", "Total Check-in Logs", "#0ea5e9", "📋"
        )
        self.card_present = self.build_kpi_card(
            kpi_container, 2, "PRESENT TODAY", "0", "Verified In-Person", "#10b981", "✓"
        )
        self.card_absent = self.build_kpi_card(
            kpi_container, 3, "ABSENT TODAY", "0", "Unaccounted Individuals", "#ef4444", "✗"
        )

        # ----------------- 3. SPLIT PANE: QUICK ACTIONS & TODAY'S LOGS -----------------
        main_content = ttk.Frame(self, padding=(20, 0, 20, 20))
        main_content.grid(row=2, column=0, sticky="nsew")
        main_content.columnconfigure(0, weight=2)
        main_content.columnconfigure(1, weight=5)
        main_content.rowconfigure(0, weight=1)

        # Left Column: Quick Actions
        actions_card = ttk.LabelFrame(main_content, text="  Quick Actions  ", padding=15)
        actions_card.grid(row=0, column=0, sticky="nsew", padx=(0, 15))

        actions = [
            ("📷 Take Attendance", "Start live camera scanner", "AttendancePage", "Success.TButton"),
            ("➕ Register New Person", "Enroll facial features & details", "RegistrationPage", "Primary.TButton"),
            ("👥 Students & Employees", "Manage registered directory", "PersonsDirectoryPage", "TButton"),
            ("📋 Attendance Records", "View & filter past logs", "AttendanceRecordsPage", "TButton"),
            ("📊 Reports & Analytics", "Export daily & monthly sheets", "ReportsPage", "TButton")
        ]

        for idx, (title, sub, page_name, btn_style) in enumerate(actions):
            action_btn = ttk.Button(
                actions_card,
                text=title,
                style=btn_style,
                command=lambda p=page_name: self.controller.show_frame(p)
            )
            action_btn.pack(fill="x", pady=(0, 4) if idx == 0 else 4)

            sub_lbl = ttk.Label(actions_card, text=sub, font=("Segoe UI", 8), foreground="#64748b")
            sub_lbl.pack(anchor="w", padx=4, pady=(0, 8))

        # Right Column: Today's Recent Check-in Activity Feed
        feed_card = ttk.LabelFrame(main_content, text="  Today's Attendance Activity  ", padding=15)
        feed_card.grid(row=0, column=1, sticky="nsew")
        feed_card.columnconfigure(0, weight=1)
        feed_card.rowconfigure(0, weight=1)

        cols = ("time", "id", "name", "dept", "status")
        self.tree_today = ttk.Treeview(feed_card, columns=cols, show="headings", selectmode="browse")

        self.tree_today.heading("time", text="Time")
        self.tree_today.heading("id", text="Person ID")
        self.tree_today.heading("name", text="Full Name")
        self.tree_today.heading("dept", text="Department")
        self.tree_today.heading("status", text="Status")

        self.tree_today.column("time", width=90, anchor="center")
        self.tree_today.column("id", width=95, anchor="center")
        self.tree_today.column("name", width=160, anchor="w")
        self.tree_today.column("dept", width=140, anchor="w")
        self.tree_today.column("status", width=90, anchor="center")

        sb = ttk.Scrollbar(feed_card, orient="vertical", command=self.tree_today.yview)
        self.tree_today.configure(yscrollcommand=sb.set)

        self.tree_today.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

    def build_kpi_card(self, parent, col, title, initial_val, footer_text, color_accent, icon_symbol):
        """Constructs an eye-catching stat card with accent borders."""
        card = tk.Frame(
            parent,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#e2e8f0",
            padx=16,
            pady=14
        )
        card.grid(row=0, column=col, sticky="ew", padx=6)

        # Top line: Title & Icon
        top_row = tk.Frame(card, bg="#ffffff")
        top_row.pack(fill="x")

        lbl_t = tk.Label(top_row, text=title, font=("Segoe UI", 8, "bold"), fg="#64748b", bg="#ffffff")
        lbl_t.pack(side="left")

        lbl_icon = tk.Label(top_row, text=icon_symbol, font=("Segoe UI", 12, "bold"), fg=color_accent, bg="#ffffff")
        lbl_icon.pack(side="right")

        # Value Counter
        lbl_v = tk.Label(card, text=initial_val, font=("Segoe UI", 22, "bold"), fg=color_accent, bg="#ffffff")
        lbl_v.pack(anchor="w", pady=(4, 0))

        # Footer context
        lbl_f = tk.Label(card, text=footer_text, font=("Segoe UI", 8), fg="#94a3b8", bg="#ffffff")
        lbl_f.pack(anchor="w")

        return lbl_v

    def refresh(self):
        """Fetches latest numbers from SQLite and updates dashboard cards and table."""
        today = get_current_date()
        stats = database.get_dashboard_stats(today)

        self.card_total.config(text=str(stats["total_registered"]))
        self.card_today_att.config(text=str(stats["today_attendance"]))
        self.card_present.config(text=str(stats["present_count"]))
        self.card_absent.config(text=str(stats["absent_count"]))

        # Populate Today's Attendance Table
        records = database.get_attendance_records(date_filter=today)
        for item in self.tree_today.get_children():
            self.tree_today.delete(item)

        for r in records[:50]:  # Limit to latest 50 for speed
            self.tree_today.insert(
                "",
                tk.END,
                values=(
                    r["time"],
                    r["person_id"],
                    r["name"],
                    r.get("department") or "General",
                    r["status"]
                )
            )


class AttendanceApp(tk.Tk):
    """Main window controller and page router."""

    def __init__(self):
        super().__init__()

        self.title("Face Recognition Attendance Management System")
        self.geometry("1240x780")
        self.minsize(1050, 680)

        # Center on screen
        self.center_window(1240, 780)

        # Apply modern theme
        ModernThemeManager.apply_styles(self)

        # Initialize Container Layout
        self.setup_layout()

        # Instantiate Pages
        self.frames = {}
        self.active_frame_name = None

        self.init_pages()

        # Start Clock Timer
        self.update_clock()

        # Show initial Dashboard
        self.show_frame("DashboardPage")

        # Window closing protocol
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def center_window(self, width, height):
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = max(0, (screen_w - width) // 2)
        pos_y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    def setup_layout(self):
        """Builds main grid with left sidebar and right content container."""
        self.columnconfigure(0, weight=0, minsize=240)  # Sidebar
        self.columnconfigure(1, weight=1)              # Content
        self.rowconfigure(0, weight=1)

        # ==================== SIDEBAR ====================
        sidebar = ttk.Frame(self, style="Sidebar.TFrame", padding=(12, 20, 12, 15))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.columnconfigure(0, weight=1)

        # App Brand Header
        brand_icon = tk.Label(
            sidebar,
            text="🎯 Face Attendance",
            font=("Segoe UI", 14, "bold"),
            fg="#38bdf8",
            bg=ModernThemeManager.SIDEBAR_BG
        )
        brand_icon.pack(anchor="w", padx=8, pady=(0, 2))

        brand_sub = tk.Label(
            sidebar,
            text="Automated Biometric System",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg=ModernThemeManager.SIDEBAR_BG
        )
        brand_sub.pack(anchor="w", padx=8, pady=(0, 20))

        # Navigation Buttons Container
        self.nav_buttons = {}
        nav_items = [
            ("DashboardPage", "🏠  Dashboard"),
            ("PersonsDirectoryPage", "👥  Students / Employees"),
            ("RegistrationPage", "➕  Face Registration"),
            ("AttendancePage", "📷  Take Attendance"),
            ("AttendanceRecordsPage", "📋  Attendance Records"),
            ("ReportsPage", "📊  Reports & Analytics")
        ]

        for page_name, label in nav_items:
            btn = ttk.Button(
                sidebar,
                text=label,
                style="Nav.TButton",
                command=lambda p=page_name: self.show_frame(p)
            )
            btn.pack(fill="x", pady=3)
            self.nav_buttons[page_name] = btn

        # Spacer to push footer to bottom
        spacer = tk.Frame(sidebar, bg=ModernThemeManager.SIDEBAR_BG)
        spacer.pack(fill="both", expand=True)

        # Sidebar Footer: System Status & Clock
        footer = tk.Frame(sidebar, bg=ModernThemeManager.SIDEBAR_BG)
        footer.pack(fill="x", padx=8, pady=(10, 0))

        engine_name = face_manager.get_engine_name()
        lbl_engine_title = tk.Label(
            footer,
            text="ACTIVE AI ENGINE:",
            font=("Segoe UI", 7, "bold"),
            fg="#64748b",
            bg=ModernThemeManager.SIDEBAR_BG
        )
        lbl_engine_title.pack(anchor="w")

        lbl_engine_val = tk.Label(
            footer,
            text=engine_name,
            font=("Segoe UI", 8, "bold"),
            fg="#10b981",
            bg=ModernThemeManager.SIDEBAR_BG,
            wraplength=210,
            justify="left"
        )
        lbl_engine_val.pack(anchor="w", pady=(0, 8))

        # Real-time Clock
        self.lbl_clock = tk.Label(
            footer,
            text="00:00:00",
            font=("Segoe UI", 12, "bold"),
            fg="#f8fafc",
            bg=ModernThemeManager.SIDEBAR_BG
        )
        self.lbl_clock.pack(anchor="w")

        self.lbl_date = tk.Label(
            footer,
            text=get_current_date(),
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg=ModernThemeManager.SIDEBAR_BG
        )
        self.lbl_date.pack(anchor="w", pady=(0, 5))

        # ==================== MAIN CONTENT AREA ====================
        self.container = ttk.Frame(self, style="TFrame")
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def init_pages(self):
        """Initializes and registers all page views inside the container."""
        page_classes = (
            DashboardPage,
            PersonsDirectoryPage,
            RegistrationPage,
            AttendancePage,
            AttendanceRecordsPage,
            ReportsPage
        )

        for F in page_classes:
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

    def show_frame(self, page_name: str):
        """Transitions to the specified page and manages camera states."""
        # 1. Clean up previous page if it had an active camera feed
        if self.active_frame_name and self.active_frame_name in self.frames:
            prev_frame = self.frames[self.active_frame_name]
            if hasattr(prev_frame, "on_page_leave"):
                prev_frame.on_page_leave()

        # 2. Raise target frame
        frame = self.frames[page_name]
        frame.tkraise()
        self.active_frame_name = page_name

        # 3. Highlight active nav button
        for name, btn in self.nav_buttons.items():
            if name == page_name:
                btn.configure(style="NavActive.TButton")
            else:
                btn.configure(style="Nav.TButton")

        # 4. Trigger page refresh hook if defined
        if hasattr(frame, "refresh"):
            frame.refresh()

    def refresh_dashboard(self):
        """Helper for child views to refresh dashboard stats."""
        dash = self.frames.get("DashboardPage")
        if dash and hasattr(dash, "refresh"):
            dash.refresh()

    def update_clock(self):
        """Updates live system time in sidebar."""
        now = datetime.now()
        self.lbl_clock.config(text=now.strftime("%I:%M:%S %p"))
        self.lbl_date.config(text=now.strftime("%A, %b %d, %Y"))
        self.after(1000, self.update_clock)

    def on_closing(self):
        """Ensures all webcam resources and threads terminate gracefully."""
        # Teardown any running camera instances
        for name in ["RegistrationPage", "AttendancePage"]:
            f = self.frames.get(name)
            if f and hasattr(f, "on_page_leave"):
                f.on_page_leave()

        self.destroy()


def main():
    """Application entry point."""
    # Ensure database and folders are primed
    database.init_db()

    app = AttendanceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
