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

    _SLOT_STEP_MINUTES = 30  # Start times on 30-min grid

    @staticmethod
    def get_available_time_slots(
        target_date: date,
        working_hours: List[Dict[str, str]],
        occupied_slots: Dict[date, List[Tuple[time, time]]],
        slot_duration_minutes: int = 30,
    ) -> List[Tuple[time, time]]:
        """
        Return available time slots. Each slot spans slot_duration_minutes.
        Start times iterate on 30-min grid. A slot is only added if the full
        block (start -> start+duration) is free within working hours.
        """
        available = []
        now = timezone.now()
        min_booking_datetime = now + timedelta(minutes=30)
        step = BookingService._SLOT_STEP_MINUTES

        for work_period in working_hours:
            start_str = work_period.get("start", "00:00")
            end_str = work_period.get("end", "23:59")
            try:
                period_start = datetime.strptime(start_str, "%H:%M").time()
                period_end = datetime.strptime(end_str, "%H:%M").time()
            except ValueError:
                continue

            current = datetime.combine(target_date, period_start)
            period_end_dt = datetime.combine(target_date, period_end)

            while current + timedelta(minutes=slot_duration_minutes) <= period_end_dt:
                slot_start = current.time()
                slot_end = (current + timedelta(minutes=slot_duration_minutes)).time()

                slot_datetime = timezone.make_aware(datetime.combine(target_date, slot_start))
                if slot_datetime < min_booking_datetime:
                    current += timedelta(minutes=step)
                    continue

                if BookingService.is_time_slot_available(
                    target_date, slot_start, slot_end, occupied_slots
                ):
                    available.append((slot_start, slot_end))

                current += timedelta(minutes=step)

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

        from apps.contracts.models import Contract

        student_id = None
        owner_user = None
        unit_duration = 60
        contract = Contract.objects.select_related("student").filter(pk=contract_id).first()
        if contract:
            student_id = contract.student_id
            owner_user = contract.student.user_id
            unit_duration = contract.unit_duration_minutes

        busy_per_day = (
            BookingService._get_busy_intervals_for_week(
                week_start, week_end, owner_user, student_id
            )
            if owner_user and student_id
            else {}
        )

        days_data = []
        for i in range(7):
            current_date = week_start + timedelta(days=i)
            weekday_name = weekday_names[i]
            day_working_hours = working_hours.get(weekday_name, [])
            available_slots = BookingService.get_available_time_slots(
                current_date,
                day_working_hours,
                occupied_slots,
                slot_duration_minutes=unit_duration,
            )
            days_data.append(
                {
                    "date": current_date,
                    "weekday": weekday_name,
                    "weekday_display": current_date.strftime("%A"),
                    "working_hours": day_working_hours,
                    "available_slots": available_slots,
                    "occupied_slots": occupied_slots.get(current_date, []),
                    "busy_intervals": busy_per_day.get(current_date, []),
                }
            )

        return {
            "week_start": week_start,
            "week_end": week_end,
            "days": days_data,
            "unit_duration_minutes": unit_duration,
        }

    @staticmethod
    def _get_busy_intervals_for_week(
        week_start: date, week_end: date, user, student_id: int | None
    ) -> Dict[date, List[dict]]:
        """
        Build busy_intervals per day with own/other distinction.
        Returns Dict[date, List[{start, end, own, label?}]].
        """
        result = defaultdict(list)

        if not user:
            return dict(result)

        lessons = Lesson.objects.filter(
            date__gte=week_start, date__lte=week_end, contract__student__user=user
        ).select_related("contract", "contract__student")

        for lesson in lessons:
            start_dt, end_dt = LessonConflictService.calculate_time_block(lesson)
            start_str = start_dt.time().strftime("%H:%M")
            end_str = end_dt.time().strftime("%H:%M")
            is_own = student_id is not None and lesson.contract.student_id == student_id
            interval = {"start": start_str, "end": end_str, "own": is_own}
            if is_own:
                interval["label"] = lesson.contract.student.full_name
            result[lesson.date].append(interval)

        start_datetime = timezone.make_aware(datetime.combine(week_start, time.min))
        end_datetime = timezone.make_aware(datetime.combine(week_end, time.max))
        blocked_qs = BlockedTime.objects.filter(
            user=user,
            start_datetime__lt=end_datetime,
            end_datetime__gt=start_datetime,
        ).order_by("start_datetime")

        recurring_qs = RecurringBlockedTime.objects.filter(
            user=user,
            start_date__lte=week_end,
            end_date__gte=week_start,
            is_active=True,
        ) | RecurringBlockedTime.objects.filter(
            user=user,
            start_date__lte=week_end,
            end_date__isnull=True,
            is_active=True,
        )
        for rbt in recurring_qs:
            for bt in RecurringBlockedTimeService.preview_blocked_times(rbt):
                if week_start <= bt.start_datetime.date() <= week_end:
                    blocked_qs = list(blocked_qs) + [bt]

        for bt in blocked_qs:
            local_start = timezone.localtime(bt.start_datetime)
            local_end = timezone.localtime(bt.end_datetime)
            d = local_start.date()
            end_d = local_end.date()
            while d <= end_d and d <= week_end:
                if d >= week_start:
                    if d == local_start.date() and d == end_d:
                        s, e = local_start.time(), local_end.time()
                    elif d == local_start.date():
                        s, e = local_start.time(), time.max
                    elif d == end_d:
                        s, e = time.min, local_end.time()
                    else:
                        s, e = time.min, time.max
                    result[d].append(
                        {
                            "start": s.strftime("%H:%M"),
                            "end": e.strftime("%H:%M"),
                            "own": False,
                        }
                    )
                d += timedelta(days=1)

        for d in result:
            result[d].sort(key=lambda x: (x["start"], x["end"]))
        return dict(result)

    @staticmethod
    def get_public_booking_data(
        year: int, month: int, day: int, user=None, student_id: int | None = None
    ) -> Dict:
        """
        Gibt Daten für die öffentliche Buchungsseite einer Woche zurück (ohne Contract-Token).

        Args:
            year: Jahr
            month: Monat
            day: Tag
            user: Optional - filtert nach User (für Multi-Tenancy)
            student_id: Optional - verified student for own/other slot labelling

        Returns:
            Dict mit:
            - 'week_start': date
            - 'week_end': date
            - 'days': List[Dict] mit Daten für jeden Tag
        """
        from apps.contracts.models import Contract
        from apps.core.models import UserProfile

        target_date = date(year, month, day)
        days_since_monday = target_date.weekday()
        week_start = target_date - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)

        unit_duration = 60
        if student_id and user:
            contract = (
                Contract.objects.filter(student_id=student_id, student__user=user, is_active=True)
                .order_by("-start_date")
                .first()
            )
            if contract:
                unit_duration = contract.unit_duration_minutes

        working_hours = {}
        profile = (
            UserProfile.objects.filter(user=user).first() if user else UserProfile.objects.first()
        )
        if profile and getattr(profile, "default_working_hours", None):
            working_hours = profile.default_working_hours

        occupied_slots = BookingService.get_all_occupied_time_slots(week_start, week_end, user=user)
        busy_intervals = BookingService._get_busy_intervals_for_week(
            week_start, week_end, user, student_id
        )

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
            day_working_hours = working_hours.get(weekday_name, [])
            available_slots = BookingService.get_available_time_slots(
                current_date,
                day_working_hours,
                occupied_slots,
                slot_duration_minutes=unit_duration,
            )
            days_data.append(
                {
                    "date": current_date,
                    "weekday": weekday_name,
                    "weekday_display": current_date.strftime("%A"),
                    "working_hours": day_working_hours,
                    "available_slots": available_slots,
                    "occupied_slots": occupied_slots.get(current_date, []),
                    "busy_intervals": busy_intervals.get(current_date, []),
                }
            )

        return {
            "week_start": week_start,
            "week_end": week_end,
            "days": days_data,
            "unit_duration_minutes": unit_duration,
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
