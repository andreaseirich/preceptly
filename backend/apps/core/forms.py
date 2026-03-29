"""
Forms for core app.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class UserEmailForm(forms.ModelForm):
    """Form to edit user email (optional, for Stripe/invoices)."""

    class Meta:
        model = User
        fields = ("email",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False
        self.fields["email"].label = _("Email address")
        self.fields["email"].help_text = _(
            "Optional. Used for invoices and Stripe billing. Recommended for Premium."
        )


class RegisterForm(UserCreationForm):
    """Registration form for new tutor accounts. No premium by default."""

    class Meta:
        model = User
        fields = ("username", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("Username")
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


class TravelPolicyForm(forms.Form):
    """Form for transport mode for on-site appointments (no technical details shown)."""

    TRANSPORT_CHOICES = [
        ("oepnv", _("Public transport (time-dependent)")),
        ("fahrrad", _("Bicycle (constant short buffer)")),
    ]
    transport_mode = forms.ChoiceField(
        choices=TRANSPORT_CHOICES,
        label=_("Travel mode for on-site appointments"),
        help_text=_(
            "Determines which time slots are offered for on-site appointments. "
            "Public transport uses time-dependent rules; bicycle uses a fixed buffer."
        ),
    )
    fahrrad_buffer_minutes = forms.IntegerField(
        min_value=5,
        max_value=60,
        initial=25,
        required=False,
        label=_("Buffer (minutes) when using bicycle"),
        help_text=_("Only used when bicycle is selected. Typical: 20–30 minutes."),
    )

    def clean_fahrrad_buffer_minutes(self):
        value = self.cleaned_data.get("fahrrad_buffer_minutes")
        if value is None:
            return 25
        return max(5, min(60, value))


class TutorNoShowPayForm(forms.Form):
    """Percentage of TutorSpace pay when session is marked tutor no-show (student waited)."""

    tutor_no_show_pay_percent = forms.IntegerField(
        min_value=0,
        max_value=100,
        initial=0,
        label=_("Pay when you missed the lesson (student was waiting)"),
        help_text=_(
            "TutorSpace only, if you mark “you did not attend, student was waiting”: share of "
            "the usual lesson pay you keep. You are not paid the rest, and the usual amount "
            "is deducted (e.g. 0%% → line shows −full usual amount; 100%% → full pay, no "
            "deduction)."
        ),
    )

    def clean_tutor_no_show_pay_percent(self):
        value = self.cleaned_data.get("tutor_no_show_pay_percent")
        if value is None:
            return 0
        return max(0, min(100, int(value)))


class TutorSpaceTierCountFromForm(forms.Form):
    """Optional start date for TutorSpace tier cumulative (13/14 € steps)."""

    tutorspace_tier_count_from = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date"},
            format="%Y-%m-%d",
        ),
        label=_("Count TutorSpace tier hours only from (optional)"),
        help_text=_(
            "Empty: every past TutorSpace lesson counts toward the 13/14 € tiers (all pupils "
            "together). Set a date if the preview or amounts look wrong because many older "
            "lessons are included—only lessons on or after this date will count."
        ),
    )
