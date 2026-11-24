"""Portal: Bewertung abgeben, aktualisieren und zurückziehen (docs/features/feat-portal-bewertungen.md). Anmeldung über die Portal-Sitzung (`get_portal_user`)."""

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View

from apps.core.models import Review
from apps.portal.reviews import PortalReviewForm, can_review
from apps.portal.views import get_portal_user


class PortalReviewView(View):
    http_method_names = ["post"]

    def post(self, request):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        if not can_review(portal_user):
            messages.error(request, "Die Bewertung ist für dein Konto nicht vorgesehen.")
            return redirect("portal:home")

        review = Review.objects.filter(user=portal_user.user).first() or Review(
            user=portal_user.user
        )
        form = PortalReviewForm(request.POST, instance=review)
        if not form.is_valid():
            problems = " ".join(error for errors in form.errors.values() for error in errors)
            messages.error(request, f"Die Bewertung wurde nicht gespeichert. {problems}")
            return redirect("portal:home")
        review = form.save(commit=False)
        review.source = portal_user.role
        review.publish_consent_at = timezone.now()
        review.save()
        messages.success(
            request,
            "Danke für deine Bewertung! Sie erscheint erst nach einer kurzen Prüfung öffentlich.",
        )
        return redirect("portal:home")


class PortalReviewWithdrawView(View):
    http_method_names = ["post"]

    def post(self, request):
        portal_user = get_portal_user(request)
        if not portal_user:
            return redirect("portal:login")
        Review.objects.filter(user=portal_user.user).exclude(source="tutor").delete()
        messages.success(request, "Deine Bewertung wurde zurückgezogen und gelöscht.")
        return redirect("portal:home")
