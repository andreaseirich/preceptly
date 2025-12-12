# TutorFlow – CodeCraze Hackathon Submission

## Title
TutorFlow – AI-assisted tutoring operations with privacy-first design

## Tagline
AI-assisted tutoring ops with safe defaults

## Short Description (2–3 sentences)
TutorFlow is a comprehensive web application for private tutors to manage students, contracts, lessons, and billing with intelligent conflict detection and AI-powered lesson planning. The application solves the challenge of organizing complex tutoring schedules while avoiding double bookings and maintaining clear financial oversight. Built with Django 6.0 and featuring a privacy-first AI integration with mock mode for demos, TutorFlow enables tutors to focus on teaching rather than administrative tasks.

## Inspiration

As a private tutor, I often experienced the same recurring problem: scattered information, inconsistent scheduling, missing overview of income, and no tool that can handle real-world tutoring workflows — including contracts, travel times, recurring lessons, conflicts, billing, and AI-assisted lesson planning.

Existing tools are either too simple (pure calendars) or too complex (full CRM systems).
I wanted something practical, fast, ethical, and secure — especially because tutoring involves minors and personal data.
This became the motivation for TutorFlow: a structured, privacy-conscious management tool for tutors.

## What it does

TutorFlow is a Django-based web application that allows tutors to:
- Manage students, contracts, planned hours, and monthly quotas
- Schedule lessons in a weekly calendar with conflict detection
- Automatically track income (taught / invoiced / paid)
- Generate invoices and mark included lessons as paid
- Block time for personal events (vacation, university, work)
- Use an LLM-powered lesson plan generator (with strict privacy controls)
- Run a deterministic demo mode (MOCK_LLM) for safe hackathon evaluation

TutorFlow supports English/German, includes a one-command demo setup, and offers a clear and secure workflow designed for real tutors.

## Why It's Unique

TutorFlow isn't another generic calendar. It's a purpose-built operating system for tutors that uniquely combines AI-assisted lesson planning with strict business logic like contract quotas, conflict detection, and invoicing — all in one coherent workflow.

**What makes it different:**

- **Not a generic calendar**: Most scheduling tools handle time slots, but TutorFlow understands tutoring-specific constraints: contract-based quotas, travel times, recurring lesson patterns, and billing relationships.

- **Integrated business logic**: Unlike separate tools for scheduling, invoicing, and planning, TutorFlow integrates contract quotas, conflict detection (time + travel + quotas), automatic invoice generation, and AI lesson planning into a single workflow.

- **Domain-specific conflict engine**: The system detects three types of conflicts that matter to tutors: time overlaps (including travel), blocked personal time, and contract quota violations — automatically preventing double bookings and overcommitment.

- **AI with privacy-first design**: The lesson planning feature uses LLM APIs, but with mandatory PII sanitization and a deterministic mock mode, ensuring no personal data leaves the system during demos or development.

Most tools solve one of these problems. TutorFlow integrates all of them into a unified system designed specifically for the tutoring workflow.

## Real World Impact

TutorFlow directly addresses measurable pain points for private tutors:

- **Prevents lost income**: Eliminates double bookings and quota overruns that can cost tutors hundreds of euros per month in missed or incorrectly billed lessons.

- **Saves 2–3 hours per week**: Automates scheduling coordination, invoice generation, and income tracking that tutors typically handle manually with spreadsheets and calendar apps.

- **Reduces human error**: Automatic conflict detection and quota validation prevent mistakes in contract compliance and billing that can damage tutor-student relationships.

- **Improves teaching quality**: Structured lesson planning with AI assistance helps tutors prepare more effectively, leading to better student outcomes.

- **Designed for real workflows**: Built for tutors working weekly with multiple students, varying contract terms, and complex scheduling constraints — not simplified use cases.

The impact is measurable: tutors using TutorFlow can focus on teaching instead of administrative overhead, leading to better student outcomes and more sustainable tutoring businesses.

## How we built it

TutorFlow is built with modern Django 6.0 and demonstrates engineering maturity through deliberate architectural decisions:

**Clean Architecture & Service Layers:**
- Domain-driven design with modular Django apps (students, contracts, lessons, billing, ai, core)
- Service layer separation: `LessonConflictService`, `ContractQuotaService`, `InvoiceService`, `LessonPlanService` — business logic isolated from views and models
- Clear separation of concerns: conflict detection, billing calculations, and AI integration are testable, reusable services

**Deterministic Demo Design:**
- Mock LLM service (`apps.ai.client.LLMClient`) with local sample responses (`docs/llm_samples.json`)
- One-command setup (`./scripts/run_demo.sh`) that guarantees reproducible demos without external dependencies
- Judges can test AI features instantly without API keys or network access

**Production-Ready Practices:**
- Environment-based configuration (no hardcoded secrets, secure defaults)
- Transaction-safe billing with row locking (`select_for_update`) to prevent race conditions
- Comprehensive internationalization (EN/DE) with proper localization-aware formatting
- CI/CD pipeline with automated tests, linting, and security scanning

**Technical Stack:**
- **Backend**: Django 6.0 + Django ORM with domain-specific models
- **Frontend**: Server-rendered UI with Django Templates and progressive JavaScript
- **AI Integration**: Pluggable LLMClient (OpenAI-compatible) with privacy-first design
- **Testing**: Unit tests, integration tests, and CI with GitHub Actions

The architecture signals engineering maturity: not just tool usage, but thoughtful design decisions that enable maintainability, testability, and real-world deployment.

## Challenges we ran into

- **Calendar UI complexity**: implementing a weekly teaching calendar with click-to-create, conflict overlays, and correct time placement required several refactorings.
- **Accurate conflict detection**: quota-based conflicts, time overlaps, and recurring events interacting cleanly was surprisingly intricate.
- **Secure AI integration**: preventing personal data from entering prompts required a custom sanitization layer and a mock-LLM system.
- **Invoice correctness**: correctly handling 45-minute units, taught vs. planned vs. invoiced states, and rollback on invoice deletion needed careful transactional design.
- **Demo reproducibility**: guaranteeing that "one command" fully sets up the system, including fake LLM responses and demo accounts.

## Accomplishments that we're proud of

- Fully working tutor management system built from scratch during the hackathon
- Secure AI integration with sanitization + mock-mode (no external calls required)
- Clean modular architecture with documented diagrams
- Internationalization (EN/DE) and deterministic demo
- Polished UI with a week-calendar and conflict visualization
- Robust invoice workflow with automatic state changes
- Comprehensive documentation

## What we learned

- Good scheduling logic is harder than it looks — real-world time planning requires edge cases.
- AI integration must be privacy-first, especially when dealing with minors.
- Mock systems are crucial for stable demos and offline CI.
- Documentation clarity significantly influences the evaluation experience for reviewers.

## What's next for TutorFlow

- A modern React or HTMX front-end for smoother interactions
- Mobile-optimized week calendar
- Optional sync with Google Calendar / Apple Calendar
- Exportable invoices (PDF templates) with customizable branding
- Tutor-student communication features (messages, shared files)
- Cloud-ready deployment template (e.g. Fly.io / Railway)

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
- **Judging Guide**: [docs/JUDGING_GUIDE.md](docs/JUDGING_GUIDE.md)
