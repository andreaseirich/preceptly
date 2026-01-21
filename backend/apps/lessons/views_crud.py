"""
Views for lesson CRUD operations.
"""

from apps.lessons.forms import LessonForm
from apps.lessons.models import Lesson
from apps.lessons.recurring_service import RecurringLessonService
from apps.lessons.services import LessonConflictService
from apps.lessons.status_service import LessonStatusService
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView


class LessonListView(LoginRequiredMixin, ListView):
    """List of all lessons."""

    model = Lesson
    template_name = "lessons/lesson_list.html"
    context_object_name = "lessons"
    paginate_by = 50

    def get_queryset(self):
        """Filter lessons by date range if provided."""
        queryset = super().get_queryset()
        
        # Filter by date range if provided
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        return queryset.order_by("-date", "-start_time")


class LessonDetailView(LoginRequiredMixin, DetailView):
    """Detail view of a lesson."""

    model = Lesson
    template_name = "lessons/lesson_detail.html"
    context_object_name = "lesson"


class LessonCreateView(LoginRequiredMixin, CreateView):
    """Create a new lesson."""

    model = Lesson
    form_class = LessonForm
    template_name = "lessons/lesson_form.html"

    def get_success_url(self):
        """Redirect back to calendar view."""
        lesson = self.object
        # Use year/month/day from request if available, otherwise from lesson date
        year = int(self.request.GET.get("year", lesson.date.year))
        month = int(self.request.GET.get("month", lesson.date.month))
        day = self.request.GET.get("day", lesson.date.day)
        return reverse_lazy("lessons:calendar") + f"?year={year}&month={month}"

    def get_initial(self):
        """Pre-fill form with date/time from request parameters."""
        initial = super().get_initial()
        
        # Get date from request
        date_str = self.request.GET.get("date")
        if date_str:
            try:
                from datetime import datetime
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                initial["date"] = date_obj
            except ValueError:
                pass
        
        # Get time from request
        time_str = self.request.GET.get("time")
        if time_str:
            try:
                from datetime import datetime
                time_obj = datetime.strptime(time_str, "%H:%M").time()
                initial["start_time"] = time_obj
            except ValueError:
                pass
        
        return initial

    def form_valid(self, form):
        from apps.lessons.services import recalculate_conflicts_for_affected_lessons
        from apps.lessons.recurring_models import RecurringLesson
        from apps.lessons.recurring_service import RecurringLessonService
        from django.utils.translation import ngettext

        # Prüfe, ob eine Serientermin erstellt werden soll
        is_recurring = form.cleaned_data.get("is_recurring", False)

        if is_recurring:
            # Erstelle eine RecurringLesson statt einer einzelnen Lesson
            lesson = form.save(commit=False)  # Noch nicht speichern
            
            # Erstelle RecurringLesson
            recurring_lesson = RecurringLesson(
                contract=lesson.contract,
                start_date=lesson.date,
                end_date=form.cleaned_data.get("recurrence_end_date"),
                start_time=lesson.start_time,
                duration_minutes=lesson.duration_minutes,
                travel_time_before_minutes=lesson.travel_time_before_minutes,
                travel_time_after_minutes=lesson.travel_time_after_minutes,
                recurrence_type=form.cleaned_data.get("recurrence_type", "weekly"),
                notes=lesson.notes,
                is_active=True,
            )
            
            # Setze Wochentage basierend auf recurrence_weekdays
            weekdays = form.cleaned_data.get("recurrence_weekdays", [])
            recurring_lesson.monday = "0" in weekdays
            recurring_lesson.tuesday = "1" in weekdays
            recurring_lesson.wednesday = "2" in weekdays
            recurring_lesson.thursday = "3" in weekdays
            recurring_lesson.friday = "4" in weekdays
            recurring_lesson.saturday = "5" in weekdays
            recurring_lesson.sunday = "6" in weekdays
            
            recurring_lesson.save()
            
            # Generiere Lessons aus der RecurringLesson
            result = RecurringLessonService.generate_lessons(recurring_lesson, check_conflicts=True)
            
            if result["created"] > 0:
                messages.success(
                    self.request,
                    ngettext(
                        "Recurring lesson series created and {count} lesson generated.",
                        "Recurring lesson series created and {count} lessons generated.",
                        result["created"],
                    ).format(count=result["created"]),
                )
            else:
                messages.info(
                    self.request,
                    _("Recurring lesson series created, but no new lessons were generated (they may already exist)."),
                )

            if result["conflicts"]:
                conflict_count = len(result["conflicts"])
                messages.warning(
                    self.request,
                    ngettext(
                        "{count} lesson with conflicts detected.",
                        "{count} lessons with conflicts detected.",
                        conflict_count,
                    ).format(count=conflict_count),
                )
            
            # Setze self.object für die Weiterleitung
            # Verwende die erste erstellte Lesson oder die erste gefundene Lesson
            if result.get("created", 0) > 0:
                # Finde die erste erstellte Lesson
                from apps.lessons.models import Lesson
                first_lesson = Lesson.objects.filter(
                    contract=recurring_lesson.contract,
                    date__gte=recurring_lesson.start_date,
                    start_time=recurring_lesson.start_time,
                ).order_by("date").first()
                self.object = first_lesson
            else:
                # Falls keine Lesson erstellt wurde, verwende die ursprüngliche Lesson
                lesson.save()
                LessonStatusService.update_status_for_lesson(lesson)
                self.object = lesson
        else:
            # Normale einzelne Lesson erstellen
            lesson = form.save()

            # Automatic status setting
            LessonStatusService.update_status_for_lesson(lesson)

            # Recalculate conflicts for this lesson and affected lessons
            recalculate_conflicts_for_affected_lessons(lesson)

            conflicts = LessonConflictService.check_conflicts(lesson)
            if conflicts:
                messages.warning(
                    self.request,
                    _("Lesson created, but {count} conflict(s) detected!").format(count=len(conflicts)),
                )
            else:
                messages.success(self.request, _("Lesson successfully created."))

        return super().form_valid(form)


class LessonUpdateView(LoginRequiredMixin, UpdateView):
    """Update a lesson."""

    model = Lesson
    form_class = LessonForm
    template_name = "lessons/lesson_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.lessons.recurring_utils import find_matching_recurring_lesson
        
        # Prüfe, ob diese Lesson zu einer Serie gehört
        matching_recurring = find_matching_recurring_lesson(self.object)
        context["matching_recurring"] = matching_recurring
        
        return context

    def get_success_url(self):
        """Redirect back to calendar view."""
        lesson = self.object
        # Use year/month/day from request if available, otherwise from lesson date
        year = int(self.request.GET.get("year", lesson.date.year))
        month = int(self.request.GET.get("month", lesson.date.month))
        day = self.request.GET.get("day", lesson.date.day)
        return reverse_lazy("lessons:calendar") + f"?year={year}&month={month}"

    def form_valid(self, form):
        from apps.lessons.services import recalculate_conflicts_for_affected_lessons
        from apps.lessons.recurring_utils import find_matching_recurring_lesson

        # WICHTIG: Hole die ursprüngliche Lesson-Instanz aus der Datenbank,
        # bevor wir nach der RecurringLesson suchen (self.object hat bereits die geänderten Werte)
        original_lesson = Lesson.objects.get(pk=self.object.pk)

        edit_scope = form.cleaned_data.get("edit_scope", "single")
        # WICHTIG: Verwende original_lesson statt self.object, um die RecurringLesson zu finden
        matching_recurring = find_matching_recurring_lesson(original_lesson)

        if edit_scope == "series" and matching_recurring:
            # Bearbeite die ganze Serie (RecurringLesson)
            recurring = matching_recurring
            
            # WICHTIG: Speichere die ursprüngliche start_time BEVOR wir sie ändern!
            original_start_time = recurring.start_time
            
            # WICHTIG: Finde alle Lessons dieser Serie BEVOR wir die RecurringLesson ändern!
            # (Sonst finden wir sie nicht mehr, da sie noch die alte start_time haben)
            from apps.lessons.recurring_utils import get_all_lessons_for_recurring
            
            all_lessons = get_all_lessons_for_recurring(recurring, original_start_time=original_start_time)
            
            # Prüfe, ob sich die Wochentage geändert haben
            new_weekdays = form.cleaned_data.get("recurrence_weekdays", [])
            new_weekdays_set = set([int(wd) for wd in new_weekdays])
            old_weekdays_set = set(recurring.get_active_weekdays())
            weekdays_changed = new_weekdays_set != old_weekdays_set
            
            # Aktualisiere RecurringLesson mit den neuen Werten
            recurring.start_time = form.cleaned_data["start_time"]
            recurring.duration_minutes = form.cleaned_data["duration_minutes"]
            recurring.travel_time_before_minutes = form.cleaned_data["travel_time_before_minutes"]
            recurring.travel_time_after_minutes = form.cleaned_data["travel_time_after_minutes"]
            recurring.notes = form.cleaned_data["notes"]
            
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
                # 1. Lösche alle alten Lessons, die nicht mehr zu den neuen Wochentagen passen
                # 2. Generiere neue Lessons für die neuen Wochentage
                
                deleted_count = 0
                for lesson in all_lessons:
                    # Prüfe, ob diese Lesson zu den neuen Wochentagen passt
                    lesson_weekday = lesson.date.weekday()
                    if lesson_weekday not in new_weekdays_set:
                        # Diese Lesson gehört nicht mehr zu den neuen Wochentagen -> löschen
                        lesson.delete()
                        deleted_count += 1
                    else:
                        # Diese Lesson passt noch -> aktualisieren
                        lesson.start_time = recurring.start_time
                        lesson.duration_minutes = recurring.duration_minutes
                        lesson.travel_time_before_minutes = recurring.travel_time_before_minutes
                        lesson.travel_time_after_minutes = recurring.travel_time_after_minutes
                        lesson.notes = recurring.notes
                        LessonStatusService.update_status_for_lesson(lesson)
                        lesson.save()
                        recalculate_conflicts_for_affected_lessons(lesson)
                
                # Generiere neue Lessons für die neuen Wochentage
                result = RecurringLessonService.generate_lessons(
                    recurring, check_conflicts=True, dry_run=False
                )
                created_count = result.get("created", 0)
                
                if result.get("conflicts"):
                    messages.warning(
                        self.request,
                        _("{count} conflict(s) detected in generated lessons.").format(
                            count=len(result.get("conflicts", []))
                        ),
                    )
                
                messages.success(
                    self.request,
                    _("Series updated. {deleted} lesson(s) deleted, {created} new lesson(s) created, {updated} lesson(s) updated.").format(
                        deleted=deleted_count,
                        created=created_count,
                        updated=len(all_lessons) - deleted_count
                    ),
                )
            else:
                # Wochentage haben sich nicht geändert -> nur bestehende Lessons aktualisieren
                updated_count = 0
                for lesson in all_lessons:
                    # Aktualisiere diese Lesson mit den neuen Werten aus der RecurringLesson
                    lesson.start_time = recurring.start_time
                    lesson.duration_minutes = recurring.duration_minutes
                    lesson.travel_time_before_minutes = recurring.travel_time_before_minutes
                    lesson.travel_time_after_minutes = recurring.travel_time_after_minutes
                    lesson.notes = recurring.notes
                    LessonStatusService.update_status_for_lesson(lesson)
                    lesson.save()
                    updated_count += 1
                    
                    # Recalculate conflicts
                    recalculate_conflicts_for_affected_lessons(lesson)
                
                messages.success(
                    self.request,
                    _("Series updated. {count} lesson(s) updated.").format(count=updated_count),
                )
        else:
            # Bearbeite nur diese eine Stunde
            lesson = form.save()

            # Automatic status setting
            LessonStatusService.update_status_for_lesson(lesson)

            # Recalculate conflicts for this lesson and affected lessons
            recalculate_conflicts_for_affected_lessons(lesson)

            conflicts = LessonConflictService.check_conflicts(lesson)
            if conflicts:
                messages.warning(
                    self.request,
                    _("Lesson updated, but {count} conflict(s) detected!").format(count=len(conflicts)),
                )
            else:
                messages.success(self.request, _("Lesson successfully updated."))
        
        return super().form_valid(form)


class LessonDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a lesson."""

    model = Lesson
    template_name = "lessons/lesson_confirm_delete.html"

    def get_success_url(self):
        """Redirect back to calendar view."""
        # Use year/month/day from request if available
        year = self.request.GET.get("year")
        month = self.request.GET.get("month")
        if year and month:
            return reverse_lazy("lessons:calendar") + f"?year={year}&month={month}"
        return reverse_lazy("lessons:list")

    def delete(self, request, *args, **kwargs):
        from apps.lessons.services import recalculate_conflicts_for_affected_lessons

        lesson = self.get_object()
        lesson_date = lesson.date
        
        messages.success(self.request, _("Lesson successfully deleted."))
        result = super().delete(request, *args, **kwargs)
        
        # Recalculate conflicts for affected lessons on the same date
        # (We need to create a temporary lesson object with the date to check conflicts)
        from apps.lessons.models import Lesson
        temp_lesson = Lesson(date=lesson_date)
        recalculate_conflicts_for_affected_lessons(temp_lesson)
        
        return result
