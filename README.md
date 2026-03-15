# NEURAX - AI-Powered Healthcare Management Platform

NEURAX is a full-stack healthcare management platform that connects patients, hospitals, and administrators. It features AI-powered medical assistance, cross-hospital data sharing, appointment management, and comprehensive medical record tracking.

## Features

### Patient Portal
- **Registration & Login** with unique Patient UID (PAT-XXXXXXXX)
- **AI Health Assistant** — chat with an AI medical assistant powered by Groq (LLaMA 3.3 70B) with 4 modes: general, symptoms, medication, and health
- **Symptom Classification** — AI-powered symptom-to-specialization mapping for smarter appointment booking
- **Appointment Booking** — search hospitals, pick a doctor, and book appointments
- **Medical History** — view all past diagnoses, prescriptions, and vitals across hospitals
- **Health Card PDF** — download a comprehensive health card with profile, appointments, and records
- **Notifications** — real-time updates on appointment status, new records, and more

### Hospital Dashboard
- **Appointment Management** — view, confirm, complete, or cancel patient appointments
- **Patient Records** — add diagnoses, prescriptions, vitals, and clinical notes
- **Cross-Hospital Access** — request and grant access to patient records across hospitals
- **Analytics Dashboard** — track total appointments, pending cases, today's schedule, unique patients, and weekly trends

### Admin Panel
- **System-wide Statistics** — monitor total hospitals, patients, and appointments
- **Hospital Directory** — view all registered hospitals with appointment metrics
- **Audit Logs** — full trail of user actions across the platform

## Tech Stack

| Layer        | Technology                              |
| ------------ | --------------------------------------- |
| Backend      | Flask, Flask-JWT-Extended, Flask-CORS   |
| Database     | MySQL                                   |
| AI           | Groq API (LLaMA 3.3 70B, LLaMA 3.1 8B)|
| Frontend     | HTML, CSS, JavaScript                   |
| PDF Reports  | ReportLab                               |
| Email        | SMTP (Gmail)                            |
| Location     | Google Places API                       |

## Prerequisites

- Python 3.8+
- MySQL Server
- Groq API Key
- Gmail App Password (for email features)
- Google Places API Key (optional, for hospital search)

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/neurax.git
   cd neurax
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate        # Linux/macOS
   venv\Scripts\activate           # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and fill in your credentials.

5. **Set up MySQL**

   Create the database:
   ```sql
   CREATE DATABASE neurax_db;
   ```
   Tables are created automatically on first run.

6. **Run the application**
   ```bash
   python app.py
   ```
   The app will be available at `http://localhost:5000`.

## Environment Variables

| Variable            | Description                    | Required |
| ------------------- | ------------------------------ | -------- |
| `JWT_SECRET_KEY`    | Secret key for JWT tokens      | Yes      |
| `GROQ_API_KEY`      | Groq API key for AI features   | Yes      |
| `GOOGLE_PLACES_KEY` | Google Places API key          | No       |
| `MAIL_EMAIL`        | Gmail address for sending mail | Yes      |
| `MAIL_PASSWORD`     | Gmail app password             | Yes      |
| `ADMIN_EMAIL`       | Admin login email              | No       |
| `ADMIN_PASSWORD`    | Admin login password           | No       |
| `DB_HOST`           | MySQL host                     | No       |
| `DB_USER`           | MySQL user                     | No       |
| `DB_PASSWORD`       | MySQL password                 | No       |
| `DB_NAME`           | MySQL database name            | No       |

## Project Structure

```
neurax/
├── app.py                 # Main application (routes, models, logic)
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable template
├── templates/             # Jinja2 HTML templates
│   ├── index.html         # Landing page
│   ├── auth.html          # Login / Registration
│   ├── patient.html       # Patient dashboard
│   ├── hospital.html      # Hospital dashboard
│   ├── admin.html         # Admin panel
│   └── branch.html        # Branch page
├── static/
│   ├── css/               # Stylesheets
│   ├── js/                # Client-side JavaScript
│   └── assets/            # Images and static assets
├── index.html
├── style.css
└── script.js
```

## API Overview

The platform exposes 46 REST API endpoints across four groups:

- **Auth** (`/api/auth/*`) — patient/hospital/admin login, registration, password reset
- **Patient** (`/api/patient/*`) — profile, appointments, medical history, notifications, AI chat
- **Hospital** (`/api/hospital/*`) — dashboard, appointments, patient records, cross-hospital access
- **Admin** (`/api/admin/*`) — statistics, hospital listing, audit logs

## License

This project is licensed under the MIT License.
