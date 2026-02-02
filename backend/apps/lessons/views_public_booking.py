"""
Views für öffentliche Buchungsseite (ohne Token).
"""

import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from apps.contracts.models import Contract
from apps.core.utils_booking import get_tutor_for_booking
from apps.lessons.booking_service import BookingService
from apps.lessons.models import Lesson, LessonDocument
from apps.lessons.throttle import is_public_booking_throttled, record_public_booking_attempt
from apps.students.booking_code_service import set_booking_code, verify_booking_code
from apps.students.models import Student
from apps.students.services import StudentSearchService
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView


@method_decorator(ensure_csrf_cookie, name="dispatch")
class PublicBookingView(TemplateView):
    """Öffentliche Buchungsseite ohne Token."""

    template_name = "lessons/public_booking.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tutor_token = self.kwargs.get("tutor_token")

        # Aktuelles Datum oder aus GET-Parameter
        try:
            year = int(self.request.GET.get("year", timezone.now().year))
            month = int(self.request.GET.get("month", timezone.now().month))
            day = int(self.request.GET.get("day", timezone.now().day))
            target_date = date(year, month, day)
        except (ValueError, TypeError):
            target_date = timezone.now().date()

        tutor = get_tutor_for_booking(tutor_token)
        if not tutor:
            raise Http404(
                _("Booking link invalid or expired. Please use the link shared by your tutor.")
            )

        student_id = None
        if self.request.session.get("public_booking_tutor_token") == tutor_token:
            student_id = self.request.session.get("public_booking_student_id")

        week_data = BookingService.get_public_booking_data(
            target_date.year, target_date.month, target_date.day, user=tutor, student_id=student_id
        )

        context.update(
            {
                "week_data": week_data,
                "current_date": target_date,
                "tutor_token": tutor_token or "",
            }
        )

        return context


def _serialize_public_week_data(week_data):
    """Serialize public booking week data to JSON-serializable dict."""

    def serialize_day(day_data):
        result = {
            "date": day_data["date"].strftime("%Y-%m-%d"),
            "weekday": day_data["weekday"],
            "weekday_display": day_data["weekday_display"],
            "working_hours": day_data["working_hours"],
            "available_slots": [
                [s[0].strftime("%H:%M"), s[1].strftime("%H:%M")]
                for s in day_data["available_slots"]
            ],
            "occupied_slots": [
                [s[0].strftime("%H:%M"), s[1].strftime("%H:%M")] for s in day_data["occupied_slots"]
            ],
            "busy_intervals": day_data.get("busy_intervals", []),
        }
        return result

    return {
        "week_start": week_data["week_start"].strftime("%Y-%m-%d"),
        "week_end": week_data["week_end"].strftime("%Y-%m-%d"),
        "unit_duration_minutes": week_data.get("unit_duration_minutes", 60),
        "days": [serialize_day(d) for d in week_data["days"]],
    }


@require_http_methods(["GET"])
def public_booking_week_api(request, tutor_token):
    """API for fetching public booking week data (for AJAX week navigation)."""
    tutor = get_tutor_for_booking(tutor_token)
    if not tutor:
        return JsonResponse(
            {"success": False, "message": _("Booking link invalid or expired.")}, status=404
        )

    try:
        year = int(request.GET.get("year", timezone.now().year))
        month = int(request.GET.get("month", timezone.now().month))
        day = int(request.GET.get("day", timezone.now().day))
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "message": _("Invalid date.")}, status=400)

    student_id = None
    if request.session.get("public_booking_tutor_token") == tutor_token:
        student_id = request.session.get("public_booking_student_id")

    week_data = BookingService.get_public_booking_data(
        year, month, day, user=tutor, student_id=student_id
    )
    data = _serialize_public_week_data(week_data)
    return JsonResponse({"success": True, "week_data": data})


_NEUTRAL_ERROR = _("Invalid name or code. Please try again.")


@csrf_exempt
@require_http_methods(["POST"])
def search_student_api(request):
    """
    Search for students by name (Public Booking step 1).
    Returns exact_match | suggestions | no_match. Stricty tutor-scoped, no sensitive data.
    """
    try:
        data = json.loads(request.body)
        name = (data.get("name") or "").strip()
        tutor_token = data.get("tutor_token")

        if not name:
            return JsonResponse(
                {"success": False, "message": _("Please enter a name.")}, status=400
            )

        tutor = get_tutor_for_booking(tutor_token)
        if not tutor:
            return JsonResponse(
                {"success": False, "message": _("Booking link invalid.")}, status=400
            )

        if is_public_booking_throttled(request, tutor_token):
            return JsonResponse({"success": False, "message": _("Too many attempts.")}, status=429)

        record_public_booking_attempt(request, tutor_token)

        exact_match, suggestions = StudentSearchService.search_for_public_booking(
            name, user=tutor, max_suggestions=10
        )

        if exact_match:
            return JsonResponse(
                {
                    "success": True,
                    "result": "exact_match",
                    "student": {"id": exact_match.id, "display_name": exact_match.full_name},
                }
            )
        if suggestions:
            return JsonResponse(
                {
                    "success": True,
                    "result": "suggestions",
                    "suggestions": [
                        {"id": s.id, "display_name": s.full_name} for s, _ in suggestions
                    ],
                }
            )
        return JsonResponse({"success": True, "result": "no_match", "suggestions": []})

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": _("Invalid request.")}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def verify_student_api(request):
    """
    Verify name + code for Public Booking. Never reveals if student exists.

    Returns student data only if both name and code are correct.
    Rate-limited by IP and tutor_token.
    """
    try:
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        code = data.get("code", "").strip()
        tutor_token = data.get("tutor_token")
        student_id = data.get("student_id")

        if not code:
            return JsonResponse(
                {"success": False, "message": _("Please enter the booking code.")}, status=400
            )

        tutor = get_tutor_for_booking(tutor_token)
        if not tutor:
            return JsonResponse({"success": False, "message": _NEUTRAL_ERROR}, status=400)

        if is_public_booking_throttled(request, tutor_token):
            return JsonResponse({"success": False, "message": _NEUTRAL_ERROR}, status=429)

        record_public_booking_attempt(request, tutor_token)

        if student_id:
            try:
                exact_match = Student.objects.get(pk=student_id, user=tutor)
            except (Student.DoesNotExist, ValueError, TypeError):
                exact_match = None
        elif name:
            exact_match = StudentSearchService.find_exact_match(name, user=tutor)
        else:
            exact_match = None

        if not exact_match or not verify_booking_code(exact_match, code):
            return JsonResponse({"success": False, "message": _NEUTRAL_ERROR}, status=400)

        if not exact_match.booking_code_hash:
            return JsonResponse({"success": False, "message": _NEUTRAL_ERROR}, status=400)

        request.session["public_booking_student_id"] = exact_match.id
        request.session["public_booking_tutor_token"] = tutor_token
        request.session.set_expiry(7200)

        return JsonResponse(
            {
                "success": True,
                "student": {
                    "id": exact_match.id,
                    "full_name": exact_match.full_name,
                    "email": exact_match.email or "",
                    "phone": exact_match.phone or "",
                },
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": _("Invalid request.")}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def create_student_api(request):
    """API for creating new students. Generates booking code; returned once."""
    try:
        data = json.loads(request.body)

        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()
        school = data.get("school", "").strip()
        grade = data.get("grade", "").strip()
        subjects = data.get("subjects", "").strip()
        tutor_token = data.get("tutor_token")

        if not first_name or not last_name:
            return JsonResponse(
                {"success": False, "message": _("First name and last name are required.")},
                status=400,
            )

        tutor = get_tutor_for_booking(tutor_token)
        if not tutor:
            return JsonResponse(
                {"success": False, "message": _("Booking is not available.")}, status=400
            )

        student = Student.objects.create(
            user=tutor,
            first_name=first_name,
            last_name=last_name,
            email=email if email else None,
            phone=phone if phone else None,
            school=school if school else None,
            grade=grade if grade else None,
            subjects=subjects if subjects else None,
        )

        new_code = set_booking_code(student)

        return JsonResponse(
            {
                "success": True,
                "message": _("Student created successfully."),
                "student": {
                    "id": student.id,
                    "full_name": student.full_name,
                    "email": student.email or "",
                    "phone": student.phone or "",
                },
                "booking_code": new_code,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": _("Invalid JSON data.")}, status=400)
    except Exception:
        return JsonResponse(
            {"success": False, "message": _("An error occurred. Please try again.")}, status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
def book_lesson_api(request):
    """API for booking a lesson. Requires valid student_id and booking_code."""
    try:
        if request.content_type and "application/json" in request.content_type:
            data = json.loads(request.body)
        else:
            data = request.POST

        student_id = data.get("student_id")
        booking_date = data.get("date")
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        subject = data.get("subject", "")
        if isinstance(subject, str):
            subject = subject.strip()
        else:
            subject = ""
        notes = data.get("notes", "")
        if isinstance(notes, str):
            notes = notes.strip()
        else:
            notes = ""
        institute = data.get("institute", "")
        if isinstance(institute, str):
            institute = institute.strip()
        else:
            institute = ""

        tutor_token = data.get("tutor_token")
        tutor = get_tutor_for_booking(tutor_token)
        if not tutor:
            return JsonResponse(
                {"success": False, "message": _("Booking is not available.")},
                status=400,
            )

        if not student_id:
            return JsonResponse(
                {"success": False, "message": _("Student ID is required.")}, status=400
            )

        booking_code = (data.get("booking_code") or "").strip()
        if not booking_code:
            return JsonResponse(
                {"success": False, "message": _("Booking code is required.")}, status=400
            )

        try:
            student = Student.objects.get(id=student_id, user=tutor)
        except Student.DoesNotExist:
            return JsonResponse({"success": False, "message": _("Student not found.")}, status=404)

        if not verify_booking_code(student, booking_code):
            return JsonResponse(
                {"success": False, "message": _("Invalid booking code.")}, status=400
            )

        if not booking_date or not start_time:
            return JsonResponse(
                {"success": False, "message": _("Date and start time are required.")}, status=400
            )

        try:
            booking_date_obj = datetime.strptime(booking_date, "%Y-%m-%d").date()
            start_time_obj = datetime.strptime(start_time, "%H:%M").time()
        except ValueError:
            return JsonResponse(
                {"success": False, "message": _("Invalid date or time format.")}, status=400
            )

        # Calculate end time
        if end_time:
            try:
                end_time_obj = datetime.strptime(end_time, "%H:%M").time()
            except ValueError:
                return JsonResponse(
                    {"success": False, "message": _("Invalid end time format.")}, status=400
                )
        else:
            # Fallback: 60 minutes
            end_time_obj = (
                datetime.combine(booking_date_obj, start_time_obj) + timedelta(minutes=60)
            ).time()

        # Validation: Check that start and end times are on 30-minute intervals
        start_minutes = start_time_obj.hour * 60 + start_time_obj.minute
        end_minutes = end_time_obj.hour * 60 + end_time_obj.minute

        if start_minutes % 30 != 0:
            return JsonResponse(
                {
                    "success": False,
                    "message": _("Start time must be on a 30-minute interval."),
                },
                status=400,
            )
        if end_minutes % 30 != 0:
            return JsonResponse(
                {
                    "success": False,
                    "message": _("End time must be on a 30-minute interval."),
                },
                status=400,
            )

        # Validation: Check that end time is after start time
        if end_time_obj <= start_time_obj:
            return JsonResponse(
                {"success": False, "message": _("End time must be after start time.")}, status=400
            )

        duration_total = end_minutes - start_minutes

        contract = (
            Contract.objects.filter(student=student, student__user=tutor, is_active=True)
            .order_by("-start_date")
            .first()
        )
        expected_duration = contract.unit_duration_minutes if contract else 60
        if duration_total != expected_duration:
            return JsonResponse(
                {"success": False, "message": _("Invalid booking duration.")}, status=400
            )

        # Validation: Check that appointment is not in the past
        # and is at least 30 minutes in the future
        booking_datetime = timezone.make_aware(datetime.combine(booking_date_obj, start_time_obj))
        min_booking_datetime = timezone.now() + timedelta(minutes=30)
        if booking_datetime < min_booking_datetime:
            return JsonResponse(
                {
                    "success": False,
                    "message": _(
                        "Bookings must be at least 30 minutes in advance. Past time slots cannot be booked."
                    ),
                },
                status=400,
            )

        # Check availability
        week_data = BookingService.get_public_booking_data(
            booking_date_obj.year,
            booking_date_obj.month,
            booking_date_obj.day,
            user=tutor,
        )

        # Find the day in week_data
        target_day = None
        for day_data in week_data["days"]:
            if day_data["date"] == booking_date_obj:
                target_day = day_data
                break

        if not target_day:
            return JsonResponse({"success": False, "message": _("Date not found.")}, status=400)

        # Check if slot is available
        occupied_slots = BookingService.get_all_occupied_time_slots(
            booking_date_obj, booking_date_obj, user=tutor
        )

        if not BookingService.is_time_slot_available(
            booking_date_obj, start_time_obj, end_time_obj, occupied_slots
        ):
            return JsonResponse(
                {"success": False, "message": _("Time slot is already booked.")}, status=400
            )

        # Find or create contract for this student (student belongs to tutor)
        contract = Contract.objects.filter(
            student=student, student__user=tutor, is_active=True
        ).first()

        if not contract:
            # Create new contract with hourly_rate=0.00 (to be set later by tutor)
            contract = Contract.objects.create(
                student=student,
                institute=institute if institute else None,
                hourly_rate=Decimal("0.00"),  # Price will be set later by tutor
                unit_duration_minutes=60,  # Default
                start_date=timezone.now().date(),
                is_active=True,
            )

        lesson = Lesson.objects.create(
            contract=contract,
            date=booking_date_obj,
            start_time=start_time_obj,
            duration_minutes=duration_total,
            status="planned",
            travel_time_before_minutes=0,
            travel_time_after_minutes=0,
            notes=f"{_('Subject')}: {subject}\n{notes}" if subject or notes else notes,
        )

        try:
            from apps.lessons.email_service import send_booking_notification

            send_booking_notification(lesson)
        except Exception:
            logging.getLogger(__name__).warning(
                "Booking notification failed", exc_info=True, extra={"lesson_id": lesson.id}
            )

        # Process document upload (if present)
        uploaded_documents = []
        if request.FILES:
            files = request.FILES.getlist("files")
            for file in files:
                # Validate file size (max 10 MB)
                max_size = 10 * 1024 * 1024  # 10 MB
                if file.size > max_size:
                    continue  # Skip files that are too large

                # Allowed file types
                allowed_extensions = [".pdf", ".doc", ".docx", ".txt", ".jpg", ".jpeg", ".png"]
                file_extension = file.name.lower().split(".")[-1] if "." in file.name else ""
                if file_extension and f".{file_extension}" not in allowed_extensions:
                    continue  # Skip disallowed file types

                document = LessonDocument.objects.create(session=lesson, file=file, name=file.name)
                uploaded_documents.append(document.id)

        return JsonResponse(
            {
                "success": True,
                "message": _("Lesson successfully booked."),
                "lesson_id": lesson.id,
                "contract_id": contract.id,
                "documents_uploaded": len(uploaded_documents),
            }
        )

    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "message": _("Invalid data format.")}, status=400)
    except Exception as e:
        logging.getLogger(__name__).error(
            "Error in book_lesson_api", exc_info=True, extra={"error": str(e)}
        )
        return JsonResponse(
            {"success": False, "message": _("An error occurred. Please try again.")}, status=500
        )
