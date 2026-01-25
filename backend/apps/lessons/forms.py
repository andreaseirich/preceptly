"""
Forms für Lesson-Model.
"""

from apps.lessons.models import Lesson, LessonDocument
from django import forms
from django.utils.translation import gettext_lazy as _


class LessonForm(forms.ModelForm):
    """Form für Lesson-Erstellung und -Bearbeitung."""

    # Option für Bearbeitung: nur diese Stunde oder ganze Serie
    edit_scope = forms.ChoiceField(
        required=False,
        initial="single",
        choices=[
            ("single", _("Edit only this lesson")),
            ("series", _("Edit entire series")),
        ],
        label=_("Edit scope"),
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )

    # Recurrence fields (only shown when creating, not editing)
    is_recurring = forms.BooleanField(
        required=False,
        label=_("Repeat this lesson"),
        help_text=_("Create a recurring series instead of a single lesson"),
        widget=forms.CheckboxInput(
            attrs={"class": "form-check-input", "onchange": "toggleRecurrenceFields()"}
        ),
    )
    recurrence_type = forms.ChoiceField(
        required=False,
        choices=[
            ("", _("None")),
            ("weekly", _("Weekly")),
            ("biweekly", _("Every 2 Weeks")),
            ("monthly", _("Monthly")),
        ],
        label=_("Repeat pattern"),
        widget=forms.Select(attrs={"class": "form-control", "style": "display: none;"}),
    )
    recurrence_end_date = forms.DateField(
        required=False,
        label=_("End date"),
        help_text=_("When should the series end? (optional)"),
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date", "style": "display: none;"}
        ),
    )
    recurrence_weekdays = forms.MultipleChoiceField(
        required=False,
        choices=[
            ("0", _("Monday")),
            ("1", _("Tuesday")),
            ("2", _("Wednesday")),
            ("3", _("Thursday")),
            ("4", _("Friday")),
            ("5", _("Saturday")),
            ("6", _("Sunday")),
        ],
        label=_("Weekdays"),
        help_text=_("Select weekdays for the recurring lesson"),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Lesson
        fields = [
            "contract",
            "date",
            "start_time",
            "duration_minutes",
            "travel_time_before_minutes",
            "travel_time_after_minutes",
            "notes",
        ]
        widgets = {
            "contract": forms.Select(attrs={"class": "form-control"}),
            "date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
            "start_time": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}, format="%H:%M"
            ),
            "duration_minutes": forms.NumberInput(attrs={"class": "form-control"}),
            "travel_time_before_minutes": forms.NumberInput(attrs={"class": "form-control"}),
            "travel_time_after_minutes": forms.NumberInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide recurrence fields when editing (only show when creating)
        if self.instance and self.instance.pk:
            self.fields["is_recurring"].widget = forms.HiddenInput()
            self.fields["recurrence_type"].widget = forms.HiddenInput()
            self.fields["recurrence_end_date"].widget = forms.HiddenInput()

            # Prüfe, ob diese Lesson zu einer Serie gehört
            from apps.lessons.recurring_utils import find_matching_recurring_lesson

            matching_recurring = find_matching_recurring_lesson(self.instance)
            if matching_recurring:
                # Zeige Option für Bearbeitungsscope
                self.fields["edit_scope"].initial = "single"
                # Wenn Serie bearbeitet wird, zeige Wochentage-Felder
                # Initialisiere mit aktuellen Wochentagen der Serie
                active_weekdays = matching_recurring.get_active_weekdays()
                self.fields["recurrence_weekdays"].initial = [str(wd) for wd in active_weekdays]
                # Widget immer sichtbar machen - wird per JavaScript gesteuert
                # WICHTIG: Kein HiddenInput, damit Checkboxes gerendert werden
                self.fields["recurrence_weekdays"].widget = forms.CheckboxSelectMultiple(
                    attrs={"class": "form-check-input"}
                )
            else:
                # Verstecke edit_scope und recurrence_weekdays, wenn keine Serie gefunden
                self.fields["edit_scope"].widget = forms.HiddenInput()
            self.fields["recurrence_weekdays"].widget = forms.HiddenInput()
        else:
            # Beim Erstellen: edit_scope verstecken
            self.fields["edit_scope"].widget = forms.HiddenInput()

    def clean(self):
        """Validiere Recurrence-Felder."""
        cleaned_data = super().clean()

        is_recurring = cleaned_data.get("is_recurring", False)

        if is_recurring:
            recurrence_type = cleaned_data.get("recurrence_type")
            recurrence_weekdays = cleaned_data.get("recurrence_weekdays", [])

            if not recurrence_type:
                raise forms.ValidationError(
                    _("Please select a repeat pattern when creating a recurring lesson.")
                )

            if not recurrence_weekdays:
                raise forms.ValidationError(
                    _("Please select at least one weekday when creating a recurring lesson.")
                )

        return cleaned_data


class LessonDocumentForm(forms.ModelForm):
    """Form für LessonDocument-Upload."""

    class Meta:
        model = LessonDocument
        fields = ["file", "name"]
        widgets = {
            "file": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png",
                }
            ),
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Optional: Document name")}
            ),
        }

    def clean_file(self):
        """Validiere Datei-Größe und -Typ."""
        file = self.cleaned_data.get("file")
        if file:
            # Maximale Dateigröße: 10 MB
            max_size = 10 * 1024 * 1024  # 10 MB
            if file.size > max_size:
                raise forms.ValidationError(
                    _("File size must be less than 10 MB. Current size: {size} MB").format(
                        size=round(file.size / (1024 * 1024), 2)
                    )
                )

            # Erlaubte Dateitypen
            allowed_extensions = [".pdf", ".doc", ".docx", ".txt", ".jpg", ".jpeg", ".png"]
            file_extension = file.name.lower().split(".")[-1] if "." in file.name else ""
            if file_extension and f".{file_extension}" not in allowed_extensions:
                raise forms.ValidationError(
                    _("File type not allowed. Allowed types: PDF, DOC, DOCX, TXT, JPG, PNG")
                )

        return file


class MultipleFileInput(forms.FileInput):
    """Custom FileInput Widget that supports multiple file uploads."""

    def __init__(self, attrs=None):
        super().__init__(attrs)
        if attrs is None:
            attrs = {}
        attrs["multiple"] = True
        self.attrs = attrs


class MultipleLessonDocumentForm(forms.Form):
    """Form für mehrere Dokumente auf einmal."""

    files = forms.FileField(
        widget=MultipleFileInput(
            attrs={
                "class": "form-control",
                "accept": ".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png",
            }
        ),
        help_text=_("You can upload multiple files at once"),
    )

    def clean_files(self):
        """Validiere Dateien."""
        files = self.files.getlist("files")
        if not files:
            raise forms.ValidationError(_("Please select at least one file."))

        max_size = 10 * 1024 * 1024  # 10 MB
        allowed_extensions = [".pdf", ".doc", ".docx", ".txt", ".jpg", ".jpeg", ".png"]

        for file in files:
            if file.size > max_size:
                raise forms.ValidationError(
                    _("File '{name}' is too large. Maximum size: 10 MB").format(name=file.name)
                )

            file_extension = file.name.lower().split(".")[-1] if "." in file.name else ""
            if file_extension and f".{file_extension}" not in allowed_extensions:
                raise forms.ValidationError(
                    _(
                        "File '{name}' has an invalid type. Allowed types: PDF, DOC, DOCX, TXT, JPG, PNG"
                    ).format(name=file.name)
                )

        return files
