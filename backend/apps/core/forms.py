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
