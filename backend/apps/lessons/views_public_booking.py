"""
Views für öffentliche Buchungsseite (ohne Token).
"""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from apps.contracts.models import Contract
from apps.core.utils_booking import get_tutor_for_booking
from apps.lessons.booking_service import BookingService
from apps.lessons.models import Lesson, LessonDocument
from apps.students.models import Student
from apps.students.services import StudentSearchService
from django.http import JsonResponse
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

        # Week data for booking page (without contract)
        week_data = BookingService.get_public_booking_data(
            target_date.year, target_date.month, target_date.day, user=tutor
        )

        context.update(
            {
                "week_data": week_data,
                "current_date": target_date,
                "tutor_token": tutor_token or "",
            }
        )

        return context


@csrf_exempt
@require_http_methods(["POST"])
def search_student_api(request):
    """API-Endpoint für Namenssuche."""
    try:
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        tutor_token = data.get("tutor_token")

        if not name:
            return JsonResponse(
                {"success": False, "message": _("Please enter a name.")}, status=400
            )

        tutor = get_tutor_for_booking(tutor_token)
        if not tutor:
            return JsonResponse(
                {"success": False, "message": _("Booking is not available.")}, status=400
            )

        # Search for exact match (within tutor's students)
        exact_match = StudentSearchService.find_exact_match(name, user=tutor)
        if exact_match:
            return JsonResponse(
                {
                    "success": True,
                    "exact_match": True,
                    "student": {
                        "id": exact_match.id,
                        "full_name": exact_match.full_name,
                        "email": exact_match.email or "",
                        "phone": exact_match.phone or "",
                    },
                }
            )

        # Search for similar names (within tutor's students)
        similar_students = StudentSearchService.search_by_name(name, threshold=0.7, user=tutor)

        if similar_students:
            return JsonResponse(
                {
                    "success": True,
                    "exact_match": False,
                    "similar_students": [
                        {
                            "id": student.id,
                            "full_name": student.full_name,
                            "similarity": round(ratio * 100, 1),
                        }
                        for student, ratio in similar_students[:5]  # Max 5 Ergebnisse
                    ],
                }
            )
        else:
            return JsonResponse(
                {
                    "success": True,
                    "exact_match": False,
                    "similar_students": [],
                    "message": _("No student found with this name."),
                }
            )

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": _("Invalid JSON data.")}, status=400)
    except Exception as e:
        # Log the error for debugging but don't expose details to user
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in search_student_api: {str(e)}", exc_info=True)
        return JsonResponse(
            {"success": False, "message": _("An error occurred. Please try again.")}, status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
def create_student_api(request):
    """API-Endpoint für neue Schüler."""
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

        # Create new student (assigned to tutor)
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
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": _("Invalid JSON data.")}, status=400)
    except Exception as e:
        # Log the error for debugging but don't expose details to user
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in search_student_api: {str(e)}", exc_info=True)
        return JsonResponse(
            {"success": False, "message": _("An error occurred. Please try again.")}, status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
def book_lesson_api(request):
    """API-Endpoint für Buchung."""
    import logging
    import sys

    logger = logging.getLogger(__name__)
    logger.info("POST request received in book_lesson_api")
    print("[PUBLIC_BOOKING] POST request received in book_lesson_api", file=sys.stdout, flush=True)

    try:
        # Use request.POST for FormData, not JSON
        if request.content_type and "application/json" in request.content_type:
            data = json.loads(request.body)
        else:
            data = request.POST

        student_id = data.get("student_id")
        logger.info(f"Student ID: {student_id}")
        print(f"[PUBLIC_BOOKING] Student ID: {student_id}", file=sys.stdout, flush=True)
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

        try:
            student = Student.objects.get(id=student_id, user=tutor)
        except Student.DoesNotExist:
            return JsonResponse({"success": False, "message": _("Student not found.")}, status=404)

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

        # Validation: Check that the time period consists of whole 30-minute blocks
        duration_total = end_minutes - start_minutes
        if duration_total % 30 != 0:
            return JsonResponse(
                {
                    "success": False,
                    "message": _("Duration must be a multiple of 30 minutes."),
                },
                status=400,
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

        # Create lesson
        logger.info(
            f"Creating lesson: student={student_id}, date={booking_date_obj}, start_time={start_time_obj}, duration={duration_total}"
        )
        print(
            f"[PUBLIC_BOOKING] Creating lesson: student={student_id}, date={booking_date_obj}, start_time={start_time_obj}, duration={duration_total}",
            file=sys.stdout,
            flush=True,
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

        logger.info(f"Lesson created successfully with ID: {lesson.id}")
        print(
            f"[PUBLIC_BOOKING] Lesson created successfully with ID: {lesson.id}",
            file=sys.stdout,
            flush=True,
        )

        # Send email notification
        logger.info(f"Lesson {lesson.id} created, attempting to send email notification")
        print(
            f"[PUBLIC_BOOKING] Lesson {lesson.id} created, attempting to send email notification",
            file=sys.stdout,
            flush=True,
        )
        try:
            from apps.lessons.email_service import send_booking_notification

            send_booking_notification(lesson)
            logger.info(f"Email notification call completed for lesson {lesson.id}")
            print(
                f"[PUBLIC_BOOKING] Email notification call completed for lesson {lesson.id}",
                file=sys.stdout,
                flush=True,
            )
        except Exception as e:
            # Don't fail the booking if email fails
            error_msg = f"Failed to send booking notification email for lesson {lesson.id}: {e}"
            logger.warning(error_msg, exc_info=True)
            print(f"[PUBLIC_BOOKING] WARNING: {error_msg}", file=sys.stdout, flush=True)

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
        # Log the error for debugging but don't expose details to user
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in book_lesson_api: {str(e)}", exc_info=True)
        return JsonResponse(
            {"success": False, "message": _("An error occurred. Please try again.")}, status=500
        )
