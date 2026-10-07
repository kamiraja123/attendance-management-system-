"""
Reports and Analytics Generation Module.
Leverages Pandas and OpenPyXL to generate, analyze, and export:
1. Daily Attendance Reports (all persons marked Present or Absent for a date)
2. Monthly Attendance Summaries (attendance counts and percentages per person)
3. Individual Attendance Logs (complete attendance history for a single person)
Supports exporting to CSV and formatted Microsoft Excel (.xlsx) files.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import pandas as pd

from utils import REPORTS_DIR, get_timestamp_string, get_current_date
from database import get_db_connection, get_all_persons


class ReportGenerator:
    """Generates attendance dataframes and exports to CSV/Excel."""

    @staticmethod
    def generate_daily_report(date_str: Optional[str] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Generates a daily attendance report for the specified date.
        Lists ALL registered persons and indicates whether they were 'Present' (with time) or 'Absent'.
        """
        if not date_str:
            date_str = get_current_date()

        with get_db_connection() as conn:
            # Get all persons
            query_persons = """
                SELECT id AS person_id, name, department, phone, email 
                FROM persons 
                ORDER BY department ASC, name ASC
            """
            df_persons = pd.read_sql_query(query_persons, conn)

            # Get attendance for that day
            query_att = """
                SELECT person_id, date, time, status 
                FROM attendance 
                WHERE date = ?
            """
            df_att = pd.read_sql_query(query_att, conn, params=[date_str])

        if df_persons.empty:
            empty_df = pd.DataFrame(columns=["Person ID", "Name", "Department", "Date", "Time", "Status", "Phone", "Email"])
            summary = {"date": date_str, "total": 0, "present": 0, "absent": 0, "rate": 0.0}
            return empty_df, summary

        # Merge persons with attendance
        merged = pd.merge(df_persons, df_att, on="person_id", how="left")
        merged["date"] = date_str
        merged["status"] = merged["status"].fillna("Absent")
        merged["time"] = merged["time"].fillna("---")

        total_enrolled = len(df_persons)
        present_count = len(merged[merged["status"] == "Present"])
        absent_count = total_enrolled - present_count
        rate = (present_count / total_enrolled * 100) if total_enrolled > 0 else 0.0

        # Rename columns for professional display
        result_df = merged[[
            "person_id", "name", "department", "date", "time", "status", "phone", "email"
        ]].rename(columns={
            "person_id": "Person ID",
            "name": "Full Name",
            "department": "Department",
            "date": "Date",
            "time": "Check-in Time",
            "status": "Attendance Status",
            "phone": "Phone Number",
            "email": "Email"
        })

        summary = {
            "date": date_str,
            "total": total_enrolled,
            "present": present_count,
            "absent": absent_count,
            "rate": round(rate, 1)
        }

        return result_df, summary

    @staticmethod
    def generate_monthly_report(year: int, month: int) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Generates a monthly attendance summary showing total present days for each registered person.
        """
        month_str = f"{year:04d}-{month:02d}"
        pattern = f"{month_str}-%"

        with get_db_connection() as conn:
            # Query all attendance records for the month
            query_att = """
                SELECT person_id, COUNT(DISTINCT date) as days_present
                FROM attendance
                WHERE date LIKE ? AND status = 'Present'
                GROUP BY person_id
            """
            df_counts = pd.read_sql_query(query_att, conn, params=[pattern])

            # Query all distinct dates in that month where attendance was taken
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT date) FROM attendance WHERE date LIKE ?", (pattern,))
            total_active_days = cursor.fetchone()[0] or 0

            # Query all persons
            query_persons = "SELECT id as person_id, name, department, email FROM persons ORDER BY name ASC"
            df_persons = pd.read_sql_query(query_persons, conn)

        if df_persons.empty:
            empty_df = pd.DataFrame(columns=["Person ID", "Name", "Department", "Days Present", "Active Days", "Attendance Rate %"])
            return empty_df, {"month": month_str, "total_persons": 0, "active_days": total_active_days}

        merged = pd.merge(df_persons, df_counts, on="person_id", how="left")
        merged["days_present"] = merged["days_present"].fillna(0).astype(int)
        merged["total_sessions"] = total_active_days

        if total_active_days > 0:
            merged["rate"] = (merged["days_present"] / total_active_days * 100).round(1)
        else:
            merged["rate"] = 0.0

        result_df = merged[[
            "person_id", "name", "department", "days_present", "total_sessions", "rate"
        ]].rename(columns={
            "person_id": "Person ID",
            "name": "Full Name",
            "department": "Department",
            "days_present": "Days Present",
            "total_sessions": "Total Working Days",
            "rate": "Attendance Rate (%)"
        })

        summary = {
            "month": month_str,
            "total_persons": len(df_persons),
            "active_days": total_active_days
        }

        return result_df, summary

    @staticmethod
    def generate_individual_report(person_id: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Generates individual attendance history for a single person.
        """
        person_id = person_id.strip()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM persons WHERE id = ?", (person_id,))
            person_row = cursor.fetchone()

            if not person_row:
                empty_df = pd.DataFrame(columns=["Date", "Time", "Status"])
                return empty_df, {"found": False}

            person_info = dict(person_row)

            query = """
                SELECT date, time, status
                FROM attendance
                WHERE person_id = ?
                ORDER BY date DESC, time DESC
            """
            df_logs = pd.read_sql_query(query, conn, params=[person_id])

        total_present = len(df_logs[df_logs["status"] == "Present"]) if not df_logs.empty else 0

        result_df = df_logs.rename(columns={
            "date": "Date",
            "time": "Time Marked",
            "status": "Status"
        })

        summary = {
            "found": True,
            "person": person_info,
            "total_present_days": total_present
        }

        return result_df, summary

    @staticmethod
    def export_dataframe(
        df: pd.DataFrame,
        filename_prefix: str,
        export_format: str = "xlsx",
        custom_filepath: Optional[str] = None
    ) -> Tuple[bool, str, Path]:
        """
        Exports DataFrame to either Excel (.xlsx) or CSV (.csv).
        Returns (success, message, saved_path).
        """
        if df.empty:
            return False, "Cannot export an empty report.", Path()

        timestamp = get_timestamp_string()
        if custom_filepath:
            target_path = Path(custom_filepath)
        else:
            filename = f"{filename_prefix}_{timestamp}.{export_format}"
            target_path = REPORTS_DIR / filename

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if export_format.lower() == "csv":
                df.to_csv(str(target_path), index=False, encoding="utf-8-sig")
            else:
                # Use openpyxl for clean Excel formatting
                with pd.ExcelWriter(str(target_path), engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="Attendance Report")
            return True, f"Report successfully exported to {target_path.name}", target_path
        except Exception as e:
            return False, f"Failed to export report: {str(e)}", target_path
