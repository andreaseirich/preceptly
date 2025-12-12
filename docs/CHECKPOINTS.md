# Checkpoints – TutorFlow

## Checkpoint System

This document logs the project's progress and important milestones.

---

## Checkpoint 1: Project Start

**Date**: 2025-12-04

**Phase**: Phase 1 – Project Setup & Architecture Foundations

**Status**: ✅ In Progress

### Completed
- ✅ Basic project structure created (backend/, docs/, scripts/)
- ✅ Django project initialized (Django 5.2.9)
- ✅ Virtual environment created
- ✅ requirements.txt created
- ✅ Documentation created:
  - README.md
  - docs/ARCHITECTURE.md
  - docs/ETHICS.md
  - docs/PHASES.md
  - docs/CHECKPOINTS.md
  - docs/API.md (placeholder)
- ✅ CHANGELOG.md created

### Open ToDos
- [x] Run Django smoke tests (`python manage.py check`)
- [x] Start and test development server
- [x] Create git commits
- [x] Validate structure

### Next Steps
1. ✅ Validation performed
2. ✅ Git commits created
3. ⏳ Complete Phase 1 (push to main branch)

---

## Checkpoint 6: Hackathon-Ready Documentation & Quality Assurance

**Date**: 2025-12-04

**Phase**: Phase 5 – Polishing, Validation & Hackathon Refinement

**Status**: ✅ Completed

### Completed
- ✅ **Documentation**: All public-facing documentation rewritten in English
  - README.md: Enhanced with screenshot section and 2-minute demo tour
  - ARCHITECTURE.md: German section headers translated to English
  - All docs (PHASES, CHECKPOINTS, ETHICS, DEPLOYMENT, DEVPOST) verified for English consistency
  - Documentation adapted for CodeCraze Hackathon submission
- ✅ **Code Quality**: Linting and formatting configuration added
  - `pyproject.toml` with ruff and black configuration
  - `scripts/lint.sh` for automated code quality checks
- ✅ **CI/CD**: GitHub Actions workflow implemented
  - Automated testing on push/pull request
  - Code formatting and linting checks
  - Django system check
- ✅ **Screenshot Structure**: Placeholder structure created in `docs/images/`

### Validation Results

#### Documentation
- [x] All public docs in English
- [x] Screenshot section prepared
- [x] Demo tour documented

#### Code Quality
- [x] Linting configuration added
- [x] CI pipeline functional
- [x] Code style guidelines documented

### Next Steps
1. Add actual screenshots to `docs/images/`
2. Continue development with quality checks in place

---

## Checkpoint 7: Mock-First Demo & Privacy

**Date**: 2025-12-08

**Phase**: Phase 5 – Polishing, Validation & Hackathon Refinement

**Status**: ✅ Completed

### Completed
- ✅ One-command demo (`.env.example` + `scripts/run_demo.sh`) with deterministic fixtures
- ✅ LLM mock mode default (`MOCK_LLM=1`) with `docs/llm_samples.json` and tests
- ✅ PII sanitizer before prompt creation; prompts rebuilt to use sanitized context
- ✅ Health endpoint `/health/` + smoke script; CI exports `MOCK_LLM=1`
- ✅ Docs updated (README, DEVPOST, SECURITY, ARCHITECTURE) to reflect mock mode and privacy

### Validation
- [x] Demo runs offline with mocked AI responses
- [x] Fixtures load deterministically
- [x] `/health/` returns 200
- [x] Tests cover mock mode and sanitizer (CI enforces MOCK_LLM)

---

## Validation Results

### Structure Check
- [x] All folders present (backend/, docs/, scripts/)
- [x] Django project correctly initialized
- [x] Documentation complete (README, ARCHITECTURE, ETHICS, PHASES, CHECKPOINTS, API)

### Django Checks
- [x] `python manage.py check` successful (0 issues)
- [x] Development server starts (port test performed)
- [x] No critical errors

### Git Commits
- [x] `.gitignore` added
- [x] Documentation committed
- [x] Django project committed
- [x] Basic structure committed

---

## Notes

- Django 5.2.9 is the latest stable version
- Project structure follows the master prompt guidelines
- Documentation oriented to ethical guidelines

---

## Checkpoint 2: Domain Models Implemented

**Date**: 2025-12-04

**Phase**: Phase 2 – Domain Data Model & Migrations

**Status**: ✅ Completed

### Completed
- ✅ 7 Django apps created (locations, students, contracts, lessons, blocked_times, lesson_plans, core)
- ✅ All domain models implemented:
  - Location (with optional coordinates)
  - Student (with contact data, school, subjects)
  - Contract (with fee, duration, contract period)
  - Lesson (with status, travel times)
  - BlockedTime (for personal appointments)
  - LessonPlan (for AI-generated plans)
  - UserProfile (premium flag)
- ✅ IncomeSelector implemented as service layer
- ✅ Admin interfaces for all models
- ✅ Migrations created and executed
- ✅ 14 unit tests written and successful

### Validation Results

#### Model Validation
- [x] All models have correct fields
- [x] Relationships correctly defined (ForeignKeys, OneToOne)
- [x] __str__ methods implemented
- [x] Meta options (ordering, verbose_name) set
- [x] Indexes for performant queries

#### Migrations
- [x] Migrations created for all apps
- [x] Migrations executed successfully
- [x] No errors with `python manage.py check`

#### Tests
- [x] 14 tests implemented
- [x] All tests run successfully
- [x] Tests cover CRUD, relationships and income calculation

#### Documentation
- [x] ARCHITECTURE.md updated with data model details
- [x] PHASES.md updated (Phase 2 marked as completed)
- [x] CHECKPOINTS.md updated

### Next Steps
1. ✅ Git commits created
2. ✅ Phase 2 completed
3. ✅ Phase 3 completed

---

## Checkpoint 3: Core Features Implemented

**Date**: 2025-12-04

**Phase**: Phase 3 – Core Features (Planning & Income)

**Status**: ✅ Completed

### Completed
- ✅ CRUD functions for all core entities:
  - Student (List, Detail, Create, Update, Delete)
  - Contract (List, Detail, Create, Update, Delete)
  - Lesson (List, Detail, Create, Update, Delete, Month View)
  - BlockedTime (List, Detail, Create, Update, Delete)
  - Location (List, Detail, Create, Update, Delete)
- ✅ Conflict detection implemented:
  - LessonConflictService for time block calculation and conflict detection
  - Consideration of travel times
  - Integration of blocked times
  - Conflict marking in UI
- ✅ Planning logic:
  - LessonQueryService for queries (month, today, upcoming)
  - Month view for lessons
- ✅ Income overview:
  - Dashboard with current income
  - IncomeOverview view with monthly/yearly view
  - Use of IncomeSelector
- ✅ Basic UI:
  - Navigation between all areas
  - Dashboard with overview
  - Simple templates for all CRUD operations
- ✅ Tests:
  - 7 new tests for services and conflict detection
  - All tests run successfully

### Validation Results

#### Code Quality
- [x] Services modularly separated (services.py, selectors.py)
- [x] Views separated into separate files
- [x] No file over 300 lines
- [x] Django check successful (0 issues)

#### Functionality
- [x] CRUD for all entities works
- [x] Conflict detection correctly recognizes overlaps
- [x] Travel times are considered in conflict detection
- [x] Blocked times are recognized
- [x] Income calculation works correctly

#### Tests
- [x] 7 new tests implemented
- [x] All tests run successfully
- [x] Tests cover conflict detection, services and queries

#### Documentation
- [x] ARCHITECTURE.md updated (conflict logic, income calculation)
- [x] API.md updated (implemented views documented)
- [x] PHASES.md updated (Phase 3 marked as completed)
- [x] CHECKPOINTS.md updated

### Next Steps
1. Create git commits
2. Complete Phase 3
3. Prepare Phase 4 (Premium & AI Features)

---

## Checkpoint 5: Polishing, Validation & Hackathon Refinement

**Date**: 2025-12-04

**Phase**: Phase 5 – Polishing, Validation & Hackathon Refinement

**Status**: ✅ Completed

### Completed
- ✅ UI/UX polishing: Templates improved, consistent navigation, clear conflict display, premium badges
- ✅ Demo/Seed data: Management command `seed_demo_data` created
  - 3 demo students with different profiles
  - Associated contracts (private and via institute)
  - Multiple lessons (including one conflict for demonstration)
  - Blocked times
  - 1 premium user with generated lesson plan
- ✅ Validation script: `scripts/validate.sh` created for automatic checks
- ✅ Documentation finalized:
  - README.md revised (demo data, validation)
  - ETHICS.md extended (demo data, privacy)
  - DEVPOST.md created (hackathon submission)
  - PHASES.md updated (Phase 5 completed)
- ✅ Code cleanup: No TODOs, no debug output, clean structure

### Validation Results

#### Functionality
- [x] UI is simple but clear and demo-ready
- [x] Reproducible demo scenario available
- [x] Validation script exists and runs
- [x] All tests run without errors

#### Documentation
- [x] README, ARCHITECTURE, ETHICS, API, PHASES, CHECKPOINTS, DEVPOST are current and consistent
- [x] Demo data documented
- [x] Validation script documented

#### Code Quality
- [x] No TODO comments in production code
- [x] No debug output (print, pdb)
- [x] Codebase appears clean, structured and comprehensible

### Next Steps
1. Phase 5 completed
2. Project ready for hackathon submission

---

## Date Correction Note

**Correction Date**: 2025-12-04

All originally documented dates with `2025-01-27` were corrected to the correct date `2025-12-04` (Europe/Berlin), as the original date did not match the actual project status.

---

## Checkpoint 4: Premium & AI Features Implemented

**Date**: 2025-12-04

**Phase**: Phase 4 – Premium & AI Features

**Status**: ✅ Completed

### Completed
- ✅ Premium logic fully integrated:
  - `apps.core.utils.is_premium_user()` for premium checks
  - UserProfile with premium flag manageable in admin
  - Premium gating in views and templates
- ✅ AI app structure created:
  - `apps.ai.client.LLMClient` - Low-level API communication
  - `apps.ai.prompts` - Prompt building for lesson plans
  - `apps.ai.services.LessonPlanService` - High-level generation
- ✅ LessonPlan generation:
  - Context collection (student, lesson, previous lessons)
  - Structured prompt building
  - LLM API integration (OpenAI-compatible)
  - Error handling (timeouts, network errors)
  - Storage as LessonPlan model
- ✅ Configuration:
  - LLM settings via environment variables (LLM_API_KEY, LLM_API_BASE_URL, LLM_MODEL_NAME)
  - No secrets in code
- ✅ UI integration:
  - Button "Generate lesson plan with AI" in lesson detail
  - Display of generated plans
  - Premium notice for non-premium users
- ✅ Tests:
  - 12 tests for premium gating, prompt building, services and client
  - Mock tests for LLM calls (no real API calls)
  - Error scenarios tested

### Validation Results

#### Code Quality
- [x] AI app modularly structured (client, prompts, services)
- [x] No file over 300 lines
- [x] Django check successful (0 issues)
- [x] API keys via ENV variables, no secrets in code

#### Functionality
- [x] Premium gating works correctly
- [x] LessonPlan generation possible for premium users
- [x] Error handling for LLM calls implemented
- [x] UI shows premium notices for non-premium users

#### Tests
- [x] 12 tests implemented
- [x] All tests run successfully
- [x] Mock tests for LLM (no real API calls)

#### Documentation
- [x] ARCHITECTURE.md updated (AI architecture documented)
- [x] ETHICS.md updated (AI usage, privacy, Human-in-the-Loop)
- [x] API.md updated (premium endpoint documented)
- [x] PHASES.md updated (Phase 4 marked as completed)
- [x] CHECKPOINTS.md updated

### Next Steps
1. Create git commits
2. Complete Phase 4
3. Prepare Phase 5 (Polishing & Hackathon Refinement)

---

## Checkpoint 6: Monthly Contract Planning Implemented

**Date**: 2025-12-04

**Phase**: Phase 6 – Monthly Contract Planning

**Status**: ✅ Completed

### Completed
- ✅ ContractMonthlyPlan model created:
  - ForeignKey to Contract
  - Year, month, planned units
  - unique_together constraint (contract, year, month)
- ✅ Formset integration:
  - ContractMonthlyPlanFormSet for editing
  - Automatic generation of month rows when creating/editing
  - Handling of period changes (add new months, remove old ones)
- ✅ IncomeSelector extended:
  - New method `get_monthly_planned_vs_actual()`
  - Calculation of planned_units, planned_amount, actual_units, actual_amount
  - Difference calculation
- ✅ UI integration:
  - contract_form.html extended with formset display
  - income_overview.html extended with planned vs. actual comparison
- ✅ Tests:
  - 8 tests for ContractMonthlyPlan, generation and IncomeSelector comparison
  - All tests run successfully

### Validation Results

#### Functionality
- [x] ContractMonthlyPlan model works correctly
- [x] Automatic generation of monthly plans works
- [x] Formset integration in Create/Update views
- [x] IncomeSelector comparison works
- [x] UI shows planned vs. actual correctly

#### Tests
- [x] 8 tests implemented
- [x] All tests run successfully
- [x] Tests cover various scenarios (with/without plan, different distributions)

#### Documentation
- [x] ARCHITECTURE.md updated (ContractMonthlyPlan documented)
- [x] CHANGELOG.md updated (Version 0.6.0)
- [x] PHASES.md updated (Phase 6 documented)
- [x] CHECKPOINTS.md updated

### Next Steps
1. Phase 6 completed

---

## Checkpoint 7: Recurring Lessons and Calendar View Implemented

**Date**: 2025-12-04

**Phase**: Phase 7 – Recurring Lessons and Calendar View

**Status**: ✅ Completed

### Completed
- ✅ RecurringLesson model created:
  - Weekday selection (monday-sunday as boolean fields)
  - Period (start_date, end_date)
  - Optional location, travel times, notes
  - is_active flag
- ✅ RecurringLessonService implemented:
  - Generates lessons for all activated weekdays in the period
  - Skips already existing lessons
  - Optional conflict detection
  - Preview function without saving
- ✅ UI for recurring lessons:
  - CRUD views (List, Detail, Create, Update, Delete)
  - RecurringLessonForm with validation (at least one weekday)
  - Button to generate lessons
  - Preview of lessons to be created
- ✅ Calendar view:
  - CalendarService for grouping by days
  - CalendarView with month grid (7 columns: Mon-Sun)
  - Display of lessons with time and student
  - Conflict marking
  - Display of blocked times
  - Navigation between months
- ✅ Integration:
  - Calendar link in navigation
  - Generated lessons integrate seamlessly into existing logic
  - Individual lessons can still be edited independently
- ✅ Tests:
  - 8 tests for RecurringLesson, service and calendar
  - All tests run successfully

### Validation Results

#### Functionality
- [x] RecurringLesson model works correctly
- [x] Service generates lessons correctly for single/multiple weekdays
- [x] Service skips existing lessons
- [x] Service optionally checks conflicts
- [x] Calendar view shows lessons and blocked times correctly
- [x] Navigation between months works

#### Tests
- [x] 8 tests implemented
- [x] All tests run successfully
- [x] Tests cover various scenarios (single/multiple weekdays, contract boundaries, conflicts)

#### Documentation
- [x] ARCHITECTURE.md updated (RecurringLesson, CalendarService)
- [x] API.md updated (endpoints for recurring lessons and calendar)
- [x] PHASES.md updated (Phase 7 documented)
- [x] CHANGELOG.md updated (Version 0.7.0)

### Next Steps
1. Phase 7 completed

---

## Checkpoint 8: Calendar as Central UI and Recurring Lessons Integration

**Date**: 2025-12-04

**Phase**: Phase 7 – Recurring Lessons and Calendar View (Extension)

**Status**: ✅ Completed

### Completed
- ✅ **Calendar as central UI**:
  - Lesson list view removed from navigation (endpoints remain for API/debugging)
  - Calendar is now primary interface for lesson management
  - Click on day in calendar opens form to create with pre-filled date
  - Click on existing lesson opens edit form
  - Redirect back to calendar after Create/Update
- ✅ **Calendar shows only future lessons**:
  - Lessons in the past are no longer displayed in the calendar
  - Blocked times in the past are also hidden
  - Financial/income views continue to show all lessons (including past)
- ✅ **Recurring lessons better integrated**:
  - Button "Create recurring lesson" in calendar header
  - Link "Create recurring lesson" on contract detail page
  - Automatic generation of lessons after creating a RecurringLesson
  - Redirect to calendar after generation
  - Note in RecurringLesson form explains functionality
- ✅ **Tests**:
  - 3 new tests for calendar filtering (past lessons are hidden)
  - Tests for calendar integration (Create with date parameter, redirect)
  - All tests run successfully
- ✅ **Documentation**:
  - ARCHITECTURE.md: Calendar as central UI documented
  - README.md: Calendar view and recurring lessons mentioned
  - DEVPOST.md: Calendar and recurring lessons included in features
  - CHANGELOG.md: Version 0.7.1 documented

### Validation Results

#### Functionality
- [x] Calendar is central UI for lesson management
- [x] Navigation no longer shows lesson list view
- [x] Click on day opens Create form with date
- [x] Click on lesson opens Update form
- [x] Calendar shows only future/current lessons
- [x] Recurring lessons button visible in calendar
- [x] Recurring lessons link on contract detail page
- [x] Automatic generation after creation works

#### Tests
- [x] 3 new tests implemented
- [x] All tests run successfully
- [x] Tests cover filtering and integration

#### Documentation
- [x] ARCHITECTURE.md updated
- [x] README.md updated
- [x] DEVPOST.md updated
- [x] CHANGELOG.md updated

### Next Steps
1. Phase 7 fully completed

## Checkpoint 2025-12-09
- Security/Deployment hardening: env-first settings, secure defaults, pinned deps, entrypoint, CI, AI backoff, billing locking, timezone note.
