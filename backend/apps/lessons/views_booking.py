"""
Views für öffentliche Schüler-Buchungsseite.
"""

import json
from datetime import date, datetime

from apps.contracts.models import Contract
from apps.lessons.booking_service import BookingService
from apps.lessons.models import Lesson
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

        # Arbeitszeiten aus Contract, fallback auf default_working_hours
        working_hours = contract.working_hours or {}
        if not working_hours:
            # Fallback auf allgemeine Arbeitszeiten des Tutors
            # Da Contracts keine direkte User-Beziehung haben, nehmen wir den ersten UserProfile
            # In einer Multi-User-Umgebung müsste hier die Logik angepasst werden
            from apps.core.models import UserProfile

            try:
                # Versuche den ersten UserProfile zu finden (für Single-User-Setup)
                profile = UserProfile.objects.first()
                if profile and profile.default_working_hours:
                    working_hours = profile.default_working_hours
            except (UserProfile.DoesNotExist, AttributeError):
                # UserProfile not found or missing attribute - use empty working hours
                pass

        # Wochendaten für Buchungsseite
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
        token = self.kwargs.get("token")

        try:
            contract = Contract.objects.get(booking_token=token, is_active=True)
        except Contract.DoesNotExist:
            messages.error(request, _("Booking link not found or contract is inactive."))
            return redirect("lessons:student_booking", token=token)

        # Parse JSON-Daten
        try:
            data = json.loads(request.body)
            action = data.get("action")

            if action == "update_working_hours":
                # Aktualisiere Arbeitszeiten
                working_hours = data.get("working_hours", {})
                contract.working_hours = working_hours
                contract.save(update_fields=["working_hours"])
                return JsonResponse({"success": True, "message": _("Working hours updated.")})

            elif action == "book_slot":
                # Buche einen Zeitslot
                booking_date = data.get("date")
                start_time = data.get("start_time")
                duration_minutes = data.get("duration_minutes", contract.unit_duration_minutes)

                try:
                    booking_date_obj = datetime.strptime(booking_date, "%Y-%m-%d").date()
                    start_time_obj = datetime.strptime(start_time, "%H:%M").time()
                except ValueError:
                    return JsonResponse(
                        {"success": False, "message": _("Invalid date or time format.")}, status=400
                    )

                # Prüfe Verfügbarkeit
                week_data = BookingService.get_week_booking_data(
                    contract.id,
                    booking_date_obj.year,
                    booking_date_obj.month,
                    booking_date_obj.day,
                    contract.working_hours or {},
                )

                # Finde den Tag in week_data
                target_day = None
                for day_data in week_data["days"]:
                    if day_data["date"] == booking_date_obj:
                        target_day = day_data
                        break

                if not target_day:
                    return JsonResponse(
                        {"success": False, "message": _("Date not found.")}, status=400
                    )

                # Prüfe ob Slot verfügbar ist
                from datetime import timedelta

                end_time_obj = (
                    datetime.combine(booking_date_obj, start_time_obj)
                    + timedelta(minutes=duration_minutes)
                ).time()

                occupied_slots = BookingService.get_occupied_time_slots(
                    contract.id, booking_date_obj, booking_date_obj
                )

                if not BookingService.is_time_slot_available(
                    booking_date_obj, start_time_obj, end_time_obj, occupied_slots
                ):
                    return JsonResponse(
                        {"success": False, "message": _("Time slot is already booked.")}, status=400
                    )

                # Erstelle Lesson
                lesson = Lesson.objects.create(
                    contract=contract,
                    date=booking_date_obj,
                    start_time=start_time_obj,
                    duration_minutes=duration_minutes,
                    status="planned",
                    travel_time_before_minutes=0,
                    travel_time_after_minutes=0,
                )

                return JsonResponse(
                    {
                        "success": True,
                        "message": _("Lesson successfully booked."),
                        "lesson_id": lesson.id,
                    }
                )

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": _("Invalid JSON data.")}, status=400)

        return JsonResponse({"success": False, "message": _("Unknown action.")}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def student_booking_api(request, token):
    """API-Endpoint für Buchungsanfragen (für AJAX)."""
    view = StudentBookingView()
    view.kwargs = {"token": token}
    view.request = request
    return view.post(request, token=token)
