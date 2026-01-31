"""
Views für öffentliche Schüler-Buchungsseite.
"""

import json
from datetime import date, datetime

from apps.contracts.models import Contract
from apps.lessons.booking_service import BookingService
from apps.lessons.email_service import send_booking_notification
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.lessons.recurring_service import RecurringLessonService
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView


@method_decorator(ensure_csrf_cookie, name="dispatch")
class StudentBookingView(TemplateView):
    """Öffentliche Buchungsseite für Schüler."""

    template_name = "lessons/student_booking.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = self.kwargs.get("token")

        try:
            contract = Contract.objects.get(booking_token=token, is_active=True)
        except Contract.DoesNotExist as err:
            raise Http404(_("Booking link not found or contract is inactive.")) from err

        # Aktuelles Datum oder aus GET-Parameter
        try:
            year = int(self.request.GET.get("year", timezone.now().year))
            month = int(self.request.GET.get("month", timezone.now().month))
            day = int(self.request.GET.get("day", timezone.now().day))
            target_date = date(year, month, day)
        except (ValueError, TypeError):
            target_date = timezone.now().date()

        # Working hours from contract, fallback to tutor's default
        working_hours = contract.working_hours or {}
        if not working_hours:
            from apps.core.models import UserProfile

            profile = UserProfile.objects.filter(user=contract.student.user).first()
            if profile and profile.default_working_hours:
                working_hours = profile.default_working_hours

        # Week data for booking page
        week_data = BookingService.get_week_booking_data(
            contract.id, target_date.year, target_date.month, target_date.day, working_hours
        )

        context.update(
            {
                "contract": contract,
                "student": contract.student,
                "week_data": week_data,
                "working_hours": working_hours,
                "current_date": target_date,
            }
        )

        return context

    def post(self, request, *args, **kwargs):
        """Behandelt Buchungsanfragen."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info("POST request received in StudentBookingView")

        token = self.kwargs.get("token")

        try:
            contract = Contract.objects.get(booking_token=token, is_active=True)
            logger.info("Contract found for booking request", extra={"contract_id": contract.id})
        except Contract.DoesNotExist:
            logger.warning("Contract not found or inactive for booking request")
            messages.error(request, _("Booking link not found or contract is inactive."))
            return redirect("lessons:student_booking", token=token)

        # Parse JSON data
        try:
            data = json.loads(request.body)
            action = data.get("action")
            if action in ("book_slot", "book_recurring_slot"):
                logger.info("Processing booking action", extra={"action": action})

            if action == "book_slot":
                # Book a time slot
                booking_date = data.get("date")
                start_time = data.get("start_time")
                end_time = data.get("end_time")  # Optional: if set, this will be used
                duration_minutes = data.get("duration_minutes", contract.unit_duration_minutes)

                try:
                    booking_date_obj = datetime.strptime(booking_date, "%Y-%m-%d").date()
                    start_time_obj = datetime.strptime(start_time, "%H:%M").time()
                except ValueError:
                    return JsonResponse(
                        {"success": False, "message": _("Invalid date or time format.")}, status=400
                    )

                # Calculate end time
                from datetime import timedelta

                if end_time:
                    try:
                        end_time_obj = datetime.strptime(end_time, "%H:%M").time()
                    except ValueError:
                        return JsonResponse(
                            {"success": False, "message": _("Invalid end time format.")}, status=400
                        )
                else:
                    # Fallback: use duration_minutes
                    end_time_obj = (
                        datetime.combine(booking_date_obj, start_time_obj)
                        + timedelta(minutes=duration_minutes)
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
                        {"success": False, "message": _("End time must be after start time.")},
                        status=400,
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

                # Calculate duration_minutes from start and end time
                duration_minutes = duration_total

                # Validation: Check that appointment is not in the past
                # and is at least 30 minutes in the future
                booking_datetime = timezone.make_aware(
                    datetime.combine(booking_date_obj, start_time_obj)
                )
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
                week_data = BookingService.get_week_booking_data(
                    contract.id,
                    booking_date_obj.year,
                    booking_date_obj.month,
                    booking_date_obj.day,
                    contract.working_hours or {},
                )

                # Find the day in week_data
                target_day = None
                for day_data in week_data["days"]:
                    if day_data["date"] == booking_date_obj:
                        target_day = day_data
                        break

                if not target_day:
                    return JsonResponse(
                        {"success": False, "message": _("Date not found.")}, status=400
                    )

                # Check if slot is available
                occupied_slots = BookingService.get_occupied_time_slots(
                    contract.id, booking_date_obj, booking_date_obj
                )

                if not BookingService.is_time_slot_available(
                    booking_date_obj, start_time_obj, end_time_obj, occupied_slots
                ):
                    return JsonResponse(
                        {"success": False, "message": _("Time slot is already booked.")}, status=400
                    )

                lesson = Lesson.objects.create(
                    contract=contract,
                    date=booking_date_obj,
                    start_time=start_time_obj,
                    duration_minutes=duration_minutes,
                    status="planned",
                    travel_time_before_minutes=0,
                    travel_time_after_minutes=0,
                )

                logger.info("Lesson created successfully", extra={"lesson_id": lesson.id})

                try:
                    send_booking_notification(lesson)
                    logger.info("Email notification sent", extra={"lesson_id": lesson.id})
                except Exception:
                    logger.warning(
                        "Failed to send booking notification email",
                        extra={"lesson_id": lesson.id},
                        exc_info=True,
                    )

                return JsonResponse(
                    {
                        "success": True,
                        "message": _("Lesson successfully booked."),
                        "lesson_id": lesson.id,
                    }
                )

            elif action == "book_recurring_slot":
                # Book a recurring lesson
                booking_date = data.get("date")
                start_time = data.get("start_time")
                end_time = data.get("end_time")
                recurrence_type = data.get("recurrence_type", "weekly")
                weekdays = data.get("weekdays", [])  # List of weekdays [0,1,2,...] (0=Monday)
                end_date = data.get("end_date")  # Optional: end date of series

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
                    # Fallback: use contract.unit_duration_minutes
                    end_time_obj = (
                        datetime.combine(booking_date_obj, start_time_obj)
                        + timedelta(minutes=contract.unit_duration_minutes)
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
                        {"success": False, "message": _("End time must be after start time.")},
                        status=400,
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

                # Validation: Check that at least one weekday is selected
                if not weekdays or len(weekdays) == 0:
                    return JsonResponse(
                        {"success": False, "message": _("At least one weekday must be selected.")},
                        status=400,
                    )

                # Validation: Check that start date is not in the past
                # and is at least 30 minutes in the future
                booking_datetime = timezone.make_aware(
                    datetime.combine(booking_date_obj, start_time_obj)
                )
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

                # Parse end date if present
                end_date_obj = None
                if end_date:
                    try:
                        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                    except ValueError:
                        return JsonResponse(
                            {"success": False, "message": _("Invalid end date format.")}, status=400
                        )

                # Create RecurringLesson
                recurring_lesson = RecurringLesson(
                    contract=contract,
                    start_date=booking_date_obj,
                    end_date=end_date_obj,
                    start_time=start_time_obj,
                    duration_minutes=duration_total,
                    travel_time_before_minutes=0,
                    travel_time_after_minutes=0,
                    recurrence_type=recurrence_type,
                    is_active=True,
                )

                # Set weekdays
                recurring_lesson.monday = 0 in weekdays
                recurring_lesson.tuesday = 1 in weekdays
                recurring_lesson.wednesday = 2 in weekdays
                recurring_lesson.thursday = 3 in weekdays
                recurring_lesson.friday = 4 in weekdays
                recurring_lesson.saturday = 5 in weekdays
                recurring_lesson.sunday = 6 in weekdays

                recurring_lesson.save()

                # Generate lessons from RecurringLesson
                result = RecurringLessonService.generate_lessons(
                    recurring_lesson, check_conflicts=True
                )

                # Send email notifications for created lessons
                import logging

                logger = logging.getLogger(__name__)
                if result.get("created", 0) > 0:
                    created_sessions = result.get("sessions", [])
                    logger.info(
                        f"Recurring booking created {len(created_sessions)} sessions, attempting to send email notifications"
                    )
                    if created_sessions:
                        # Send one email per created session
                        for session in created_sessions:
                            try:
                                send_booking_notification(session)
                                logger.info(
                                    "Email notification sent",
                                    extra={"session_id": session.id},
                                )
                            except Exception:
                                logger.warning(
                                    "Failed to send booking notification email",
                                    extra={"session_id": session.id},
                                    exc_info=True,
                                )

                return JsonResponse(
                    {
                        "success": True,
                        "message": _(
                            "Recurring lesson series successfully created. {count} lesson(s) generated."
                        ).format(count=result["created"]),
                        "recurring_lesson_id": recurring_lesson.id,
                        "lessons_created": result["created"],
                    }
                )

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": _("Invalid JSON data.")}, status=400)

        return JsonResponse({"success": False, "message": _("Unknown action.")}, status=400)


def _get_week_data_json(contract, year: int, month: int, day: int):
    """Returns week booking data as JSON-serializable dict."""
    working_hours = contract.working_hours or {}
    if not working_hours:
        from apps.core.models import UserProfile

        profile = UserProfile.objects.filter(user=contract.student.user).first()
        if profile and profile.default_working_hours:
            working_hours = profile.default_working_hours

    week_data = BookingService.get_week_booking_data(contract.id, year, month, day, working_hours)

    def serialize_day(day_data):
        return {
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
        }

    return {
        "week_start": week_data["week_start"].strftime("%Y-%m-%d"),
        "week_end": week_data["week_end"].strftime("%Y-%m-%d"),
        "days": [serialize_day(d) for d in week_data["days"]],
    }


@require_http_methods(["GET"])
def student_booking_week_api(request, token):
    """API for fetching week booking data (for AJAX week navigation)."""
    try:
        contract = Contract.objects.get(booking_token=token, is_active=True)
    except Contract.DoesNotExist:
        return JsonResponse({"success": False, "message": _("Booking link not found.")}, status=404)

    try:
        year = int(request.GET.get("year", timezone.now().year))
        month = int(request.GET.get("month", timezone.now().month))
        day = int(request.GET.get("day", timezone.now().day))
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "message": _("Invalid date.")}, status=400)

    data = _get_week_data_json(contract, year, month, day)
    return JsonResponse({"success": True, "week_data": data})


@csrf_exempt
@require_http_methods(["POST"])
def student_booking_api(request, token):
    """API-Endpoint für Buchungsanfragen (für AJAX)."""
    view = StudentBookingView()
    view.kwargs = {"token": token}
    view.request = request
    return view.post(request, token=token)
