# 🏥 Neurax

![Python Version](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Framework-Flask-green.svg)
![MySQL](https://img.shields.io/badge/Database-MySQL-orange.svg)
![License](https://img.shields.io/badge/License-MIT-purple.svg)

**Neurax** is a comprehensive, AI-powered Healthcare Management System (HMS) designed to bridge the communication and data gap between hospitals, doctors, and patients. Built with Flask and MySQL, Neurax provides secure Role-Based Access Control (RBAC) and modern medical data sharing capabilities.

## ✨ Key Features

- **🧑‍⚕️ Role-Based Access Control (RBAC):** Dedicated portals and secure JWT authentication for Patients, Hospitals, and Admins.
- **🏥 Cross-Hospital Access:** Securely request and grant access to patient medical records across different hospitals.
- **📅 Appointment Management:** Schedule, confirm, and track doctor appointments seamlessly.
- **💊 Electronic Medical Records (EMR):** Manage diagnoses, prescriptions, and patient vitals securely.
- **🤖 AI Health Assistant:** Integrated chat assistant (powered by Google GenAI) for patient queries.
- **🔔 Notifications & Alerts:** Real-time notifications for appointments and record access requests.
- **🔒 Security & Auditing:** Comprehensive audit logs, OTP-based password resets, and encrypted data storage.

## 🛠️ Technology Stack

- **Backend Framework:** Python / Flask
- **Database:** MySQL
- **Authentication:** Flask-JWT-Extended
- **AI Integration:** Google GenAI (`google-genai`)
- **Other Utilities:** Geopy (location services), ReportLab (PDF generation), PyOTP (OTP generation).

## 📂 Project Structure

```text
neurax/
├── app.py                 # Application entry point & initialization
├── config.py              # Environment configuration & DB settings
├── database.py            # MySQL schema initialization & RBAC decorators
├── routes/                # API Endpoints (Auth, Patients, Hospitals)
├── services/              # Core business logic
├── static/                # CSS, JS, and Images
├── templates/             # HTML Templates (Jinja2)
├── utils/                 # Helper functions (PDF, Email, OTP)
└── requirements.txt       # Project dependencies
```

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- MySQL Server running locally or remotely.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/vikaskarnati/Neurax.git
   cd Neurax
   ```

2. **Set up a virtual environment:**
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Mac/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Setup:**
   Create a `.env` file in the root directory based on the configuration required in `config.py` (e.g., MySQL connection string, JWT Secret Key, Google GenAI API Key).

5. **Run the Application:**
   The database tables will be automatically initialized on the first run.
   ```bash
   python app.py
   ```
   *The server will start on `http://localhost:5000`.*
