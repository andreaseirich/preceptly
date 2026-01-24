"""
Views für BlockedTime-CRUD-Operationen.
"""

from apps.blocked_times.forms import BlockedTimeForm
from apps.blocked_times.models import BlockedTime
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView


class BlockedTimeDetailView(LoginRequiredMixin, DetailView):
    """Detailansicht einer Blockzeit."""

    model = BlockedTime
    template_name = "blocked_times/blockedtime_detail.html"
    context_object_name = "blocked_time"


class BlockedTimeCreateView(LoginRequiredMixin, CreateView):
    """Neue Blockzeit erstellen."""

    model = BlockedTime
    form_class = BlockedTimeForm
    template_name = "blocked_times/blockedtime_form.html"

    def get_initial(self):
        """Pre-fill form with date/time from request parameters (similar to LessonCreateView)."""
        initial = super().get_initial()
        
        # Support for start/end parameters from week view (ISO datetime format: YYYY-MM-DDTHH:MM)
        start_str = self.request.GET.get("start")
        end_str = self.request.GET.get("end")
        
        if start_str:
            try:
                from datetime import datetime, timedelta
                from django.utils import timezone
                
                # Parse ISO format: YYYY-MM-DDTHH:MM or YYYY-MM-DDTHH:MM:SS
                if 'T' in start_str:
                    # ISO datetime format
                    if len(start_str) == 16:  # YYYY-MM-DDTHH:MM
                        start_dt = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
                    else:  # YYYY-MM-DDTHH:MM:SS or with timezone
                        start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                        if start_dt.tzinfo:
                            start_dt = timezone.make_naive(start_dt)
                    
                    # Make timezone-aware
                    if timezone.is_naive(start_dt):
                        start_dt = timezone.make_aware(start_dt)
                    
                    initial["start_datetime"] = start_dt
                    
                    # Calculate end_datetime from end parameter if provided
                    if end_str:
                        try:
                            if len(end_str) == 16:  # YYYY-MM-DDTHH:MM
                                end_dt = datetime.strptime(end_str, "%Y-%m-%dT%H:%M")
                            else:  # YYYY-MM-DDTHH:MM:SS or with timezone
                                end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                                if end_dt.tzinfo:
                                    end_dt = timezone.make_naive(end_dt)
                            
                            # Make timezone-aware
                            if timezone.is_naive(end_dt):
                                end_dt = timezone.make_aware(end_dt)
                            
                            initial["end_datetime"] = end_dt
                        except (ValueError, TypeError):
                            # Fallback: use start + 1 hour
                            initial["end_datetime"] = start_dt + timedelta(hours=1)
                    else:
                        # Fallback: use start + 1 hour
                        initial["end_datetime"] = start_dt + timedelta(hours=1)
                else:
                    # Fallback: treat as date only
                    date_obj = datetime.strptime(start_str, "%Y-%m-%d").date()
                    start_dt = timezone.make_aware(datetime.combine(date_obj, datetime.min.time().replace(hour=9)))
                    initial["start_datetime"] = start_dt
                    initial["end_datetime"] = start_dt + timedelta(hours=1)
            except (ValueError, TypeError):
                pass
        
        # Fallback: Get date from request (for backward compatibility)
        if "start_datetime" not in initial:
            date_str = self.request.GET.get("date")
            if date_str:
                try:
                    from datetime import datetime
                    from django.utils import timezone
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    start_dt = timezone.make_aware(datetime.combine(date_obj, datetime.min.time().replace(hour=9)))
                    initial["start_datetime"] = start_dt
                    initial["end_datetime"] = start_dt + timedelta(hours=1)
                except ValueError:
                    pass
        
        return initial

    def get_success_url(self):
        """Redirect back to last used calendar view (similar to LessonCreateView)."""
        blocked_time = self.object
        # Use year/month/day from request if available, otherwise from blocked_time date
        year = int(self.request.GET.get("year", blocked_time.start_datetime.year))
        month = int(self.request.GET.get("month", blocked_time.start_datetime.month))
        day = int(self.request.GET.get("day", blocked_time.start_datetime.day))
        
        # Get last used calendar view from session (default: week)
        last_view = self.request.session.get('last_calendar_view', 'week')
        
        if last_view == 'week':
            return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"
        else:
            return reverse_lazy("lessons:calendar") + f"?year={year}&month={month}"

    def form_valid(self, form):
        from apps.blocked_times.recurring_models import RecurringBlockedTime
        from apps.blocked_times.recurring_service import RecurringBlockedTimeService
        from apps.lessons.services import recalculate_conflicts_for_blocked_time
        from django.utils.translation import gettext_lazy as _, ngettext
        from datetime import datetime
        from django.utils import timezone

        # Prüfe, ob eine Serientermin erstellt werden soll
        is_recurring = form.cleaned_data.get("is_recurring", False)

        if is_recurring:
            # Erstelle eine RecurringBlockedTime statt einer einzelnen BlockedTime
            blocked_time = form.save(commit=False)  # Noch nicht speichern
            
            # Erstelle RecurringBlockedTime
            recurring_blocked_time = RecurringBlockedTime(
                title=blocked_time.title,
                description=blocked_time.description,
                start_date=blocked_time.start_datetime.date(),
                end_date=form.cleaned_data.get("recurrence_end_date"),
                start_time=blocked_time.start_datetime.time(),
                end_time=blocked_time.end_datetime.time(),
                recurrence_type=form.cleaned_data.get("recurrence_type", "weekly"),
                is_active=True,
            )
            
            # Setze Wochentage basierend auf recurrence_weekdays
            weekdays = form.cleaned_data.get("recurrence_weekdays", [])
            recurring_blocked_time.monday = "0" in weekdays
            recurring_blocked_time.tuesday = "1" in weekdays
            recurring_blocked_time.wednesday = "2" in weekdays
            recurring_blocked_time.thursday = "3" in weekdays
            recurring_blocked_time.friday = "4" in weekdays
            recurring_blocked_time.saturday = "5" in weekdays
            recurring_blocked_time.sunday = "6" in weekdays
            
            recurring_blocked_time.save()
            
            # Generiere BlockedTimes aus der RecurringBlockedTime
            result = RecurringBlockedTimeService.generate_blocked_times(recurring_blocked_time, check_conflicts=True)
            
            if result["created"] > 0:
                messages.success(
                    self.request,
                    ngettext(
                        "Recurring blocked time series created and {count} blocked time generated.",
                        "Recurring blocked time series created and {count} blocked times generated.",
                        result["created"],
                    ).format(count=result["created"]),
                )
            else:
                messages.info(
                    self.request,
                    _("Recurring blocked time series created, but no new blocked times were generated (they may already exist)."),
                )

            if result["conflicts"]:
                conflict_count = len(result["conflicts"])
                messages.warning(
                    self.request,
                    ngettext(
                        "{count} blocked time with conflicts detected.",
                        "{count} blocked times with conflicts detected.",
                        conflict_count,
                    ).format(count=conflict_count),
                )
            
            # Setze self.object für die Weiterleitung
            # Verwende die erste erstellte BlockedTime oder die erste gefundene BlockedTime
            if result.get("created", 0) > 0:
                # Finde die erste erstellte BlockedTime
                first_blocked_time = BlockedTime.objects.filter(
                    title=recurring_blocked_time.title,
                    start_datetime__date__gte=recurring_blocked_time.start_date,
                    start_datetime__time=recurring_blocked_time.start_time,
                ).order_by("start_datetime").first()
                self.object = first_blocked_time
            else:
                # Falls keine BlockedTime erstellt wurde, verwende die ursprüngliche BlockedTime
                blocked_time.save()
                recalculate_conflicts_for_blocked_time(blocked_time)
                self.object = blocked_time
        else:
            # Normale einzelne BlockedTime erstellen
            blocked_time = form.save()

            # Recalculate conflicts for affected lessons
            recalculate_conflicts_for_blocked_time(blocked_time)

            conflicts = []
            from apps.lessons.models import Lesson
            from apps.lessons.services import LessonConflictService
            # Prüfe Konflikte mit Lessons
            conflicting_lessons = Lesson.objects.filter(
                date=blocked_time.start_datetime.date()
            ).select_related("contract", "contract__student")
            
            for lesson in conflicting_lessons:
                lesson_start, lesson_end = LessonConflictService.calculate_time_block(lesson)
                if not (blocked_time.end_datetime <= lesson_start or blocked_time.start_datetime >= lesson_end):
                    conflicts.append(lesson)
            
            if conflicts:
                messages.warning(
                    self.request,
                    _("Blocked time created, but {count} conflict(s) detected!").format(count=len(conflicts)),
                )
            else:
                messages.success(self.request, _("Blocked time successfully created."))

        return super().form_valid(form)


class BlockedTimeUpdateView(LoginRequiredMixin, UpdateView):
    """Blockzeit bearbeiten."""

    model = BlockedTime
    form_class = BlockedTimeForm
    template_name = "blocked_times/blockedtime_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.blocked_times.recurring_utils import find_matching_recurring_blocked_time
        
        # Prüfe, ob diese BlockedTime zu einer Serie gehört
        matching_recurring = find_matching_recurring_blocked_time(self.object)
        context["matching_recurring"] = matching_recurring
        
        return context

    def get_success_url(self):
        """Redirect back to last used calendar view (similar to LessonUpdateView)."""
        blocked_time = self.object
        # Use year/month/day from request if available, otherwise from blocked_time date
        year = int(self.request.GET.get("year", blocked_time.start_datetime.year))
        month = int(self.request.GET.get("month", blocked_time.start_datetime.month))
        day = int(self.request.GET.get("day", blocked_time.start_datetime.day))
        
        # Get last used calendar view from session (default: week)
        last_view = self.request.session.get('last_calendar_view', 'week')
        
        if last_view == 'week':
            return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"
        else:
            return reverse_lazy("lessons:calendar") + f"?year={year}&month={month}"

    def form_valid(self, form):
        from apps.blocked_times.recurring_models import RecurringBlockedTime
        from apps.blocked_times.recurring_service import RecurringBlockedTimeService
        from apps.blocked_times.recurring_utils import find_matching_recurring_blocked_time, get_all_blocked_times_for_recurring
        from apps.lessons.services import recalculate_conflicts_for_blocked_time
        from django.utils.translation import gettext_lazy as _

        # WICHTIG: Hole die ursprüngliche BlockedTime-Instanz aus der Datenbank,
        # bevor wir nach der RecurringBlockedTime suchen
        original_blocked_time = BlockedTime.objects.get(pk=self.object.pk)

        edit_scope = form.cleaned_data.get("edit_scope", "single")
        # WICHTIG: Verwende original_blocked_time statt self.object, um die RecurringBlockedTime zu finden
        matching_recurring = find_matching_recurring_blocked_time(original_blocked_time)

        if edit_scope == "series" and matching_recurring:
            # Bearbeite die ganze Serie (RecurringBlockedTime)
            recurring = matching_recurring
            
            # WICHTIG: Speichere die ursprüngliche start_time BEVOR wir sie ändern!
            original_start_time = recurring.start_time
            
            # WICHTIG: Finde alle BlockedTimes dieser Serie BEVOR wir die RecurringBlockedTime ändern!
            all_blocked_times = get_all_blocked_times_for_recurring(recurring, original_start_time=original_start_time)
            
            # Prüfe, ob sich die Wochentage geändert haben
            new_weekdays = form.cleaned_data.get("recurrence_weekdays", [])
            new_weekdays_set = set([int(wd) for wd in new_weekdays])
            old_weekdays_set = set(recurring.get_active_weekdays())
            weekdays_changed = new_weekdays_set != old_weekdays_set
            
            # Aktualisiere RecurringBlockedTime mit den neuen Werten
            recurring.title = form.cleaned_data["title"]
            recurring.description = form.cleaned_data["description"]
            recurring.start_time = form.cleaned_data["start_datetime"].time()
            recurring.end_time = form.cleaned_data["end_datetime"].time()
            
            # Aktualisiere Wochentage
            if new_weekdays:
                recurring.monday = "0" in new_weekdays
                recurring.tuesday = "1" in new_weekdays
                recurring.wednesday = "2" in new_weekdays
                recurring.thursday = "3" in new_weekdays
                recurring.friday = "4" in new_weekdays
                recurring.saturday = "5" in new_weekdays
                recurring.sunday = "6" in new_weekdays
            
            recurring.save()
            
            if weekdays_changed:
                # Wenn sich die Wochentage geändert haben:
                # 1. Lösche alle alten BlockedTimes, die nicht mehr zu den neuen Wochentagen passen
                # 2. Generiere neue BlockedTimes für die neuen Wochentage
                
                deleted_count = 0
                for blocked_time in all_blocked_times:
                    # Prüfe, ob diese BlockedTime zu den neuen Wochentagen passt
                    blocked_time_weekday = blocked_time.start_datetime.date().weekday()
                    if blocked_time_weekday not in new_weekdays_set:
                        # Diese BlockedTime gehört nicht mehr zu den neuen Wochentagen -> löschen
                        blocked_time.delete()
                        deleted_count += 1
                    else:
                        # Diese BlockedTime passt noch -> aktualisieren
                        blocked_time.title = recurring.title
                        blocked_time.description = recurring.description
                        # Behalte das Datum, aber aktualisiere die Zeit
                        blocked_time.start_datetime = blocked_time.start_datetime.replace(
                            hour=recurring.start_time.hour,
                            minute=recurring.start_time.minute
                        )
                        blocked_time.end_datetime = blocked_time.end_datetime.replace(
                            hour=recurring.end_time.hour,
                            minute=recurring.end_time.minute
                        )
                        blocked_time.save()
                        recalculate_conflicts_for_blocked_time(blocked_time)
                
                # Generiere neue BlockedTimes für die neuen Wochentage
                result = RecurringBlockedTimeService.generate_blocked_times(
                    recurring, check_conflicts=True, dry_run=False
                )
                created_count = result.get("created", 0)
                
                if result.get("conflicts"):
                    messages.warning(
                        self.request,
                        _("{count} conflict(s) detected in generated blocked times.").format(
                            count=len(result.get("conflicts", []))
                        ),
                    )
                
                messages.success(
                    self.request,
                    _("Series updated. {deleted} blocked time(s) deleted, {created} new blocked time(s) created, {updated} blocked time(s) updated.").format(
                        deleted=deleted_count,
                        created=created_count,
                        updated=len(all_blocked_times) - deleted_count
                    ),
                )
            else:
                # Wochentage haben sich nicht geändert -> nur bestehende BlockedTimes aktualisieren
                updated_count = 0
                for blocked_time in all_blocked_times:
                    # Aktualisiere diese BlockedTime mit den neuen Werten aus der RecurringBlockedTime
                    blocked_time.title = recurring.title
                    blocked_time.description = recurring.description
                    # Behalte das Datum, aber aktualisiere die Zeit
                    blocked_time.start_datetime = blocked_time.start_datetime.replace(
                        hour=recurring.start_time.hour,
                        minute=recurring.start_time.minute
                    )
                    blocked_time.end_datetime = blocked_time.end_datetime.replace(
                        hour=recurring.end_time.hour,
                        minute=recurring.end_time.minute
                    )
                    blocked_time.save()
                    updated_count += 1
                    recalculate_conflicts_for_blocked_time(blocked_time)
                
                messages.success(
                    self.request,
                    _("Series updated. {count} blocked time(s) updated.").format(count=updated_count),
                )
            
            # Setze self.object für die Weiterleitung
            self.object = original_blocked_time
        else:
            # Normale einzelne BlockedTime bearbeiten
            blocked_time = form.save()

            # Recalculate conflicts for affected lessons
            recalculate_conflicts_for_blocked_time(blocked_time)

            messages.success(self.request, _("Blocked time successfully updated."))

        return super().form_valid(form)


class BlockedTimeDeleteView(LoginRequiredMixin, DeleteView):
    """Blockzeit löschen."""

    model = BlockedTime
    template_name = "blocked_times/blockedtime_confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.blocked_times.recurring_utils import find_matching_recurring_blocked_time, get_all_blocked_times_for_recurring
        
        # Prüfe, ob diese BlockedTime zu einer Serie gehört
        matching_recurring = find_matching_recurring_blocked_time(self.object)
        context["matching_recurring"] = matching_recurring
        
        if matching_recurring:
            # Finde alle BlockedTimes dieser Serie
            all_blocked_times = get_all_blocked_times_for_recurring(matching_recurring)
            context["series_blocked_times_count"] = len(all_blocked_times)
            context["series_blocked_times"] = all_blocked_times
        
        return context

    def get_success_url(self):
        """Redirect back to last used calendar view (similar to LessonDeleteView)."""
        # Use year/month/day from request if available
        year = self.request.GET.get("year")
        month = self.request.GET.get("month")
        day = self.request.GET.get("day")
        
        # Get last used calendar view from session (default: week)
        last_view = self.request.session.get('last_calendar_view', 'week')
        
        if year and month:
            if last_view == 'week' and day:
                return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"
            elif last_view == 'week':
                # If no day provided, use current day
                from django.utils import timezone
                now = timezone.now()
                day = now.day
                return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"
            else:
                return reverse_lazy("lessons:calendar") + f"?year={year}&month={month}"
        return reverse_lazy("lessons:week")

    def delete(self, request, *args, **kwargs):
        from apps.blocked_times.recurring_models import RecurringBlockedTime
        from apps.blocked_times.recurring_utils import find_matching_recurring_blocked_time
        from apps.lessons.services import recalculate_conflicts_for_blocked_time
        from django.utils.translation import gettext_lazy as _, ngettext
        from django.http import HttpResponseRedirect

        blocked_time = self.get_object()
        blocked_time_date = blocked_time.start_datetime.date()
        
        # Prüfe, ob diese BlockedTime zu einer Serie gehört
        matching_recurring = find_matching_recurring_blocked_time(blocked_time)
        
        # Prüfe, ob der Benutzer die gesamte Serie löschen möchte
        delete_series = request.POST.get("delete_series", "false") == "true"
        
        if delete_series and matching_recurring:
            # Lösche die gesamte Serie
            start_date = matching_recurring.start_date
            end_date = matching_recurring.end_date
            
            # Finde alle BlockedTimes im Zeitraum mit gleichem Titel und gleicher Zeit
            all_blocked_times_query = BlockedTime.objects.filter(
                title=matching_recurring.title,
                start_datetime__time=matching_recurring.start_time,
                start_datetime__date__gte=start_date,
            )
            if end_date:
                all_blocked_times_query = all_blocked_times_query.filter(start_datetime__date__lte=end_date)
            
            # Hole alle IDs
            all_blocked_time_ids = list(all_blocked_times_query.values_list('id', flat=True))
            deleted_count = len(all_blocked_time_ids)
            
            # Lösche alle BlockedTimes der Serie direkt über die IDs
            if all_blocked_time_ids:
                BlockedTime.objects.filter(id__in=all_blocked_time_ids).delete()
            
            # Lösche die RecurringBlockedTime
            matching_recurring.delete()
            
            messages.success(
                request,
                ngettext(
                    "Series deleted. {count} blocked time deleted.",
                    "Series deleted. {count} blocked times deleted.",
                    deleted_count,
                ).format(count=deleted_count),
            )
        else:
            # Lösche nur diese eine BlockedTime
            # Recalculate conflicts before deleting (so we know which lessons to update)
            recalculate_conflicts_for_blocked_time(blocked_time)
            
            blocked_time.delete()
            messages.success(self.request, _("Blocked time successfully deleted."))
        
        return HttpResponseRedirect(self.get_success_url())
