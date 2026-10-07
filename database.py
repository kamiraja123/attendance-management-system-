"""
Database module for Face Recognition Attendance Management System.
Handles SQLite initialization, CRUD operations for persons and attendance records,
and analytical queries for dashboards and reports.
"""

import sqlite3
from typing import Optional, List, Dict, Any, Tuple
from utils import DB_PATH, get_current_date, get_current_time


def get_db_connection() -> sqlite3.Connection:
    """Creates a new SQLite database connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Initializes the database tables if they do not exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Table: persons
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS persons (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                father_name TEXT,
                phone TEXT,
                department TEXT,
                email TEXT,
                face_data TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Table: attendance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id TEXT NOT NULL,
                name TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Present',
                FOREIGN KEY (person_id) REFERENCES persons (id) ON DELETE CASCADE
            )
        """)

        # Indexes for fast querying and filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_attendance_date 
            ON attendance(date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_attendance_person_date 
            ON attendance(person_id, date)
        """)

        conn.commit()


# ==========================================
# PERSON OPERATIONS
# ==========================================

def person_exists(person_id: str) -> bool:
    """Checks if a person with the given ID already exists."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM persons WHERE id = ?", (person_id.strip(),))
        return cursor.fetchone() is not None


def add_person(
    person_id: str,
    name: str,
    father_name: str = "",
    phone: str = "",
    department: str = "",
    email: str = "",
    face_data: str = ""
) -> Tuple[bool, str]:
    """Adds a new person to the database."""
    person_id = person_id.strip()
    name = name.strip()
    father_name = father_name.strip()
    phone = phone.strip()
    department = department.strip()
    email = email.strip()

    if person_exists(person_id):
        return False, f"Person with ID '{person_id}' is already registered."

    try:
        created_at = f"{get_current_date()} {get_current_time()}"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO persons (id, name, father_name, phone, department, email, face_data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (person_id, name, father_name, phone, department, email, face_data, created_at))
            conn.commit()
            return True, f"Person '{name}' registered successfully."
    except Exception as e:
        return False, f"Database error: {str(e)}"


def get_person(person_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single person record by their ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM persons WHERE id = ?", (person_id.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_persons(search_query: str = "") -> List[Dict[str, Any]]:
    """Retrieves all registered persons, optionally filtered by search string."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM persons"
        params = []
        if search_query.strip():
            query += " WHERE id LIKE ? OR name LIKE ? OR department LIKE ? OR phone LIKE ?"
            param = f"%{search_query.strip()}%"
            params.extend([param, param, param, param])
        query += " ORDER BY name COLLATE NOCASE ASC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def delete_person(person_id: str) -> Tuple[bool, str]:
    """Deletes a person and their attendance records via cascade."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM persons WHERE id = ?", (person_id.strip(),))
            conn.commit()
            return True, f"Person '{person_id}' and associated data deleted successfully."
    except Exception as e:
        return False, f"Failed to delete person: {str(e)}"


# ==========================================
# ATTENDANCE OPERATIONS
# ==========================================

def is_attendance_marked_today(person_id: str, date_str: Optional[str] = None) -> bool:
    """Checks if attendance has already been recorded for a person on a specific date."""
    if not date_str:
        date_str = get_current_date()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM attendance 
            WHERE person_id = ? AND date = ?
        """, (person_id.strip(), date_str))
        return cursor.fetchone() is not None


def mark_attendance(
    person_id: str,
    name: str,
    date_str: Optional[str] = None,
    time_str: Optional[str] = None,
    status: str = "Present"
) -> Tuple[bool, str]:
    """
    Records attendance for a person.
    Prevents duplicate entries on the same day.
    """
    person_id = person_id.strip()
    name = name.strip()
    if not date_str:
        date_str = get_current_date()
    if not time_str:
        time_str = get_current_time()

    if is_attendance_marked_today(person_id, date_str):
        return False, f"Attendance already recorded today for {name} ({person_id})."

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO attendance (person_id, name, date, time, status)
                VALUES (?, ?, ?, ?, ?)
            """, (person_id, name, date_str, time_str, status))
            conn.commit()
            return True, f"Attendance marked for {name} ({person_id}) at {time_str}."
    except Exception as e:
        return False, f"Database error marking attendance: {str(e)}"


def get_attendance_records(
    search_query: str = "",
    date_filter: str = "",
    department_filter: str = ""
) -> List[Dict[str, Any]]:
    """
    Retrieves attendance records with optional filtering by:
    - search query (name or ID)
    - date filter (YYYY-MM-DD)
    - department filter
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                a.attendance_id,
                a.person_id,
                a.name,
                p.department,
                a.date,
                a.time,
                a.status
            FROM attendance a
            LEFT JOIN persons p ON a.person_id = p.id
            WHERE 1=1
        """
        params = []

        if search_query.strip():
            query += " AND (a.name LIKE ? OR a.person_id LIKE ?)"
            term = f"%{search_query.strip()}%"
            params.extend([term, term])

        if date_filter.strip():
            query += " AND a.date = ?"
            params.append(date_filter.strip())

        if department_filter.strip() and department_filter != "All Departments":
            query += " AND p.department = ?"
            params.append(department_filter.strip())

        query += " ORDER BY a.date DESC, a.time DESC"

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def delete_attendance_record(attendance_id: int) -> Tuple[bool, str]:
    """Deletes an incorrect or unwanted attendance entry."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance WHERE attendance_id = ?", (attendance_id,))
            conn.commit()
            return True, "Attendance record deleted successfully."
    except Exception as e:
        return False, f"Failed to delete attendance record: {str(e)}"


# ==========================================
# DASHBOARD & ANALYTICS QUERIES
# ==========================================

def get_dashboard_stats(today_date: Optional[str] = None) -> Dict[str, int]:
    """
    Calculates summary metrics:
    - Total registered people
    - Today's attendance entries count
    - Present count (distinct people marked today)
    - Absent count (total registered - distinct present)
    """
    if not today_date:
        today_date = get_current_date()

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Total registered
        cursor.execute("SELECT COUNT(*) FROM persons")
        total_registered = cursor.fetchone()[0]

        # Present today (distinct persons)
        cursor.execute("""
            SELECT COUNT(DISTINCT person_id) 
            FROM attendance 
            WHERE date = ? AND status = 'Present'
        """, (today_date,))
        present_count = cursor.fetchone()[0]

        # Total attendance rows recorded today
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (today_date,))
        today_attendance = cursor.fetchone()[0]

        absent_count = max(0, total_registered - present_count)

        return {
            "total_registered": total_registered,
            "today_attendance": today_attendance,
            "present_count": present_count,
            "absent_count": absent_count
        }


def get_distinct_departments() -> List[str]:
    """Returns a list of all distinct departments registered in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT department FROM persons WHERE department IS NOT NULL AND department != '' ORDER BY department ASC")
        return [row[0] for row in cursor.fetchall()]


# Auto-initialize database on import
init_db()
