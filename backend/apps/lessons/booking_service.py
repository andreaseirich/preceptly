"""
Service für Schüler-Buchungsseite - Berechnung verfügbarer/belegter Zeiten.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Tuple

from apps.blocked_times.models import BlockedTime
from apps.blocked_times.recurring_models import RecurringBlockedTime
from apps.blocked_times.recurring_service import RecurringBlockedTimeService
from apps.lessons.conflict_service import LessonConflictService
from apps.lessons.models import Lesson
from django.utils import timezone


class BookingService:
    """Service für Schüler-Buchungsseite."""

    @staticmethod
    def get_occupied_time_slots(
        contract_id: int, start_date: date, end_date: date
    ) -> Dict[date, List[Tuple[time, time]]]:
        """
        Gibt alle belegten Zeitslots für einen Vertrag zurück (inkl. Wegzeiten).

        Args:
            contract_id: ID des Vertrags
            start_date: Startdatum
            end_date: Enddatum

        Returns:
            Dict[date, List[Tuple[start_time, end_time]]] - belegte Zeitslots pro Tag
        """
        occupied = defaultdict(list)

        # Load all lessons in the period (including from other contracts, as travel times are relevant)
        lessons = Lesson.objects.filter(date__gte=start_date, date__lte=end_date).select_related(
            "contract", "contract__student"
        )

        for lesson in lessons:
            start_datetime, end_datetime = LessonConflictService.calculate_time_block(lesson)
            occupied[lesson.date].append((start_datetime.time(), end_datetime.time()))

        # Lade Blockzeiten im Zeitraum
        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
        end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))
        blocked_times = BlockedTime.objects.filter(
            start_datetime__lt=end_datetime, end_datetime__gt=start_datetime
        ).order_by("start_datetime")

        # Lade wiederkehrende Blockzeiten und generiere temporäre Blockzeiten für den Zeitraum
        recurring_blocked_times = RecurringBlockedTime.objects.filter(
            start_date__lte=end_date, end_date__gte=start_date, is_active=True
        ) | RecurringBlockedTime.objects.filter(
            start_date__lte=end_date, end_date__isnull=True, is_active=True
        )

        # Füge Vorschau-Blockzeiten aus wiederkehrenden Blockzeiten hinzu
        for rbt in recurring_blocked_times:
            generated_blocked_times_preview = RecurringBlockedTimeService.preview_blocked_times(rbt)
            for bt_preview in generated_blocked_times_preview:
                # Filter nur für den Zeitraum
                if start_date <= bt_preview.start_datetime.date() <= end_date:
                    blocked_times = list(blocked_times) + [bt_preview]

        for blocked_time in blocked_times:
            # Convert to local timezone for correct time extraction
            local_start_datetime = timezone.localtime(blocked_time.start_datetime)
            local_end_datetime = timezone.localtime(blocked_time.end_datetime)

            current_date = local_start_datetime.date()
            end_date_bt = local_end_datetime.date()

            while current_date <= end_date_bt and current_date <= end_date:
                if current_date >= start_date:
                    # Calculate the actual time range for this specific day
                    if current_date == local_start_datetime.date():
                        # First day: from start time to end of day or end time
                        if current_date == end_date_bt:
                            # Same day: use actual start and end time
                            day_start_time = local_start_datetime.time()
                            day_end_time = local_end_datetime.time()
                        else:
                            # Multi-day: from start time to end of day
                            day_start_time = local_start_datetime.time()
                            day_end_time = time.max
                    elif current_date == end_date_bt:
                        # Last day: from start of day to end time
                        day_start_time = time.min
                        day_end_time = local_end_datetime.time()
                    else:
                        # Middle days: full day
                        day_start_time = time.min
                        day_end_time = time.max

                    occupied[current_date].append((day_start_time, day_end_time))
                current_date += timedelta(days=1)

        # Sortiere Zeitslots pro Tag
        for day in occupied:
            occupied[day].sort()

        return dict(occupied)

    @staticmethod
    def is_time_slot_available(
        target_date: date,
        start_time: time,
        end_time: time,
        occupied_slots: Dict[date, List[Tuple[time, time]]],
    ) -> bool:
        """
        Prüft, ob ein Zeitslot verfügbar ist.

        Args:
            target_date: Datum
            start_time: Startzeit
            end_time: Endzeit
            occupied_slots: Dict mit belegten Zeitslots

        Returns:
            True wenn verfügbar, False wenn belegt
        """
        if target_date not in occupied_slots:
            return True

        for occupied_start, occupied_end in occupied_slots[target_date]:
            # Check for overlap
            if not (end_time <= occupied_start or start_time >= occupied_end):
                return False

        return True

    @staticmethod
    def get_available_time_slots(
        target_date: date,
        working_hours: List[Dict[str, str]],
        occupied_slots: Dict[date, List[Tuple[time, time]]],
        slot_duration_minutes: int = 30,
    ) -> List[Tuple[time, time]]:
        """
        Gibt verfügbare Zeitslots für einen Tag zurück.

        Args:
            target_date: Datum
            working_hours: Liste von Arbeitszeiten [{'start': '09:00', 'end': '17:00'}, ...]
            occupied_slots: Dict mit belegten Zeitslots
            slot_duration_minutes: Dauer eines Slots in Minuten

        Returns:
            Liste von (start_time, end_time) Tupeln
        """
        available = []
        now = timezone.now()
        min_booking_datetime = now + timedelta(minutes=30)  # At least 30 minutes advance notice

        for work_period in working_hours:
            start_str = work_period.get("start", "00:00")
            end_str = work_period.get("end", "23:59")

            try:
                period_start = datetime.strptime(start_str, "%H:%M").time()
                period_end = datetime.strptime(end_str, "%H:%M").time()
            except ValueError:
                continue

            # Generate slots within working hours
            current = datetime.combine(target_date, period_start)
            period_end_dt = datetime.combine(target_date, period_end)

            while current + timedelta(minutes=slot_duration_minutes) <= period_end_dt:
                slot_start = current.time()
                slot_end = (current + timedelta(minutes=slot_duration_minutes)).time()

                # Check if slot is in the past or less than 30 minutes in the future
                slot_datetime = timezone.make_aware(datetime.combine(target_date, slot_start))
                if slot_datetime < min_booking_datetime:
                    current += timedelta(minutes=slot_duration_minutes)
                    continue

                if BookingService.is_time_slot_available(
                    target_date, slot_start, slot_end, occupied_slots
                ):
                    available.append((slot_start, slot_end))

                current += timedelta(minutes=slot_duration_minutes)

        return available

    @staticmethod
    def get_week_booking_data(
        contract_id: int, year: int, month: int, day: int, working_hours: Dict
    ) -> Dict:
        """
        Gibt Daten für die Buchungsseite einer Woche zurück.

        Args:
            contract_id: ID des Vertrags
            year: Jahr
            month: Monat
            day: Tag
            working_hours: Dict mit Arbeitszeiten pro Wochentag

        Returns:
            Dict mit:
            - 'week_start': date
            - 'week_end': date
            - 'days': List[Dict] mit Daten für jeden Tag
        """
        target_date = date(year, month, day)
        days_since_monday = target_date.weekday()
        week_start = target_date - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)

        # Load occupied time slots
        occupied_slots = BookingService.get_occupied_time_slots(contract_id, week_start, week_end)

        # Weekday names
        weekday_names = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]

        days_data = []
        for i in range(7):
            current_date = week_start + timedelta(days=i)
            weekday_name = weekday_names[i]

            # Working hours for this weekday
            day_working_hours = working_hours.get(weekday_name, [])

            # Available slots
            available_slots = BookingService.get_available_time_slots(
                current_date, day_working_hours, occupied_slots
            )

            days_data.append(
                {
                    "date": current_date,
                    "weekday": weekday_name,
                    "weekday_display": current_date.strftime("%A"),
                    "working_hours": day_working_hours,
                    "available_slots": available_slots,
                    "occupied_slots": occupied_slots.get(current_date, []),
                }
            )

        return {
            "week_start": week_start,
            "week_end": week_end,
            "days": days_data,
        }

    @staticmethod
    def get_public_booking_data(year: int, month: int, day: int, user=None) -> Dict:
        """
        Gibt Daten für die öffentliche Buchungsseite einer Woche zurück (ohne Contract-Token).

        Args:
            year: Jahr
            month: Monat
            day: Tag
            user: Optional - filtert nach User (für Multi-Tenancy)

        Returns:
            Dict mit:
            - 'week_start': date
            - 'week_end': date
            - 'days': List[Dict] mit Daten für jeden Tag
        """
        from apps.core.models import UserProfile

        target_date = date(year, month, day)
        days_since_monday = target_date.weekday()
        week_start = target_date - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)

        # Use default working hours from UserProfile
        working_hours = {}
        try:
            profile = (
                UserProfile.objects.filter(user=user).first()
                if user
                else UserProfile.objects.first()
            )
            if profile and profile.default_working_hours:
                working_hours = profile.default_working_hours
        except (UserProfile.DoesNotExist, AttributeError) as e:
            # Log the error for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Could not load default working hours: {str(e)}")

        # Load occupied time slots (for all contracts, as there is no specific contract)
        occupied_slots = BookingService.get_all_occupied_time_slots(week_start, week_end, user=user)

        # Weekday names
        weekday_names = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]

        days_data = []
        for i in range(7):
            current_date = week_start + timedelta(days=i)
            weekday_name = weekday_names[i]

            # Working hours for this weekday
            day_working_hours = working_hours.get(weekday_name, [])

            # Available slots
            available_slots = BookingService.get_available_time_slots(
                current_date, day_working_hours, occupied_slots
            )

            days_data.append(
                {
                    "date": current_date,
                    "weekday": weekday_name,
                    "weekday_display": current_date.strftime("%A"),
                    "working_hours": day_working_hours,
                    "available_slots": available_slots,
                    "occupied_slots": occupied_slots.get(current_date, []),
                }
            )

        return {
            "week_start": week_start,
            "week_end": week_end,
            "days": days_data,
        }

    @staticmethod
    def get_all_occupied_time_slots(
        start_date: date, end_date: date, user=None
    ) -> Dict[date, List[Tuple[time, time]]]:
        """
        Gibt alle belegten Zeitslots zurück.

        Args:
            start_date: Startdatum
            end_date: Enddatum
            user: Optional - filtert nach User (für Multi-Tenancy)

        Returns:
            Dict[date, List[Tuple[start_time, end_time]]] - belegte Zeitslots pro Tag
        """
        occupied = defaultdict(list)

        # Load all lessons in the period
        lessons_qs = Lesson.objects.filter(date__gte=start_date, date__lte=end_date).select_related(
            "contract", "contract__student"
        )
        if user:
            lessons_qs = lessons_qs.filter(contract__student__user=user)
        lessons = lessons_qs

        for lesson in lessons:
            start_datetime, end_datetime = LessonConflictService.calculate_time_block(lesson)
            occupied[lesson.date].append((start_datetime.time(), end_datetime.time()))

        # Load blocked times in the period
        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
        end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))
        blocked_times_qs = BlockedTime.objects.filter(
            start_datetime__lt=end_datetime, end_datetime__gt=start_datetime
        ).order_by("start_datetime")
        if user:
            blocked_times_qs = blocked_times_qs.filter(user=user)
        blocked_times = blocked_times_qs

        # Lade wiederkehrende Blockzeiten und generiere temporäre Blockzeiten für den Zeitraum
        recurring_qs = RecurringBlockedTime.objects.filter(
            start_date__lte=end_date, end_date__gte=start_date, is_active=True
        ) | RecurringBlockedTime.objects.filter(
            start_date__lte=end_date, end_date__isnull=True, is_active=True
        )
        if user:
            recurring_qs = recurring_qs.filter(user=user)
        recurring_blocked_times = recurring_qs

        # Füge Vorschau-Blockzeiten aus wiederkehrenden Blockzeiten hinzu
        for rbt in recurring_blocked_times:
            generated_blocked_times_preview = RecurringBlockedTimeService.preview_blocked_times(rbt)
            for bt_preview in generated_blocked_times_preview:
                # Filter nur für den Zeitraum
                if start_date <= bt_preview.start_datetime.date() <= end_date:
                    blocked_times = list(blocked_times) + [bt_preview]

        for blocked_time in blocked_times:
            # Convert to local timezone for correct time extraction
            local_start_datetime = timezone.localtime(blocked_time.start_datetime)
            local_end_datetime = timezone.localtime(blocked_time.end_datetime)

            current_date = local_start_datetime.date()
            end_date_bt = local_end_datetime.date()

            while current_date <= end_date_bt and current_date <= end_date:
                if current_date >= start_date:
                    # Calculate the actual time range for this specific day
                    if current_date == local_start_datetime.date():
                        # First day: from start time to end of day or end time
                        if current_date == end_date_bt:
                            # Same day: use actual start and end time
                            day_start_time = local_start_datetime.time()
                            day_end_time = local_end_datetime.time()
                        else:
                            # Multi-day: from start time to end of day
                            day_start_time = local_start_datetime.time()
                            day_end_time = time.max
                    elif current_date == end_date_bt:
                        # Last day: from start of day to end time
                        day_start_time = time.min
                        day_end_time = local_end_datetime.time()
                    else:
                        # Middle days: full day
                        day_start_time = time.min
                        day_end_time = time.max

                    occupied[current_date].append((day_start_time, day_end_time))
                current_date += timedelta(days=1)

        # Sort time slots per day
        for day in occupied:
            occupied[day].sort()

        return dict(occupied)
