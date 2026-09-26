"""
Forms for core app.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import Expense, Review


class UserEmailForm(forms.ModelForm):
    """Adds an email address to an account that has none yet."""

    class Meta:
        model = User
        fields = ("email",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["email"].label = _("Email address")
        self.fields["email"].help_text = _(
            "Needed to restore access to your account, for invoices and important notices."
        )


class RegisterForm(UserCreationForm):
    """Registration form for new tutor accounts. No premium by default."""

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("Username")
        # Pflicht seit 26.09.2026: ohne Adresse lässt sich ein vergessenes
        # Passwort nicht zurücksetzen und der Tutor ist nicht erreichbar.
        self.fields["email"].required = True
        self.fields["email"].label = _("Email address")
        self.fields["email"].help_text = _(
            "Required. Lets you restore access to your account and receive invoices "
            "and important notices."
        )
        self.fields["password1"].label = _("Password")
        self.fields["password2"].label = _("Password confirmation")
        # Generic error to avoid account enumeration
        self.error_messages["duplicate_username"] = _(
            "Registration failed. Please try a different username or contact support."
        )

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                self.error_messages["duplicate_username"],
                code="duplicate_username",
            )
        return username


class WorkingHoursForm(forms.Form):
    """Form for editing default working hours."""

    # Wochentage
    WEEKDAYS = [
        ("monday", _("Monday")),
        ("tuesday", _("Tuesday")),
        ("wednesday", _("Wednesday")),
        ("thursday", _("Thursday")),
        ("friday", _("Friday")),
        ("saturday", _("Saturday")),
        ("sunday", _("Sunday")),
    ]

    def __init__(self, *args, **kwargs):
        initial_working_hours = kwargs.pop("initial_working_hours", {})
        super().__init__(*args, **kwargs)

        # Create dynamic fields for each weekday
        for weekday_key, weekday_label in self.WEEKDAYS:
            # Checkbox whether the day is enabled
            self.fields[f"{weekday_key}_enabled"] = forms.BooleanField(
                required=False,
                label=f"{weekday_label} - {_('Enabled')}",
                initial=bool(initial_working_hours.get(weekday_key)),
            )

            # Start and end time for the day
            day_hours = initial_working_hours.get(weekday_key, [])
            if day_hours and len(day_hours) > 0:
                first_period = day_hours[0]
                self.fields[f"{weekday_key}_start"] = forms.TimeField(
                    required=False,
                    label=f"{weekday_label} - {_('Start time')}",
                    initial=first_period.get("start", "09:00"),
                    widget=forms.TimeInput(attrs={"type": "time", "format": "%H:%M"}),
                )
                self.fields[f"{weekday_key}_end"] = forms.TimeField(
                    required=False,
                    label=f"{weekday_label} - {_('End time')}",
                    initial=first_period.get("end", "17:00"),
                    widget=forms.TimeInput(attrs={"type": "time", "format": "%H:%M"}),
                )
            else:
                self.fields[f"{weekday_key}_start"] = forms.TimeField(
                    required=False,
                    label=f"{weekday_label} - {_('Start time')}",
                    initial="09:00",
                    widget=forms.TimeInput(attrs={"type": "time", "format": "%H:%M"}),
                )
                self.fields[f"{weekday_key}_end"] = forms.TimeField(
                    required=False,
                    label=f"{weekday_label} - {_('End time')}",
                    initial="17:00",
                    widget=forms.TimeInput(attrs={"type": "time", "format": "%H:%M"}),
                )

    def clean(self):
        cleaned_data = super().clean()
        working_hours = {}

        for weekday_key, _weekday_label in self.WEEKDAYS:
            enabled = cleaned_data.get(f"{weekday_key}_enabled", False)
            if enabled:
                start = cleaned_data.get(f"{weekday_key}_start")
                end = cleaned_data.get(f"{weekday_key}_end")

                if start and end:
                    if start >= end:
                        raise forms.ValidationError(
                            _("Start time must be before end time for {weekday}.").format(
                                weekday=_weekday_label
                            )
                        )
                    working_hours[weekday_key] = [
                        {"start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")}
                    ]

        cleaned_data["working_hours"] = working_hours
        return cleaned_data


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["date", "amount", "category", "description", "notes", "business_use_percent"]
        widgets = {
            "date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
                format="%Y-%m-%d",
            ),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "business_use_percent": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 100, "step": 1}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure YYYY-MM-DD format for rendering AND parsing,
        # independent of USE_L10N (HTML date inputs always use YYYY-MM-DD)
        self.fields["date"].input_formats = ["%Y-%m-%d"]
        if not self.instance.pk:
            self.fields["date"].initial = timezone.localdate()


class ReviewForm(forms.ModelForm):
    """Star rating + optional written feedback about Preceptly."""

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "rating": forms.RadioSelect(
                choices=[(i, i) for i in range(1, 6)], attrs={"class": "star-rating-input"}
            ),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _(
                        "Optional: what do you like, what's missing, what should change?"
                    ),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rating"].required = True
        self.fields["comment"].required = False
        self.fields["rating"].label = _("Your rating")
        self.fields["comment"].label = _("Your feedback")
