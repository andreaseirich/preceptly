"""
CRUD views for lessons (List, Create, Update, Detail, Delete).
"""

from datetime import date

from apps.lessons.forms import LessonForm
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.lessons.recurring_service import RecurringLessonService
from apps.lessons.services import LessonConflictService
from apps.lessons.status_service import LessonStatusService
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView


class LessonListView(LoginRequiredMixin, ListView):
    """List of all lessons."""

    model = Lesson
    template_name = "lessons/lesson_list.html"
    context_object_name = "lessons"
    paginate_by = 30

    def get_queryset(self):
        """Extends queryset with conflict information."""
        queryset = super().get_queryset().select_related("contract", "contract__student")
        # Add conflict info
        for lesson in queryset:
            lesson.conflicts = LessonConflictService.check_conflicts(lesson)
        return queryset


class LessonCreateView(LoginRequiredMixin, CreateView):
    """Create a new lesson."""

    model = Lesson
    form_class = LessonForm
    template_name = "lessons/lesson_form.html"

    def get_initial(self):
        """Sets initial values, e.g., date and times from query parameters."""
        initial = super().get_initial()

        # Support for start/end from drag-to-create
        start_param = self.request.GET.get("start")
        end_param = self.request.GET.get("end")

        if start_param and end_param:
            try:
                from datetime import datetime

                start_dt = datetime.fromisoformat(start_param.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_param.replace("Z", "+00:00"))

                # Convert to timezone-aware if needed
                if timezone.is_naive(start_dt):
                    start_dt = timezone.make_aware(start_dt)
                if timezone.is_naive(end_dt):
                    end_dt = timezone.make_aware(end_dt)

                initial["date"] = start_dt.date()
                initial["start_time"] = start_dt.time()

                # Calculate duration in minutes
                duration = (end_dt - start_dt).total_seconds() / 60
                initial["duration_minutes"] = int(duration)

                return initial
            except (ValueError, TypeError):
                pass

        # Fallback: Normal date parameters
        date_param = self.request.GET.get("date")
        if date_param:
            try:
                parsed_date = date.fromisoformat(date_param)
                initial["date"] = parsed_date
            except (ValueError, TypeError):
                year_param = self.request.GET.get("year")
                month_param = self.request.GET.get("month")
                if year_param and month_param:
                    try:
                        initial["date"] = date(int(year_param), int(month_param), 1)
                    except (ValueError, TypeError):
                        initial["date"] = timezone.localdate()
                else:
                    initial["date"] = timezone.localdate()
        else:
            year_param = self.request.GET.get("year")
            month_param = self.request.GET.get("month")
            if year_param and month_param:
                try:
                    initial["date"] = date(int(year_param), int(month_param), 1)
                except (ValueError, TypeError):
                    initial["date"] = timezone.localdate()
            else:
                initial["date"] = timezone.localdate()
        return initial

    def get_success_url(self):
        """Redirect back to week view."""
        if hasattr(self, "object") and self.object:
            lesson = self.object
            return (
                reverse_lazy("lessons:week")
                + f"?year={lesson.date.year}&month={lesson.date.month}&day={lesson.date.day}"
            )
        # Fallback
        return reverse_lazy("lessons:week")

    def form_valid(self, form):
        is_recurring = form.cleaned_data.get("is_recurring", False)

        if is_recurring:
            # Create RecurringLesson instead of single lesson
            recurrence_type = form.cleaned_data.get("recurrence_type")
            recurrence_end_date = form.cleaned_data.get("recurrence_end_date")
            recurrence_weekdays = form.cleaned_data.get("recurrence_weekdays", [])

            if not recurrence_type or not recurrence_weekdays:
                form.add_error(
                    "is_recurring",
                    _("Please select a recurrence pattern and at least one weekday."),
                )
                return self.form_invalid(form)

            # Create RecurringLesson
            recurring_lesson = RecurringLesson.objects.create(
                contract=form.cleaned_data["contract"],
                start_date=form.cleaned_data["date"],
                end_date=recurrence_end_date,
                start_time=form.cleaned_data["start_time"],
                duration_minutes=form.cleaned_data["duration_minutes"],
                travel_time_before_minutes=form.cleaned_data.get("travel_time_before_minutes", 0),
                travel_time_after_minutes=form.cleaned_data.get("travel_time_after_minutes", 0),
                recurrence_type=recurrence_type,
                notes=form.cleaned_data.get("notes", ""),
                monday="0" in recurrence_weekdays,
                tuesday="1" in recurrence_weekdays,
                wednesday="2" in recurrence_weekdays,
                thursday="3" in recurrence_weekdays,
                friday="4" in recurrence_weekdays,
                saturday="5" in recurrence_weekdays,
                sunday="6" in recurrence_weekdays,
            )

            # Generate lessons from recurring lesson
            result = RecurringLessonService.generate_lessons(
                recurring_lesson, check_conflicts=True, dry_run=False
            )

            # Set self.object to first generated lesson for redirect
            generated_lessons = Lesson.objects.filter(
                contract=form.cleaned_data["contract"],
                date=form.cleaned_data["date"],
                start_time=form.cleaned_data["start_time"],
            ).order_by("date", "start_time")

            if generated_lessons.exists():
                self.object = generated_lessons.first()
            else:
                # Fallback: create single lesson
                self.object = form.save()
                LessonStatusService.update_status_for_lesson(self.object)

            messages.success(
                self.request,
                _("Recurring lesson created and {count} lesson(s) generated.").format(
                    count=result.get("created", 0)
                ),
            )

            if result.get("conflicts"):
                messages.warning(
                    self.request,
                    _("{count} conflict(s) detected in generated lessons.").format(
                        count=len(result.get("conflicts", []))
                    ),
                )
        else:
            # Create single lesson as before
            lesson = form.save()
            self.object = lesson

            # Automatic status setting
            LessonStatusService.update_status_for_lesson(lesson)

            conflicts = LessonConflictService.check_conflicts(lesson, exclude_self=False)
            if conflicts:
                messages.warning(
                    self.request,
                    _("Lesson created, but {count} conflict(s) detected!").format(
                        count=len(conflicts)
                    ),
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

        edit_scope = form.cleaned_data.get("edit_scope", "single")
        matching_recurring = find_matching_recurring_lesson(self.object)

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


class LessonDetailView(LoginRequiredMixin, DetailView):
    """Detail view of a lesson with conflict information and premium features."""

    model = Lesson
    template_name = "lessons/lesson_detail.html"
    context_object_name = "lesson"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lesson = self.object

        # Load conflicts
        conflicts = LessonConflictService.check_conflicts(lesson, exclude_self=True)

        # Extract conflict lessons
        conflict_lessons = []
        conflict_blocked_times = []
        quota_conflicts = []

        for conflict in conflicts:
            if conflict["type"] == "lesson":
                conflict_lessons.append(conflict["object"])
            elif conflict["type"] == "blocked_time":
                conflict_blocked_times.append(conflict["object"])
            elif conflict["type"] == "quota":
                quota_conflicts.append(conflict)

        # LessonPlan information
        from apps.core.utils import is_premium_user
        from apps.lesson_plans.models import LessonPlan

        lesson_plans = LessonPlan.objects.filter(lesson=lesson).order_by("-created_at")

        context.update(
            {
                "conflicts": conflicts,
                "conflict_lessons": conflict_lessons,
                "conflict_blocked_times": conflict_blocked_times,
                "quota_conflicts": quota_conflicts,
                "has_conflicts": len(conflicts) > 0,
                "lesson_plans": lesson_plans,
                "has_lesson_plan": lesson_plans.exists(),
                "latest_lesson_plan": lesson_plans.first() if lesson_plans.exists() else None,
                "is_premium": is_premium_user(self.request.user)
                if self.request.user.is_authenticated
                else False,
            }
        )

        return context


class LessonDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a lesson."""

    model = Lesson
    template_name = "lessons/lesson_confirm_delete.html"

    def get_success_url(self):
        """Redirect back to week view."""
        lesson = self.object
        year = int(self.request.GET.get("year", lesson.date.year))
        month = int(self.request.GET.get("month", lesson.date.month))
        day = self.request.GET.get("day", lesson.date.day)
        return reverse_lazy("lessons:week") + f"?year={year}&month={month}&day={day}"

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Lesson successfully deleted."))
        return super().delete(request, *args, **kwargs)
