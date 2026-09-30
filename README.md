# 🏥 Neurax

![Python Version](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Framework-Flask-green.svg)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-blue.svg)
![License](https://img.shields.io/badge/License-MIT-purple.svg)

**Neurax** is a comprehensive, AI-powered Healthcare Management System (HMS) designed to bridge the communication and data gap between hospitals, doctors, and patients. Built with Flask and PostgreSQL, Neurax provides secure Role-Based Access Control (RBAC) and modern medical data sharing capabilities.

## ✨ Key Features

- **🧑‍⚕️ Role-Based Access Control (RBAC):** Dedicated portals and secure JWT authentication for Patients, Hospitals, and Admins.
- **🏥 Cross-Hospital Access:** Securely request and grant access to patient medical records across different hospitals.
- **📅 Appointment Management:** Schedule, confirm, and track doctor appointments seamlessly.
- **💊 Electronic Medical Records (EMR):** Manage diagnoses, prescriptions, and patient vitals securely.
- **🤖 AI Health Assistant:** Integrated chat assistant (powered by Google Gemini) for patient queries.
- **🔔 Notifications & Alerts:** Real-time notifications for appointments and record access requests.
- **🔒 Security & Auditing:** Comprehensive audit logs, OTP-based password resets, and encrypted data storage.

## 🛠️ Technology Stack

- **Backend Framework:** Python / Flask
- **Database:** PostgreSQL (`psycopg2-binary`)
- **Authentication:** Flask-JWT-Extended
- **AI Integration:** Google Gemini (`google-generativeai`)
- **Other Utilities:** Geopy (location services), ReportLab (PDF generation), PyOTP (OTP generation).

## 📂 Project Structure

```text
neurax/
├── app.py                 # Application entry point & initialization
├── config.py              # Environment configuration & DB settings
├── database.py            # PostgreSQL schema initialization & RBAC decorators
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
- PostgreSQL Server running locally or in the cloud.

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
   Create a `.env` file in the root directory based on `.env.example` (e.g., PostgreSQL connection string, JWT Secret Key, Google Gemini API Key).

5. **Run the Application:**
   The database tables will be automatically initialized on the first run.
   ```bash
   python app.py
   ```
   *The server will start on `http://localhost:5000`.*

## ☁️ Deploy to Render (1-Click Blueprint)

1. Push your repository to GitHub.
2. Log in to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** > **Blueprint**.
4. Select this repository. Render will automatically read `render.yaml` and provision both the **PostgreSQL Database** and the **Web Service**.
5. Set `GEMINI_API_KEY` under Environment Variables.
6. Click **Apply** — Render automatically connects the database to the web service.
