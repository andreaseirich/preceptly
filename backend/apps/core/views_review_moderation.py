"""
Small, purpose-built review moderation page - not Django Admin, which is
deliberately disabled for this project (see
apps/core/tests/test_admin_disabled.py). Restricted to superusers only;
the flag is set directly on a User row, not through any admin UI.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from apps.core.models import Review


class ReviewModerationView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Review
    template_name = "core/review_moderation.html"
    context_object_name = "reviews"

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return Review.objects.select_related("user").order_by("is_approved", "-updated_at")


@require_POST
def moderate_review(request, pk):
    if not request.user.is_superuser:
        return redirect("core:dashboard")

    review = get_object_or_404(Review, pk=pk)
    action = request.POST.get("action")
    if action == "approve":
        review.is_approved = True
        review.save(update_fields=["is_approved"])
        messages.success(request, _("Review approved."))
    elif action == "reject":
        review.is_approved = False
        review.save(update_fields=["is_approved"])
        messages.success(request, _("Review rejected."))
    else:
        messages.error(request, _("Unknown action."))
    return redirect(reverse("core:review_moderation"))
