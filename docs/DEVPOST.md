# TutorFlow – CodeCraze Hackathon Submission

## Title
TutorFlow – AI-assisted tutoring operations with privacy-first design

## Tagline
AI-assisted tutoring ops with safe defaults

## Short Description (2–3 sentences)
TutorFlow is a comprehensive web application for private tutors to manage students, contracts, lessons, and billing with intelligent conflict detection and AI-powered lesson planning. The application solves the challenge of organizing complex tutoring schedules while avoiding double bookings and maintaining clear financial oversight. Built with Django 6.0 and featuring a privacy-first AI integration with mock mode for demos, TutorFlow enables tutors to focus on teaching rather than administrative tasks.

## Inspiration

Private tutors face significant challenges in managing their business operations:
- **Overloaded schedules**: Juggling multiple students with varying schedules, contract terms, and lesson frequencies
- **Complex planning**: Avoiding scheduling conflicts while accounting for travel times, blocked personal time, and contract quotas
- **Income tracking**: Manually tracking planned vs. actual lessons, generating invoices, and maintaining financial clarity
- **Time management**: Balancing teaching, planning, and administrative work

TutorFlow was inspired by the real-world needs of tutors who need a structured, reliable tool to manage their teaching activities efficiently. The CodeCraze Hackathon's open-innovation focus allowed us to build a solution that addresses these practical challenges with modern technology and best practices.

## What it does

TutorFlow provides a complete solution for managing tutoring activities:

- **Intelligent Scheduling**: Interactive week view calendar with click-to-create appointments, automatic conflict detection (time overlaps, travel times, contract quotas), and recurring lesson support
- **Student & Contract Management**: Centralized management of students, contracts, and monthly planning with flexible contract structures
- **Billing & Income Tracking**: Automated invoice generation from lessons, monthly/yearly income overviews, and planned vs. actual comparisons
- **Blocked Time Management**: Personal appointment blocking (vacations, university, etc.) with multi-day and recurring support, fully integrated in calendar
- **AI-Powered Lesson Plans**: Premium feature for automatic generation of structured lesson plans using LLM APIs (OpenAI-compatible) with automatic retry on rate limits
- **Privacy-First AI**: Mock mode enabled by default (`MOCK_LLM=1`) for demos and CI; PII sanitization before any AI call; no prompt logs in demo mode
- **Full Internationalization**: Complete i18n/l10n support with English (default) and German, including proper date, number, and currency formatting

## How we built it

### Tech Stack
- **Backend**: Django 6.0 (Python 3.12+)
- **Database**: SQLite for development; PostgreSQL-ready for production (env-first via `DATABASE_URL`)
- **AI Integration**: OpenAI-compatible client with mock mode (`docs/llm_samples.json`) and local samples for offline/demo use
- **Frontend**: Django Templates with minimal JavaScript for calendar UI
- **Security**: Content Security Policy (CSP), environment-based configuration, PII sanitization
- **CI/CD**: GitHub Actions with `MOCK_LLM=1` enforcement, CodeQL security scanning, Ruff/Black linting

### Key Implementation Details

- **AI Layer with Mock/Safety**: `apps.ai.client.LLMClient` with mock mode, retry logic for rate limits, and clear error handling. `apps.ai.utils_safety.sanitize_context()` redacts PII before prompt creation.
- **Deterministic Demo**: `backend/fixtures/demo_data.json` for consistent demo data, `.env.example` for configuration, `scripts/run_demo.sh` for one-command startup.
- **Conflict Engine**: `LessonConflictService` detects time overlaps (including travel times), blocked time conflicts, and contract quota violations with automatic recalculation.
- **Billing System**: Transaction-safe invoice creation with row locking (`select_for_update`) to prevent race conditions.
- **CI Pipeline**: Automated tests, linting, formatting checks, and security scanning with `MOCK_LLM=1` to prevent external API calls.

## Challenges we ran into

- **Complex calendar & conflict logic**: Implementing deterministic conflict detection that accounts for travel times, recurring lessons, and contract quotas while maintaining performance
- **Correct quotas, billing, and recurring lessons**: Ensuring accurate unit-based billing calculations and proper handling of recurring lesson generation
- **PII-safe AI prompts + MOCK_LLM**: Designing a privacy-first AI integration that sanitizes sensitive data before prompting and provides deterministic mock responses for demos
- **Timezone + UI consistency**: Handling timezone conversions for blocked times while maintaining consistent UI behavior across different views
- **Deterministic demos**: Creating reproducible demo scenarios that work consistently for judges without external dependencies

## Accomplishments that we're proud of

- **Single-command demo with deterministic data**: `./scripts/run_demo.sh` starts the entire application with fixtures, migrations, and mock AI in under 60 seconds
- **Strong documentation and architecture**: Comprehensive documentation (README, ARCHITECTURE, SECURITY, DEPLOYMENT) with clear structure and best practices
- **AI integration with privacy-first design**: Mock mode by default, PII sanitization, no prompt logs in demo mode, and clear separation between demo and production modes
- **Clean, reproducible setup**: `.env.example`, deterministic fixtures, health endpoint (`/health/`), and smoke test script (`scripts/smoke_demo.sh`)
- **Security best practices**: CSP implementation, environment-based configuration, secure defaults, and comprehensive security documentation

## What we learned

- **Building production-like systems in a hackathon timeframe**: Balancing feature completeness with code quality, documentation, and security best practices
- **Balancing UX, complexity and correctness**: Designing intuitive interfaces while maintaining accurate business logic (conflict detection, billing calculations)
- **Designing safe AI integrations**: Implementing mock mode, PII sanitization, and deterministic responses to enable safe demos without external dependencies
- **Django best practices**: Service layer architecture, transaction safety, environment-based configuration, and comprehensive testing

## What's next for TutorFlow

- **Possible SaaS or open-source adoption**: Making TutorFlow available to tutors as a hosted service or open-source project
- **Extending analytics**: More detailed financial reports, student progress tracking, and performance metrics
- **Multi-user access**: Support for multiple tutors or tutoring organizations with role-based access control
- **Multi-timezone support**: Explicit timezone handling for tutors working across different regions
- **Deeper AI features**: Adaptive learning plans, personalized recommendations, and integration with educational content providers

## Hackathon Context

TutorFlow is submitted to the **CodeCraze Hackathon** (November 15 – December 15, 2025), an open-innovation challenge with no fixed theme. Projects are evaluated based on:
- **Uniqueness of the Idea**: How creative and original the solution is
- **Real World Impact**: The practical value and potential adoption of the solution
- **Technologies Used**: The technical sophistication and appropriate use of modern tools

TutorFlow addresses all three criteria by solving a real problem with modern technology and a privacy-first approach.

## How to run the demo

```bash
cp .env.example .env
./scripts/run_demo.sh
```

- Opens at `http://127.0.0.1:8000/` (health check: `curl http://127.0.0.1:8000/health/` → `{"status": "ok"}`)
- Demo logins: `demo_premium` / `demo123` (premium), `demo_user` / `demo123` (standard)
- AI responses are mocked (`MOCK_LLM=1`); no external network calls required

## Links

- **Repository**: https://github.com/andreaseirich/tutorflow
- **Video Script**: [docs/VIDEO_SCRIPT.md](docs/VIDEO_SCRIPT.md)
- **Judging Guide**: [docs/JUDGING_GUIDE.md](docs/JUDGING_GUIDE.md)
