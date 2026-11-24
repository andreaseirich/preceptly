"""Bewertungen von Eltern und Schülern im Portal: Berechtigung, Formular und Karte (docs/features/feat-portal-bewertungen.md).

Portal-Konten haben keinen Vornamen (Benutzername `portal_<Nr>_<Zufall>`, E-Mail). Der Anzeigename wird deshalb beim Bewerten eingegeben; Benutzername und E-Mail werden nie angezeigt.
"""

import re

from django import forms

from apps.core.models import Review
from apps.portal.models import ParentStudentLink

COMMENT_MAX = 1000
NAME_MIN, NAME_MAX = 2, 30
ADDRESS_LIKE = re.compile(
    r"@|://|www\.|\b[\w-]+\.(?:de|com|org|net|eu|info|at|ch)\b", re.IGNORECASE
)


def can_review(portal_user):
    """Eltern mit mindestens einem aktiven Kind; Schüler nur, wenn alle ihre aktiven Verträge volljährig sind."""
    contracts = [
        link.contract
        for link in ParentStudentLink.objects.filter(
            parent=portal_user, is_active=True
        ).select_related("contract")
    ]
    if not contracts:
        return False
    if portal_user.role == "parent":
        return True
    if portal_user.role == "student":
        return all(contract.is_adult for contract in contracts)
    return False


class PortalReviewForm(forms.ModelForm):
    consent = forms.BooleanField(
        required=True,
        label="Einwilligung",
        error_messages={
            "required": "Ohne Einwilligung kann die Bewertung nicht veröffentlicht werden."
        },
    )

    class Meta:
        model = Review
        fields = ["rating", "comment", "display_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rating"].label = "Sterne"
        self.fields["rating"].error_messages["required"] = "Bitte wähle 1 bis 5 Sterne."
        self.fields["display_name"].label = "Vorname"
        self.fields["display_name"].required = True
        self.fields["comment"].label = "Kommentar"
        self.fields["comment"].required = False

    def clean_display_name(self):
        name = (self.cleaned_data.get("display_name") or "").strip()
        if not NAME_MIN <= len(name) <= NAME_MAX:
            raise forms.ValidationError(f"Der Vorname braucht {NAME_MIN} bis {NAME_MAX} Zeichen.")
        if ADDRESS_LIKE.search(name):
            raise forms.ValidationError(
                "Bitte nur einen Vornamen angeben, keine E-Mail- oder Internetadresse."
            )
        return name

    def clean_comment(self):
        comment = (self.cleaned_data.get("comment") or "").strip()
        if len(comment) > COMMENT_MAX:
            raise forms.ValidationError(
                f"Der Kommentar darf höchstens {COMMENT_MAX} Zeichen lang sein."
            )
        return comment


def review_card(portal_user):
    """Daten für die Karte im Portal-Dashboard, oder None, wenn das Konto nicht bewerten darf."""
    if not can_review(portal_user):
        return None
    return {
        "review": Review.objects.filter(user=portal_user.user).exclude(source="tutor").first(),
        "comment_max": COMMENT_MAX,
    }
