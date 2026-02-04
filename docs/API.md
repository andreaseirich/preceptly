# API Documentation – TutorFlow

## Overview

This documentation describes the endpoints and views of TutorFlow. Django-based views with JSON responses for API endpoints.

## Status

CRUD views and core features implemented. Django templates for UI; JSON for booking/search APIs.

## Implemented Views (Phase 3)

### Dashboard
- `GET /` - Dashboard with today's lessons, conflicts and income overview

### Student Management
- `GET /students/` - List of all students
- `GET /students/<id>/` - Student details
- `GET /students/create/` - Form to create
- `POST /students/create/` - Create new student
- `GET /students/<id>/update/` - Form to edit
- `POST /students/<id>/update/` - Update student
- `GET /students/<id>/delete/` - Confirmation page
- `POST /students/<id>/delete/` - Delete student

### Contract Management
- `GET /contracts/` - List of all contracts
- `GET /contracts/<id>/` - Contract details
- `GET /contracts/create/` - Form to create
- `POST /contracts/create/` - Create new contract
- `GET /contracts/<id>/update/` - Form to edit
- `POST /contracts/<id>/update/` - Update contract
- `GET /contracts/<id>/delete/` - Confirmation page
- `POST /contracts/<id>/delete/` - Delete contract

### Lesson Planning
- `GET /lessons/` - List of all lessons
- `GET /lessons/<id>/` - Lesson details (with conflicts)
- `GET /lessons/create/` - Form to create
- `POST /lessons/create/` - Create new lesson (with conflict detection)
- `GET /lessons/<id>/update/` - Form to edit
- `POST /lessons/<id>/update/` - Update lesson (with conflict detection)
- `GET /lessons/<id>/delete/` - Confirmation page
- `POST /lessons/<id>/delete/` - Delete lesson
- `GET /lessons/month/<year>/<month>/` - Month view of all lessons
- `GET /lessons/calendar/` - Monthly calendar view (redirects to week view)
- `GET /lessons/week/` - Interactive week view (Monday-Sunday, 08:00-22:00) - **Default calendar view**
- `GET /lessons/week/?year=<year>&month=<month>&day=<day>` - Week view for specific week
- **Click behavior**: Click on lesson block opens lesson plan view; click on edit icon (✏️) opens lesson edit form

### Lesson Plans
- `GET /lesson-plans/lessons/<lesson_id>/` - Lesson plan view (display/create AI lesson plans)
- **Note**: Clicking on a lesson in the week view opens this view. Premium users can generate AI lesson plans here.

### Recurring Lessons
- `GET /lessons/recurring/` - List of all recurring lessons
- `GET /lessons/recurring/<id>/` - Recurring lesson details (with preview)
- `GET /lessons/recurring/create/` - Form to create
- `POST /lessons/recurring/create/` - Create new recurring lesson
- `GET /lessons/recurring/<id>/update/` - Form to edit
- `POST /lessons/recurring/<id>/update/` - Update recurring lesson
- `GET /lessons/recurring/<id>/delete/` - Confirmation page
- `POST /lessons/recurring/<id>/delete/` - Delete recurring lesson
- `POST /lessons/recurring/<id>/generate/` - Generate lessons from recurring lesson

### Blocked Times
- `GET /blocked-times/<id>/` - Blocked time details
- `GET /blocked-times/create/` - Form to create
- `POST /blocked-times/create/` - Create new blocked time
- `GET /blocked-times/<id>/update/` - Form to edit
- `POST /blocked-times/<id>/update/` - Update blocked time
- `GET /blocked-times/<id>/delete/` - Confirmation page
- `POST /blocked-times/<id>/delete/` - Delete blocked time

### Recurring Blocked Times
- `GET /blocked-times/recurring/<id>/` - Recurring blocked time details
- `GET /blocked-times/recurring/<id>/update/` - Form to edit
- `POST /blocked-times/recurring/<id>/update/` - Update recurring blocked time
- `GET /blocked-times/recurring/<id>/delete/` - Confirmation page
- `POST /blocked-times/recurring/<id>/delete/` - Delete recurring blocked time
- `POST /blocked-times/recurring/<id>/generate/` - Generate blocked times from recurring blocked time
- **Note**: Recurring blocked times can no longer be created directly from the UI. They are managed internally but have no visible creation button.

### Public Booking (student/parent self-service)
- `GET /lessons/public-booking/<tutor_token>/` - Public booking page
- `GET /lessons/public-booking/<tutor_token>/week/?year=&month=&day=` - Week data (JSON)
- `POST /lessons/public-booking/api/search-student/` - Search by name (JSON)
- `POST /lessons/public-booking/api/verify-student/` - Verify booking code (JSON)
- `POST /lessons/public-booking/api/create-student/` - Create new student (JSON)
- `POST /lessons/public-booking/api/book-lesson/` - Book lesson (multipart/form-data)
- `POST /lessons/public-booking/api/reschedule-lesson/` - Reschedule lesson (JSON)

### Contract Booking (with contract token)
- `GET /lessons/booking/<token>/` - Contract-specific booking page
- `GET /lessons/booking/<token>/week/` - Week data (JSON)

### Billing
- `GET /billing/` - List of all invoices
- `GET /billing/<id>/` - Invoice details
- `GET /billing/create/` - Form to create invoice
- `POST /billing/create/` - Create invoice from lessons
- `GET /billing/<id>/delete/` - Confirmation page
- `POST /billing/<id>/delete/` - Delete invoice (resets lesson status)
- `GET /billing/<id>/document/` - Invoice document (HTML)

### Income Evaluation
- `GET /income/` - Income overview (current month)
- `GET /income/?year=<year>&month=<month>` - Monthly income
- `GET /income/?year=<year>` - Yearly income with monthly breakdown

## Services

### LessonConflictService
- `calculate_time_block(lesson)`: Calculates total time block including travel times
- `check_conflicts(lesson)`: Checks conflicts with other lessons and blocked times
- `has_conflicts(lesson)`: Boolean check for conflicts

### ContractQuotaService
- `check_quota_conflict(lesson)`: Checks if lesson exceeds contract quota based on ContractMonthlyPlan
- Returns dict with conflict information if quota is exceeded

### LessonQueryService
- `get_lessons_for_month(year, month)`: Returns all lessons for a month
- `get_today_lessons()`: Returns today's lessons
- `get_upcoming_lessons(days=7)`: Returns upcoming lessons

### RecurringLessonService (apps.lessons.recurring_service)
- `generate_lessons(recurring_lesson, check_conflicts=True, dry_run=False)`: Generates lessons from a RecurringLesson template
- `preview_lessons(recurring_lesson)`: Returns preview of lessons to be created (without saving)

### RecurringBlockedTimeService (apps.blocked_times.recurring_service)
- `generate_blocked_times(recurring_blocked_time, check_conflicts=True, dry_run=False)`: Generates blocked times from a RecurringBlockedTime template
- `preview_blocked_times(recurring_blocked_time)`: Returns preview of blocked times to be created (without saving)

### CalendarService (apps.lessons.calendar_service)
- `get_calendar_data(year, month)`: Loads lessons and blocked times for a month and groups them by days

### WeekService (apps.lessons.week_service)
- `get_week_data(year, month, day)`: Loads lessons and blocked times for a week (Monday to Sunday) and groups them by days

### IncomeSelector (apps.core.selectors)
- `get_monthly_income(year, month, status='paid')`: Monthly income
- `get_yearly_income(year, status='paid')`: Yearly income
- `get_income_by_status(year=None, month=None)`: Income grouped by status
- `get_monthly_planned_vs_actual(year, month)`: Comparison of planned vs. actual units and income per month

### InvoiceService (apps.billing.services)
- `get_billable_lessons(period_start, period_end, contract_id=None)`: Returns all lessons available for billing
- `create_invoice_from_lessons(period_start, period_end, contract=None, institute=None, user=None)`: Creates invoice with invoice items from lessons; owner is set from user or derived from lessons
- `delete_invoice(invoice)`: Deletes invoice and resets lesson status to TAUGHT

## Planned Endpoints (Future)

### Student Management
- `GET /api/students/` - List of all students
- `POST /api/students/` - Create new student
- `GET /api/students/{id}/` - Student details
- `PUT /api/students/{id}/` - Update student
- `DELETE /api/students/{id}/` - Delete student

### Contract Management
- `GET /api/contracts/` - List of all contracts
- `POST /api/contracts/` - Create new contract
- `GET /api/contracts/{id}/` - Contract details
- `PUT /api/contracts/{id}/` - Update contract
- `DELETE /api/contracts/{id}/` - Delete contract

### Lesson Planning
- `GET /api/lessons/` - List of all lessons
- `POST /api/lessons/` - Create new lesson
- `GET /api/lessons/{id}/` - Lesson details
- `PUT /api/lessons/{id}/` - Update lesson
- `DELETE /api/lessons/{id}/` - Delete lesson

### Blocked Times
- `GET /api/blocked-times/` - List of all blocked times
- `POST /api/blocked-times/` - Create new blocked time
- `GET /api/blocked-times/{id}/` - Blocked time details
- `PUT /api/blocked-times/{id}/` - Update blocked time
- `DELETE /api/blocked-times/{id}/` - Delete blocked time

### Income Evaluation
- `GET /api/income/` - Income overview
- `GET /api/income/monthly/` - Monthly income
- `GET /api/income/yearly/` - Yearly income

### Premium Features (Phase 4)
- `POST /ai/lessons/<lesson_id>/generate-plan/` - Create AI-generated lesson plan (Premium users only)
  - Requires: Authentication + Premium status
  - Generates LessonPlan for the specified lesson
  - On errors: Error message, no retries

## Authentication

Authentication will be done via Django's authentication system. Details will be defined in later phases.

## Error Handling

API errors are returned in JSON format:

```json
{
  "error": "Error description",
  "code": "ERROR_CODE"
}
```

## Versioning

API versioning will be defined in later phases.
