# TutorFlow

[![CI Status](https://img.shields.io/badge/CI-Passing-brightgreen)](https://github.com/andreaseirich/tutorflow/actions)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-6.0-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![i18n](https://img.shields.io/badge/i18n-English%20%7C%20German-lightgrey.svg)](docs/ARCHITECTURE.md#internationalization-i18n)

**The productivity bridge for educators** – A comprehensive tutoring management system that eliminates administrative overhead and enables tutors to focus on teaching.

### 🎥 Demo Video

[![TutorFlow Demo](https://img.youtube.com/vi/YUsSuPgR1XQ/maxresdefault.jpg)](https://youtu.be/YUsSuPgR1XQ?si=P2ucdtZZjWFqePLB)

*Watch the full demo: [YouTube](https://youtu.be/YUsSuPgR1XQ?si=P2ucdtZZjWFqePLB)*

### 📸 Screenshots

| Dashboard | Week Calendar | Conflicts & Blocked Times | Invoice Generation |
|-----------|--------------|---------------------------|-------------------|
| ![Dashboard](docs/images/dashboard.png) | ![Week Calendar](docs/images/week_calendar.png) | ![Conflicts](docs/images/conflicts_and_blocktimes.png) | ![Invoice](docs/images/invoice_example.png) |

---

## Vision

### The Problem

Private tutors juggle multiple responsibilities: managing student schedules across different contracts, avoiding double bookings, tracking income, and creating lesson plans. This administrative overhead consumes 2–3 hours per week, pulling focus away from what matters most—teaching.

Existing tools are either too simple (generic calendars that ignore contract quotas and travel times) or too complex (full CRM systems with unnecessary features). Tutors need a purpose-built solution that understands their unique workflow.

### The Solution

TutorFlow is a domain-specific operating system for tutors that uniquely combines:
- **Intelligent conflict detection** (time overlaps, travel constraints, contract quotas)
- **Automated billing** with invoice generation from taught sessions
- **AI-assisted lesson planning** with privacy-first design
- **Contract-based quota management** ensuring compliance with student agreements

All integrated into a single, coherent workflow that saves tutors hours every week and prevents costly scheduling mistakes.

---

## Live Links

- 🚀 **[Live Application](https://tutorflow-production.up.railway.app/)** – Deployed on Railway
- 👨‍💻 **[Portfolio](https://andreaseirich.github.io/tutorflow.html)** – Project details and case study

**Demo Credentials:**
- Premium User: `demo_premium` / `demo123`
- Standard User: `demo_user` / `demo123`

---

## Feature Highlights

### 🎯 **Intelligent Conflict Detection**
Prevents double bookings by detecting time overlaps, travel constraints, and contract quota violations in real-time. Tutors never accidentally overcommit or miss scheduling conflicts.

### 💰 **Automated Billing & Income Tracking**
Generate invoices directly from taught sessions with automatic calculations based on contract rates. Track planned vs. actual income with monthly and yearly overviews for clear financial oversight.

### 🤖 **AI-Powered Lesson Planning** (Premium)
Generate structured lesson plans using LLM APIs with privacy-first design—PII sanitization ensures student data never leaves the system. Human-in-the-loop editing ensures accountability and quality.

---

## Technical Overview

### Tech Stack

**Backend:**
- **Framework**: Django 6.0 (Python 3.12+)
- **Database**: PostgreSQL (production), SQLite (development)
- **Architecture**: Service layer pattern with clear separation of concerns
- **API**: RESTful endpoints with JSON responses

**Frontend:**
- Django Templates with vanilla JavaScript
- Responsive design with mobile support
- Progressive Web App (PWA) capabilities
- Dark mode support

**AI Integration:**
- OpenAI-compatible LLM API
- Privacy-first design with PII sanitization
- Mock mode for deterministic demos (`MOCK_LLM=1`)

**DevOps & Quality:**
- CI/CD with GitHub Actions
- Code quality: `ruff` for linting and formatting
- Security: CodeQL scanning, Dependabot
- Internationalization: Full i18n support (English, German)

### Data Model

TutorFlow's core data model follows a clear hierarchy:

```
Students ←→ Contracts ←→ Sessions ←→ Invoices
    ↓           ↓            ↓
    └───────────┴────────────┘
         (Quota Management)
```

- **Students**: Contact information, school/grade, subjects
- **Contracts**: Rates, duration, contract period, monthly quotas
- **Sessions**: Date, time, duration, travel time, status (planned/taught)
- **Invoices**: Generated from taught sessions, tracks payment status

The system automatically enforces contract quotas, detects conflicts across all relationships, and generates invoices based on taught sessions.

---

## Quick Start

### One-Command Demo

```bash
./scripts/run_demo.sh
```

Creates `.env` from `.env.example` if missing, then starts the application with mocked AI (`MOCK_LLM=1`) and deterministic demo data. Access at `http://127.0.0.1:8000/`.

### Manual Setup

```bash
# Clone repository
git clone https://github.com/andreaseirich/tutorflow.git
cd tutorflow

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Setup database
cd backend
python manage.py migrate
python manage.py compilemessages

# Load demo data (optional)
python manage.py load_demo_data

# Start server
python manage.py runserver
```

### Pre-commit hook (optional)

To auto-fix ruff format and lint (including import sorting) before each commit:

```bash
git config core.hooksPath .githooks
```

---

## Project Status

TutorFlow is currently submitted to the **CodeCraze Hackathon** (November 15 – December 15, 2025), an open-innovation challenge focused on creativity, real-world impact, and technology.

**Current Status:**
- ✅ Core scheduling with conflict detection
- ✅ Contract-based quota management
- ✅ Automated billing and invoice generation
- ✅ AI-powered lesson planning (premium feature)
- ✅ Full internationalization (English, German)
- ✅ Production deployment on Railway
- ✅ Comprehensive test coverage
- ✅ Security best practices (CodeQL, Dependabot)

---

## Documentation

- **[Architecture](docs/ARCHITECTURE.md)** – Technical architecture and design decisions
- **[API Documentation](docs/API.md)** – API endpoints and usage
- **[Deployment Guide](docs/RAILWAY_DEPLOYMENT.md)** – Railway deployment instructions
- **[Ethics & Privacy](docs/ETHICS.md)** – Ethical guidelines and data protection principles

---

## License

This project is licensed under the Apache License 2.0 – see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Andreas Eirich

---

## Contact

For questions, suggestions, or security concerns, please create an issue in the repository or refer to [SECURITY.md](SECURITY.md) for vulnerability reporting.
