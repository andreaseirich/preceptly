"""Tarif-Sperren für Views.

Regel für alle gesperrten Funktionen: Neues anlegen und Ändern erst ab dem
passenden Tarif. Ansehen, Absagen und Löschen bleiben immer möglich - läuft
ein Abo aus, verlieren Schüler und Eltern nicht, was schon da ist.

Welcher Tarif was freischaltet, steht in ``feature_flags.FEATURE_MIN_TIER``.
"""

from django.contrib import messages
from django.shortcuts import redirect

from apps.core.feature_flags import FEATURE_MIN_TIER, Feature, Tier, user_has_feature

TIER_LABEL = {
    Tier.FREE: "Free",
    Tier.STARTER: "Starter",
    Tier.PRO: "Pro",
    Tier.BUSINESS: "Business",
}

FEATURE_LABEL = {
    Feature.FEATURE_RECURRING_LESSONS: "Serientermine",
    Feature.FEATURE_BLOCKED_TIMES: "Sperrzeiten",
    Feature.FEATURE_STUDENT_PORTAL: "Das Schüler-Portal",
    Feature.FEATURE_PARENT_PORTAL: "Der Familien-Zugang (mehrere Kinder an einem Portal-Konto)",
    Feature.FEATURE_MEETING_ROOMS: "Meeting-Räume",
}


def denied_message(feature: Feature) -> str:
    tier = TIER_LABEL[FEATURE_MIN_TIER[feature]]
    return f"{FEATURE_LABEL[feature]} gibt es ab dem {tier}-Tarif (Einstellungen → Abo)."


def deny(request, feature: Feature, to: str, *args, **kwargs):
    """Hinweis anzeigen und zurückleiten."""
    messages.info(request, denied_message(feature))
    return redirect(to, *args, **kwargs)


class FeatureRequiredMixin:
    """Für Views, die nur mit ``required_feature`` erreichbar sein dürfen.

    Nach ``LoginRequiredMixin`` einsetzen, damit Unangemeldete zuerst zum Login gehen."""

    required_feature: Feature | None = None
    feature_denied_redirect = "core:dashboard"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not user_has_feature(
            request.user, self.required_feature
        ):
            return deny(request, self.required_feature, self.feature_denied_redirect)
        return super().dispatch(request, *args, **kwargs)
