"""
Take Attendance GUI Module.
Provides live webcam attendance scanning:
- Real-time face detection and identity matching
- Automatic attendance marking for recognized individuals
- Prevention of duplicate attendance for the same day
- Audio cues and HUD overlays (Green=Recognized, Cyan=Already Marked, Red=Unknown)
- Live sidebar table showing attendance marked during current active session
"""

import time
from typing import Optional, Dict, Tuple, Set
import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk

from utils import (
    get_current_date,
    get_current_time,
    play_success_sound,
    play_warning_sound
)
import database
from face_recognition_module import face_manager


class AttendancePage(ttk.Frame):
    """Interactive webcam page for automated face recognition attendance."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Video & Recognition State
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_camera_running = False
        self.photo_image = None

        # Tracking state to prevent duplicate database writes and audio spam
        self.recognized_streaks: Dict[str, int] = {}  # person_id -> consecutive frames seen
        self.recently_marked_cache: Set[str] = set()   # person_ids marked during this app session
        self.session_count = 0

        self.setup_ui()

    def setup_ui(self):
        """Constructs split-pane layout: Camera stream (Left) & Live Log (Right)."""
        self.configure(style="TFrame")

        self.columnconfigure(0, weight=5)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        # ----------------- LEFT PANE: LIVE SCANNER -----------------
        cam_card = ttk.LabelFrame(self, text="  Live Facial Attendance Scanner  ", padding=15)
        cam_card.grid(row=0, column=0, sticky="nsew", padx=(15, 10), pady=15)
        cam_card.columnconfigure(0, weight=1)
        cam_card.rowconfigure(1, weight=1)

        # Scanner Header
        hdr_frame = ttk.Frame(cam_card)
        hdr_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.lbl_status = ttk.Label(
            hdr_frame,
            text="Scanner: Inactive (Click 'Start Scanner')",
            font=("Segoe UI", 10, "italic"),
            foreground="#64748b"
        )
        self.lbl_status.pack(side="left")

        self.btn_toggle = ttk.Button(
            hdr_frame,
            text="Start Scanner",
            command=self.toggle_scanner
        )
        self.btn_toggle.pack(side="right")

        # Video Canvas
        self.video_canvas = tk.Canvas(
            cam_card,
            bg="#0b0f19",
            highlightthickness=1,
            highlightbackground="#1e293b"
        )
        self.video_canvas.grid(row=1, column=0, sticky="nsew")

        self.placeholder_text = self.video_canvas.create_text(
            260, 200,
            text="Face Recognition Scanner is Standby.\n\n"
                 "• Ensure good ambient lighting.\n"
                 "• Face the camera directly.\n"
                 "• The system will automatically detect, verify, and mark your attendance.",
            fill="#94a3b8",
            font=("Segoe UI", 11),
            justify="center"
        )

        # Notification Banner at bottom of camera card
        self.lbl_toast = ttk.Label(
            cam_card,
            text="Ready to take attendance.",
            font=("Segoe UI", 10, "bold"),
            foreground="#38bdf8",
            anchor="center"
        )
        self.lbl_toast.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        # ----------------- RIGHT PANE: SESSION ATTENDANCE LOG -----------------
        log_card = ttk.LabelFrame(self, text="  Session Check-In Activity  ", padding=15)
        log_card.grid(row=0, column=1, sticky="nsew", padx=(10, 15), pady=15)
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)

        # Counter Header
        log_header = ttk.Frame(log_card)
        log_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.lbl_session_count = ttk.Label(
            log_header,
            text="Marked This Session: 0",
            font=("Segoe UI", 11, "bold"),
            foreground="#10b981"
        )
        self.lbl_session_count.pack(side="left")

        btn_clear_log = ttk.Button(
            log_header,
            text="Clear View",
            command=self.clear_session_table,
            width=10
        )
        btn_clear_log.pack(side="right")

        # Treeview for live session logs
        columns = ("time", "id", "name", "status")
        self.tree = ttk.Treeview(log_card, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("time", text="Time")
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("status", text="Status")

        self.tree.column("time", width=75, anchor="center")
        self.tree.column("id", width=85, anchor="center")
        self.tree.column("name", width=120, anchor="w")
        self.tree.column("status", width=75, anchor="center")

        tree_scroll = ttk.Scrollbar(log_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.grid(row=1, column=0, sticky="nsew")
        tree_scroll.grid(row=1, column=1, sticky="ns")

        # Bottom Helper Note
        note_lbl = ttk.Label(
            log_card,
            text="💡 Tip: Duplicate attendance on the same day is prevented automatically.",
            font=("Segoe UI", 9, "italic"),
            foreground="#64748b",
            wraplength=280
        )
        note_lbl.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def toggle_scanner(self):
        """Starts or stops the scanner webcam feed."""
        if self.is_camera_running:
            self.stop_scanner()
        else:
            self.start_scanner()

    def start_scanner(self):
        """Activates camera stream and facial recognition."""
        if self.is_camera_running:
            return

        if not face_manager.is_model_trained():
            messagebox.showwarning(
                "No Enrolled Faces",
                "No trained face recognition model found!\n\n"
                "Please go to the 'Face Registration' page and register at least one student or employee before taking attendance."
            )
            return

        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                messagebox.showerror(
                    "Camera Error",
                    "Could not access the webcam.\nPlease ensure no other application is using it."
                )
                self.cap = None
                return

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            self.is_camera_running = True
            self.btn_toggle.config(text="Stop Scanner")
            engine_name = face_manager.get_engine_name()
            self.lbl_status.config(
                text=f"Scanner: Active ({engine_name})",
                foreground="#10b981"
            )
            self.lbl_toast.config(
                text="Scanning for registered faces...",
                foreground="#38bdf8"
            )

            # Start real-time recognition frame cycle
            self.update_frame()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start camera: {e}")
            self.stop_scanner()

    def stop_scanner(self):
        """Releases camera resource and halts video loop."""
        self.is_camera_running = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        self.btn_toggle.config(text="Start Scanner")
        self.lbl_status.config(text="Scanner: Inactive", foreground="#64748b")
        self.lbl_toast.config(text="Scanner stopped.", foreground="#94a3b8")

        self.video_canvas.delete("all")
        self.placeholder_text = self.video_canvas.create_text(
            260, 200,
            text="Scanner is offline.\nClick 'Start Scanner' to resume taking attendance.",
            fill="#94a3b8",
            font=("Segoe UI", 11),
            justify="center"
        )

    def update_frame(self):
        """Continuous frame processing loop for real-time recognition."""
        if not self.is_camera_running or self.cap is None:
            return

        ret, frame = self.cap.read()
        if not ret or frame is None:
            self.after(30, self.update_frame)
            return

        # Mirror horizontally for natural webcam view
        frame = cv2.flip(frame, 1)

        # Detect faces in frame
        faces = face_manager.detect_faces(frame)
        today = get_current_date()

        for box in faces:
            # Predict identity
            person_id, confidence, is_known = face_manager.recognize_face(frame, box)

            if is_known and person_id:
                # Look up person info from DB
                person_info = database.get_person(person_id)
                person_name = person_info["name"] if person_info else person_id

                # Check if attendance is already marked today
                already_marked = (
                    person_id in self.recently_marked_cache or
                    database.is_attendance_marked_today(person_id, today)
                )

                if already_marked:
                    self.recently_marked_cache.add(person_id)
                    title = f"Already Marked: {person_name}"
                    subtitle = f"ID: {person_id} | Conf: {int(confidence)}%"
                    face_manager.draw_hud_box(
                        frame, box, title, subtitle,
                        is_known=True, is_already_marked=True
                    )
                else:
                    # New attendance marking
                    title = f"{person_name}"
                    subtitle = f"ID: {person_id} | Conf: {int(confidence)}%"
                    face_manager.draw_hud_box(
                        frame, box, title, subtitle,
                        is_known=True, is_already_marked=False
                    )

                    # Consecutive frame recognition smoothing (2 frames)
                    streak = self.recognized_streaks.get(person_id, 0) + 1
                    self.recognized_streaks[person_id] = streak

                    if streak >= 2:
                        self.process_successful_attendance(person_id, person_name)
                        self.recognized_streaks[person_id] = 0
            else:
                # Unknown individual
                title = "Unknown Person"
                subtitle = "Not registered in dataset"
                face_manager.draw_hud_box(
                    frame, box, title, subtitle,
                    is_known=False, is_already_marked=False
                )

        # Render frame onto Tkinter Canvas
        canvas_w = self.video_canvas.winfo_width()
        canvas_h = self.video_canvas.winfo_height()
        if canvas_w < 50:
            canvas_w, canvas_h = 560, 420

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_frame)
        img = img.resize((canvas_w, canvas_h), Image.Resampling.BILINEAR)
        self.photo_image = ImageTk.PhotoImage(image=img)

        self.video_canvas.delete("all")
        self.video_canvas.create_image(0, 0, anchor="nw", image=self.photo_image)

        # Loop after 30ms (approx 30fps)
        self.after(30, self.update_frame)

    def process_successful_attendance(self, person_id: str, person_name: str):
        """Marks attendance in database, gives audio feedback, and updates UI."""
        today = get_current_date()
        cur_time = get_current_time()

        success, msg = database.mark_attendance(
            person_id=person_id,
            name=person_name,
            date_str=today,
            time_str=cur_time,
            status="Present"
        )

        if success:
            self.recently_marked_cache.add(person_id)
            self.session_count += 1
            self.lbl_session_count.config(text=f"Marked This Session: {self.session_count}")

            # Audio beep
            play_success_sound()

            # Toast update
            self.lbl_toast.config(
                text=f"✓ Attendance Marked: {person_name} ({person_id}) at {cur_time}",
                foreground="#10b981"
            )

            # Insert at top of session activity Treeview
            self.tree.insert("", 0, values=(cur_time, person_id, person_name, "Present"))

            # Notify controller to refresh dashboard stats if visible
            if hasattr(self.controller, "refresh_dashboard"):
                self.controller.refresh_dashboard()
        else:
            self.recently_marked_cache.add(person_id)
            self.lbl_toast.config(text=msg, foreground="#f59e0b")

    def clear_session_table(self):
        """Clears the live view table."""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def on_page_leave(self):
        """Stops scanner when switching away from this tab."""
        if self.is_camera_running:
            self.stop_scanner()
