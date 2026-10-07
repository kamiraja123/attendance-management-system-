"""
Person Registration and Face Enrollment GUI Module.
Provides interactive form for Student/Employee registration with:
- ID, Name, Father Name, Phone, Department, Email fields
- Security & Privacy Consent Notice checkbox
- Embedded real-time webcam feed with face detection box
- Burst capture of face samples (15 frames) saved to dataset/
- Automatic training/encoding trigger
- Safe webcam resource management and graceful fallback if camera is offline
"""

import time
import threading
from typing import Optional, List, Tuple
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk

from utils import validate_person_input, DATASET_DIR
import database
from face_recognition_module import face_manager


class RegistrationPage(ttk.Frame):
    """Registration frame for capturing person details and facial samples."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Camera & Capture State
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_camera_running = False
        self.is_capturing_samples = False
        self.captured_count = 0
        self.target_samples = 15
        self.captured_boxes: List[Tuple[int, int, int, int]] = []
        self.current_frame_bgr = None
        self.current_face_box = None
        self.photo_image = None
        self.last_capture_time = 0.0

        self.setup_ui()

    def setup_ui(self):
        """Builds the dual-pane registration interface."""
        self.configure(style="TFrame")

        # Main Layout Grid: Left pane for Form, Right pane for Camera
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=4)
        self.rowconfigure(0, weight=1)

        # ----------------- LEFT PANE: REGISTRATION FORM -----------------
        form_card = ttk.LabelFrame(self, text="  Person Information Form  ", padding=20)
        form_card.grid(row=0, column=0, sticky="nsew", padx=(15, 10), pady=15)
        form_card.columnconfigure(1, weight=1)

        labels = [
            ("Person ID *:", "Unique Student / Employee ID (e.g. EMP-101, STD-2026-01)"),
            ("Full Name *:", "Enter full name"),
            ("Father Name:", "Enter father/guardian name"),
            ("Phone Number:", "e.g. +1 555-0199 or 0300-1234567"),
            ("Department / Class *:", "Select or type department"),
            ("Email Address:", "e.g. name@company.edu")
        ]

        self.entries = {}
        for idx, (label_text, placeholder) in enumerate(labels):
            lbl = ttk.Label(form_card, text=label_text, font=("Segoe UI", 10, "bold"))
            lbl.grid(row=idx, column=0, sticky="w", pady=8, padx=(0, 10))

            if "Department" in label_text:
                combo = ttk.Combobox(
                    form_card,
                    values=[
                        "Computer Science",
                        "Information Technology",
                        "Software Engineering",
                        "Electrical Engineering",
                        "Business Administration",
                        "Human Resources",
                        "Finance & Accounts",
                        "Marketing & Sales",
                        "Operations & Admin",
                        "General Staff"
                    ],
                    font=("Segoe UI", 10)
                )
                combo.grid(row=idx, column=1, sticky="ew", pady=8)
                combo.set("Computer Science")
                self.entries["department"] = combo
            else:
                ent = ttk.Entry(form_card, font=("Segoe UI", 10))
                ent.grid(row=idx, column=1, sticky="ew", pady=8)
                key = label_text.split()[0].lower().replace(":", "").replace("*", "")
                if "person" in label_text.lower():
                    key = "person_id"
                elif "full" in label_text.lower():
                    key = "name"
                elif "father" in label_text.lower():
                    key = "father_name"
                elif "phone" in label_text.lower():
                    key = "phone"
                elif "email" in label_text.lower():
                    key = "email"
                self.entries[key] = ent

        # Privacy and Consent Notice (Mandatory Checkbox)
        consent_frame = ttk.LabelFrame(form_card, text=" Security & Privacy Notice ", padding=12)
        consent_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(15, 10))

        self.consent_var = tk.BooleanVar(value=False)
        self.chk_consent = ttk.Checkbutton(
            consent_frame,
            text="I agree to capture and store facial data solely for the\npurpose of automated attendance verification.",
            variable=self.consent_var,
            command=self.on_consent_toggled
        )
        self.chk_consent.pack(anchor="w", padx=5, pady=2)

        # Action Buttons inside Form
        btn_box = ttk.Frame(form_card)
        btn_box.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(15, 0))
        btn_box.columnconfigure(0, weight=1)
        btn_box.columnconfigure(1, weight=1)

        self.btn_clear = ttk.Button(
            btn_box,
            text="Clear Form",
            command=self.clear_form,
            width=14
        )
        self.btn_clear.grid(row=0, column=0, padx=5, sticky="ew")

        self.btn_manual_register = ttk.Button(
            btn_box,
            text="Save Record Only",
            command=self.register_without_face,
            width=18
        )
        self.btn_manual_register.grid(row=0, column=1, padx=5, sticky="ew")

        # ----------------- RIGHT PANE: WEBCAM FACE ENROLLMENT -----------------
        cam_card = ttk.LabelFrame(self, text="  Live Face Enrollment Camera  ", padding=15)
        cam_card.grid(row=0, column=1, sticky="nsew", padx=(10, 15), pady=15)
        cam_card.columnconfigure(0, weight=1)
        cam_card.rowconfigure(1, weight=1)

        # Camera Header Bar
        cam_header = ttk.Frame(cam_card)
        cam_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.lbl_cam_status = ttk.Label(
            cam_header,
            text="Status: Camera Standby",
            font=("Segoe UI", 10, "italic"),
            foreground="#64748b"
        )
        self.lbl_cam_status.pack(side="left")

        self.btn_toggle_cam = ttk.Button(
            cam_header,
            text="Start Camera",
            command=self.toggle_camera
        )
        self.btn_toggle_cam.pack(side="right")

        # Video Display Canvas
        self.video_canvas = tk.Canvas(
            cam_card,
            bg="#0f172a",
            highlightthickness=1,
            highlightbackground="#334155"
        )
        self.video_canvas.grid(row=1, column=0, sticky="nsew")

        # Initial Placeholder text
        self.placeholder_text_id = self.video_canvas.create_text(
            240, 180,
            text="Click 'Start Camera' to begin face capture preview.\nEnsure adequate lighting and look directly into the camera.",
            fill="#94a3b8",
            font=("Segoe UI", 11),
            justify="center"
        )

        # Progress bar and Counter for Face Samples
        progress_box = ttk.Frame(cam_card)
        progress_box.grid(row=2, column=0, sticky="ew", pady=(12, 5))
        progress_box.columnconfigure(1, weight=1)

        self.lbl_samples = ttk.Label(
            progress_box,
            text="Samples: 0 / 15",
            font=("Segoe UI", 10, "bold")
        )
        self.lbl_samples.grid(row=0, column=0, padx=(0, 10))

        self.progress_bar = ttk.Progressbar(
            progress_box,
            orient="horizontal",
            maximum=self.target_samples,
            mode="determinate"
        )
        self.progress_bar.grid(row=0, column=1, sticky="ew")

        # Capture Button
        self.btn_capture = ttk.Button(
            cam_card,
            text="Capture Face & Enroll Person",
            command=self.start_sample_capture,
            state="disabled"
        )
        self.btn_capture.grid(row=3, column=0, sticky="ew", pady=(8, 0))

    def on_consent_toggled(self):
        """Enables/disables capture button based on consent status."""
        self.update_capture_button_state()

    def update_capture_button_state(self):
        """Updates whether capture is permitted."""
        has_consent = self.consent_var.get()
        has_cam = self.is_camera_running
        if has_consent and has_cam:
            self.btn_capture.config(state="normal")
        else:
            self.btn_capture.config(state="disabled")

    def toggle_camera(self):
        """Starts or stops the webcam feed."""
        if self.is_camera_running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        """Initializes webcam capture."""
        if self.is_camera_running:
            return

        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                messagebox.showerror(
                    "Camera Error",
                    "Unable to access the webcam. Please ensure a camera is connected and not currently used by another program."
                )
                self.cap = None
                return

            # Set resolution for crisp video
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            self.is_camera_running = True
            self.btn_toggle_cam.config(text="Stop Camera")
            self.lbl_cam_status.config(text="Status: Camera Active (Detecting Faces...)", foreground="#10b981")
            self.update_capture_button_state()

            # Start video stream loop
            self.update_frame()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start camera: {e}")
            self.stop_camera()

    def stop_camera(self):
        """Safely stops video feed and releases camera hardware."""
        self.is_camera_running = False
        self.is_capturing_samples = False

        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        self.btn_toggle_cam.config(text="Start Camera")
        self.lbl_cam_status.config(text="Status: Camera Stopped", foreground="#64748b")
        self.update_capture_button_state()

        # Reset Canvas
        self.video_canvas.delete("all")
        self.placeholder_text_id = self.video_canvas.create_text(
            240, 180,
            text="Camera is stopped.\nClick 'Start Camera' to reactivate.",
            fill="#94a3b8",
            font=("Segoe UI", 11),
            justify="center"
        )

    def update_frame(self):
        """Periodically reads frame from webcam, detects faces, and paints on canvas."""
        if not self.is_camera_running or self.cap is None:
            return

        ret, frame = self.cap.read()
        if not ret or frame is None:
            self.after(30, self.update_frame)
            return

        # Flip horizontally for natural mirror feel
        frame = cv2.flip(frame, 1)
        self.current_frame_bgr = frame.copy()

        # Detect faces in frame
        faces = face_manager.detect_faces(frame)
        self.current_face_box = faces[0] if faces else None

        # Draw visual indicators on frame
        canvas_w = self.video_canvas.winfo_width()
        canvas_h = self.video_canvas.winfo_height()
        if canvas_w < 50:
            canvas_w, canvas_h = 480, 360

        display_frame = frame.copy()

        if faces:
            # Highlight detected face
            fx, fy, fw, fh = faces[0]
            box_color = (65, 215, 95) if not self.is_capturing_samples else (255, 165, 0)
            cv2.rectangle(display_frame, (fx, fy), (fx + fw, fy + fh), box_color, 2)

            tag = "Face Detected" if not self.is_capturing_samples else f"Capturing: {self.captured_count}/{self.target_samples}"
            cv2.putText(
                display_frame,
                tag,
                (fx, max(20, fy - 10)),
                cv2.FONT_HERSHEY_DUPLEX,
                0.6,
                box_color,
                1,
                cv2.LINE_AA
            )
        else:
            cv2.putText(
                display_frame,
                "No face detected. Please face the camera.",
                (20, 35),
                cv2.FONT_HERSHEY_DUPLEX,
                0.6,
                (0, 140, 255),
                1,
                cv2.LINE_AA
            )

        # Handle burst capture during active enrollment
        if self.is_capturing_samples and self.current_face_box:
            now = time.time()
            # Capture a sample every 200 milliseconds to get varied angles/expressions
            if now - self.last_capture_time >= 0.20:
                self.last_capture_time = now
                self.record_sample()

        # Resize for canvas display
        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_frame)
        img = img.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
        self.photo_image = ImageTk.PhotoImage(image=img)

        self.video_canvas.delete("all")
        self.video_canvas.create_image(0, 0, anchor="nw", image=self.photo_image)

        # Schedule next frame update (approx 30 FPS)
        self.after(30, self.update_frame)

    def start_sample_capture(self):
        """Validates input, checks database, and starts burst face capture."""
        person_id = self.entries["person_id"].get().strip()
        name = self.entries["name"].get().strip()
        phone = self.entries["phone"].get().strip()
        email = self.entries["email"].get().strip()

        # Validate form inputs
        is_valid, err_msg = validate_person_input(person_id, name, phone, email)
        if not is_valid:
            messagebox.showwarning("Validation Error", err_msg)
            return

        if not self.consent_var.get():
            messagebox.showwarning(
                "Consent Required",
                "You must check the Privacy and Consent checkbox before capturing facial data."
            )
            return

        # Check if ID already exists
        if database.person_exists(person_id):
            messagebox.showerror(
                "Duplicate ID",
                f"A person with ID '{person_id}' is already registered in the system.\nPlease use a unique ID."
            )
            return

        if not self.is_camera_running:
            messagebox.showwarning("Camera Offline", "Please start the camera first.")
            return

        # Reset counters and initiate burst mode
        self.captured_count = 0
        self.progress_bar["value"] = 0
        self.lbl_samples.config(text=f"Samples: 0 / {self.target_samples}")
        self.is_capturing_samples = True
        self.btn_capture.config(state="disabled")
        self.lbl_cam_status.config(
            text="Capturing Face Samples... Look slightly left, right, and center.",
            foreground="#3b82f6"
        )

    def record_sample(self):
        """Saves a single face crop from the current frame."""
        person_id = self.entries["person_id"].get().strip()
        if self.current_frame_bgr is None or self.current_face_box is None:
            return

        self.captured_count += 1
        face_manager.save_face_sample(
            self.current_frame_bgr,
            self.current_face_box,
            person_id,
            self.captured_count
        )

        self.progress_bar["value"] = self.captured_count
        self.lbl_samples.config(text=f"Samples: {self.captured_count} / {self.target_samples}")

        # Check if target samples reached
        if self.captured_count >= self.target_samples:
            self.is_capturing_samples = False
            self.finalize_registration(person_id)

    def finalize_registration(self, person_id: str):
        """Saves person record to database and trains the face recognizer."""
        name = self.entries["name"].get().strip()
        father_name = self.entries["father_name"].get().strip()
        phone = self.entries["phone"].get().strip()
        department = self.entries["department"].get().strip()
        email = self.entries["email"].get().strip()
        face_data_path = str(DATASET_DIR / person_id)

        # Show saving status
        self.lbl_cam_status.config(text="Training Face Recognition Engine...", foreground="#8b5cf6")
        self.update_idletasks()

        # Run model training
        def train_and_save():
            success, msg = database.add_person(
                person_id=person_id,
                name=name,
                father_name=father_name,
                phone=phone,
                department=department,
                email=email,
                face_data=face_data_path
            )

            if not success:
                self.after(0, lambda: messagebox.showerror("Database Error", msg))
                self.after(0, self.reset_capture_ui)
                return

            # Retrain model
            train_ok, train_msg, count = face_manager.train_model()

            def on_complete():
                self.reset_capture_ui()
                if train_ok:
                    messagebox.showinfo(
                        "Registration Complete",
                        f"Successfully enrolled {name} ({person_id})!\n\n"
                        f"• Face samples captured: {self.target_samples}\n"
                        f"• Model Status: {train_msg}\n"
                        f"• Attendance can now be marked automatically via webcam."
                    )
                    self.clear_form()
                    # Refresh controller/dashboard stats if available
                    if hasattr(self.controller, "refresh_dashboard"):
                        self.controller.refresh_dashboard()
                else:
                    messagebox.showwarning(
                        "Registration Note",
                        f"Person registered in database, but model training returned: {train_msg}"
                    )

            self.after(0, on_complete)

        threading.Thread(target=train_and_save, daemon=True).start()

    def register_without_face(self):
        """Allows registering person info without capturing webcam face samples immediately."""
        person_id = self.entries["person_id"].get().strip()
        name = self.entries["name"].get().strip()
        father_name = self.entries["father_name"].get().strip()
        phone = self.entries["phone"].get().strip()
        department = self.entries["department"].get().strip()
        email = self.entries["email"].get().strip()

        is_valid, err_msg = validate_person_input(person_id, name, phone, email)
        if not is_valid:
            messagebox.showwarning("Validation Error", err_msg)
            return

        success, msg = database.add_person(
            person_id=person_id,
            name=name,
            father_name=father_name,
            phone=phone,
            department=department,
            email=email,
            face_data=""
        )

        if success:
            messagebox.showinfo(
                "Record Saved",
                f"Record for '{name}' ({person_id}) saved successfully.\n"
                "Note: Facial recognition will not identify this person until face samples are captured."
            )
            self.clear_form()
            if hasattr(self.controller, "refresh_dashboard"):
                self.controller.refresh_dashboard()
        else:
            messagebox.showerror("Error", msg)

    def reset_capture_ui(self):
        """Resets the capture progress bar and status label."""
        self.is_capturing_samples = False
        self.captured_count = 0
        self.progress_bar["value"] = 0
        self.lbl_samples.config(text=f"Samples: 0 / {self.target_samples}")
        if self.is_camera_running:
            self.lbl_cam_status.config(text="Status: Camera Active (Ready)", foreground="#10b981")
            self.update_capture_button_state()
        else:
            self.lbl_cam_status.config(text="Status: Camera Standby", foreground="#64748b")
            self.btn_capture.config(state="disabled")

    def clear_form(self):
        """Clears all input fields and resets the form."""
        for key, widget in self.entries.items():
            if isinstance(widget, ttk.Combobox):
                widget.set("Computer Science")
            else:
                widget.delete(0, tk.END)
        self.consent_var.set(False)
        self.reset_capture_ui()

    def on_page_leave(self):
        """Called when user switches tabs or navigates away; frees camera."""
        if self.is_camera_running:
            self.stop_camera()
