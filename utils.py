"""
Utility functions and configuration constants for Face Recognition Attendance System.
Handles directory resolution, audio feedback, input validation, and date-time utilities.
"""

import os
import sys
import platform
import re
from pathlib import Path
from datetime import datetime

# Base Directory Resolution (dynamic and portable across systems)
BASE_DIR = Path(__file__).resolve().parent

# Dedicated Project Subdirectories
DATASET_DIR = BASE_DIR / "dataset"
ENCODINGS_DIR = BASE_DIR / "encodings"
REPORTS_DIR = BASE_DIR / "reports"
DATABASE_DIR = BASE_DIR / "database"
DB_PATH = DATABASE_DIR / "attendance.db"

# Ensure all directories exist
for directory in [DATASET_DIR, ENCODINGS_DIR, REPORTS_DIR, DATABASE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


def get_current_date() -> str:
    """Returns today's date formatted as YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def get_current_time() -> str:
    """Returns current time formatted as HH:MM:SS."""
    return datetime.now().strftime("%H:%M:%S")


def get_timestamp_string() -> str:
    """Returns formatted timestamp for report file naming."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def play_success_sound() -> None:
    """Plays an auditory feedback beep on successful attendance marking."""
    if platform.system() == "Windows":
        try:
            import winsound
            winsound.Beep(1200, 180)  # Frequency: 1200Hz, Duration: 180ms
        except Exception:
            pass


def play_warning_sound() -> None:
    """Plays a lower tone audio beep for warnings / duplicate attendance."""
    if platform.system() == "Windows":
        try:
            import winsound
            winsound.Beep(650, 220)  # Frequency: 650Hz, Duration: 220ms
        except Exception:
            pass


def validate_person_input(person_id: str, name: str, phone: str = "", email: str = "") -> tuple[bool, str]:
    """
    Validates user registration inputs.
    Returns (is_valid, error_message).
    """
    person_id = person_id.strip()
    name = name.strip()

    if not person_id:
        return False, "Person ID cannot be empty."

    # Allow alphanumeric characters, hyphens, and underscores in ID
    if not re.match(r"^[A-Za-z0-9_\-]+$", person_id):
        return False, "Person ID should only contain letters, numbers, hyphens (-), and underscores (_)."

    if not name:
        return False, "Full Name cannot be empty."

    if len(name) < 2:
        return False, "Full Name must be at least 2 characters long."

    if email.strip():
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_regex, email.strip()):
            return False, "Please enter a valid email address (e.g. user@example.com)."

    if phone.strip():
        # Clean phone numbers (digits, +, spaces, hyphens)
        clean_phone = re.sub(r"[\s\-\(\)\+]", "", phone)
        if not clean_phone.isdigit() or len(clean_phone) < 7:
            return False, "Please enter a valid phone number with at least 7 digits."

    return True, ""


def open_folder_in_explorer(folder_path: Path) -> None:
    """Opens a directory in Windows File Explorer or the default system file manager."""
    try:
        path_str = str(folder_path.resolve())
        if platform.system() == "Windows":
            os.startfile(path_str)
        elif platform.system() == "Darwin":
            import subprocess
            subprocess.run(["open", path_str], check=True)
        else:
            import subprocess
            subprocess.run(["xdg-open", path_str], check=True)
    except Exception as e:
        print(f"Error opening folder: {e}")
