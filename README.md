# 🎯 Face Recognition Attendance Management System

A complete, modern, and user-friendly **Face Recognition Attendance Management System** built with **Python**, **OpenCV**, **SQLite3**, **Tkinter**, and **Pandas**.

The system utilizes a webcam to automatically detect registered students or employees, verify their identity in real-time, and log attendance without duplicate entries on the same day.

---

## 🌟 Key Features

1. **Modern Tkinter Dashboard**
   - Live KPI cards: **Total Registered**, **Today's Attendance Logs**, **Present Today**, and **Absent Today**.
   - Quick action shortcuts to register, take attendance, view records, and generate reports.
   - Live real-time feed of today's attendance logs.

2. **Person Enrollment & Face Registration**
   - Captures **ID**, **Full Name**, **Father/Guardian Name**, **Phone Number**, **Department / Class**, and **Email**.
   - **Privacy & Consent Protection**: Built-in consent notice checkbox before facial data capture.
   - Embedded real-time webcam feed with face detection bounding box and burst-capture progress bar (15 calibrated face crops).
   - Dedicated `dataset/<person_id>/` folder structure.
   - Automatic training and encoding generation.

3. **Real-Time Facial Recognition & HUD**
   - High-performance face detection with Haar Cascade / DNN.
   - Dual-engine architecture:
     - **OpenCV LBPH Face Recognizer** (Fast, offline, 100% native on Windows with zero C++ compilation needed).
     - **`face_recognition` (dlib 128D)** supported seamlessly if installed.
   - Dynamic HUD bounding boxes:
     - 🟢 **Green Box**: Recognized registered individual.
     - 🔵 **Cyan / Teal Box**: Already marked present today (shows check-in timestamp).
     - 🔴 **Red Box**: Unrecognized individual ("Unknown Person").

4. **Duplicate Attendance Prevention & Audio Feedback**
   - Prevents duplicate attendance for the same person on the same date.
   - Emits a success chime/beep when attendance is verified.
   - Displays real-time session activity feed on the right panel.

5. **Attendance Records Management**
   - View, search, and filter all historical attendance records.
   - Instant search by Name or Person ID.
   - Filter by date (`YYYY-MM-DD` or "Today" quick button).
   - Filter by Department / Class.
   - Delete incorrect or unwanted records with confirmation.
   - Direct export of filtered records to Excel (`.xlsx`) and CSV (`.csv`).

6. **Comprehensive Analytics & Reports**
   - **Daily Attendance Report**: Complete roster of all registered people with **Present** (time) or **Absent** status and attendance percentage.
   - **Monthly Attendance Report**: Summarizes total working days, days present, and attendance rate (%) for each individual.
   - **Individual Attendance History**: Complete check-in timestamp logs for any selected person.
   - Direct export to **CSV** and **Microsoft Excel (.xlsx)** via Pandas and OpenPyXL.
   - "Open Reports Folder" shortcut button.

7. **Student & Employee Directory**
   - View all registered individuals.
   - Search by name, ID, or department.
   - **GDPR & Privacy Deletion**: Option to permanently delete a person's registration, which deletes their database entry, attendance logs, and all stored face dataset files, then immediately retrains the face model.

---

## 📁 Project Structure

```
attendance_system/
│
├── main.py                     # Main Tkinter application, modern theme & page router
├── database.py                 # SQLite3 schema, CRUD operations & analytical queries
├── face_recognition_module.py  # Dual-engine face detector, dataset trainer & HUD renderer
├── attendance.py               # Live webcam attendance scanner & live session feed
├── registration.py             # Enrollment form, privacy consent & burst face capture
├── records_view.py             # Attendance records & student/employee directory management
├── reports_view.py             # Interactive reporting tabs (Daily, Monthly, Individual)
├── reports.py                  # Pandas report generator & Excel/CSV exporter
├── utils.py                    # Path resolution, validation, audio beeps & helper tools
├── requirements.txt            # Python dependencies
├── README.md                   # Documentation and usage guide
│
├── dataset/                    # Stored facial image samples (dataset/<person_id>/)
├── encodings/                  # Trained classifier models & label maps
├── reports/                    # Exported Excel (.xlsx) and CSV (.csv) reports
└── database/
    └── attendance.db           # SQLite database
```

---

## 🚀 Getting Started

Follow these step-by-step instructions to set up and run the system on Windows.

### Prerequisites
- Python 3.9+ or Python 3.10+ (Python 3.11, 3.12, 3.13, 3.14 also supported)
- A connected USB webcam or built-in laptop camera

---

### 1. Create the Virtual Environment

Open PowerShell or Command Prompt in the project directory:

```powershell
python -m venv .venv
```

---

### 2. Activate the Virtual Environment on Windows

#### In PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```

> *Note: If PowerShell shows an `Execution_Policies` script error, run:*
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
> .\.venv\Scripts\Activate.ps1
> ```

#### In Command Prompt (cmd):
```cmd
.\.venv\Scripts\activate.bat
```

---

### 3. Install Dependencies

Install the required packages using `pip`:

```powershell
pip install -r requirements.txt
```

---

### 4. Run the Application

Launch the full application from PowerShell, Command Prompt, or VS Code:

```powershell
python main.py
```

---

### 5. Build an Executable (.exe) using PyInstaller

To package the entire project into a standalone Windows executable:

```powershell
pyinstaller --noconfirm --onedir --windowed --name "FaceAttendanceSystem" --add-data "haarcascade_frontalface_default.xml;." --add-data "database;database" --add-data "dataset;dataset" --add-data "encodings;encodings" --add-data "reports;reports" main.py
```

The resulting executable will be available in the `dist/FaceAttendanceSystem/` directory:
```
dist/FaceAttendanceSystem/FaceAttendanceSystem.exe
```

---

## 🔒 Security & Privacy Notice

- **Facial Biometric Data**: Face image crops are stored strictly in the local `dataset/` directory and are never uploaded to any remote or cloud server.
- **Explicit Consent**: A mandatory checkbox is enforced during person registration, ensuring compliance with privacy standards.
- **Right to Erasure**: Administrators can select any person in the **Students / Employees** tab and click **"Delete Person & Face Data"** to permanently erase their profile, all past attendance records, and all stored facial dataset images.

---

## 🛠 Troubleshooting

1. **Webcam Not Detected (`Camera Error`)**:
   - Ensure your webcam is plugged in and recognized in Windows Device Manager.
   - Check Windows Settings: `Settings > Privacy & Security > Camera` and ensure "Allow desktop apps to access your camera" is turned ON.
   - Close any other application (Zoom, Teams, Skype, or browser) that might currently be using the webcam.

2. **No Enrolled Faces Warning**:
   - Before taking attendance, navigate to **"Face Registration"**, fill out the form, accept the consent notice, and click **"Capture Face & Enroll Person"** to enroll at least one face.

3. **Database Location**:
   - The database is dynamically located at `database/attendance.db` relative to the application directory and is automatically initialized on the first run.
