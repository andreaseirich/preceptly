import hashlib
import os
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from apps.core.models import RequestLog

User = get_user_model()

SESSION_KEY = "dev_stats_authed"


def _check_password(raw: str) -> bool:
    expected = os.environ.get("DEV_STATS_PASSWORD", "")
    if not expected:
        return False
    return secrets.compare_digest(
        hashlib.sha256(raw.encode()).hexdigest(),
        hashlib.sha256(expected.encode()).hexdigest(),
    )


class DevStatsView(View):
    def get(self, request):
        if not request.session.get(SESSION_KEY):
            return render(request, "core/dev_stats_login.html", {"error": False})
        return self._dashboard(request)

    def post(self, request):
        action = request.POST.get("action")
        if action == "logout":
            request.session.pop(SESSION_KEY, None)
            return redirect("core:dev_stats")

        password = request.POST.get("password", "")
        if _check_password(password):
            request.session[SESSION_KEY] = True
            request.session.set_expiry(28800)  # 8 Stunden
            return redirect("core:dev_stats")
        return render(request, "core/dev_stats_login.html", {"error": True})

    def _dashboard(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        qs_base = RequestLog.objects.all()

        requests_today = qs_base.filter(timestamp__gte=today_start).count()
        requests_week = qs_base.filter(timestamp__gte=week_start).count()
        requests_month = qs_base.filter(timestamp__gte=month_start).count()

        unique_ips_today = (
            qs_base.filter(timestamp__gte=today_start).values("ip").distinct().count()
        )

        last_7d = now - timedelta(days=7)
        top_paths = list(
            qs_base.filter(timestamp__gte=last_7d)
            .exclude(path__startswith="/static/")
            .exclude(path__startswith="/health/")
            .exclude(path__startswith="/media/")
            .values("path")
            .annotate(count=Count("id"))
            .order_by("-count")[:15]
        )

        last_24h = now - timedelta(hours=24)

        hours_data = []
        for i in range(23, -1, -1):
            h_start = now - timedelta(hours=i + 1)
            h_end = now - timedelta(hours=i)
            count = qs_base.filter(timestamp__gte=h_start, timestamp__lt=h_end).count()
            hours_data.append({"hour": h_start.strftime("%H:00"), "count": count})

        days_data = []
        for i in range(29, -1, -1):
            d_start = today_start - timedelta(days=i)
            d_end = d_start + timedelta(days=1)
            count = qs_base.filter(timestamp__gte=d_start, timestamp__lt=d_end).count()
            days_data.append({"day": d_start.strftime("%d.%m."), "count": count})

        status_qs = qs_base.filter(timestamp__gte=last_7d)
        status_2xx = status_qs.filter(status_code__gte=200, status_code__lt=300).count()
        status_3xx = status_qs.filter(status_code__gte=300, status_code__lt=400).count()
        status_4xx = status_qs.filter(status_code__gte=400, status_code__lt=500).count()
        status_5xx = status_qs.filter(status_code__gte=500, status_code__lt=600).count()

        new_users_30d = User.objects.filter(date_joined__gte=month_start).count()
        try:
            from apps.portal.models import PortalUser

            new_portal_users_30d = PortalUser.objects.filter(created_at__gte=month_start).count()
        except Exception:
            new_portal_users_30d = None

        recent_errors = list(
            qs_base.filter(status_code__gte=400).values("path", "status_code", "timestamp", "ip")[
                :50
            ]
        )

        top_agents = list(
            qs_base.filter(timestamp__gte=last_7d)
            .exclude(user_agent="")
            .values("user_agent")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        avg_response = qs_base.filter(timestamp__gte=last_24h, response_ms__isnull=False).aggregate(
            avg=Avg("response_ms")
        )["avg"]
        avg_response = round(avg_response, 1) if avg_response else None

        max_hour_count = max((h["count"] for h in hours_data), default=1) or 1
        max_day_count = max((d["count"] for d in days_data), default=1) or 1

        context = {
            "requests_today": requests_today,
            "requests_week": requests_week,
            "requests_month": requests_month,
            "unique_ips_today": unique_ips_today,
            "top_paths": top_paths,
            "hours_data": hours_data,
            "days_data": days_data,
            "status_2xx": status_2xx,
            "status_3xx": status_3xx,
            "status_4xx": status_4xx,
            "status_5xx": status_5xx,
            "new_users_30d": new_users_30d,
            "new_portal_users_30d": new_portal_users_30d,
            "recent_errors": recent_errors,
            "top_agents": top_agents,
            "avg_response": avg_response,
            "max_hour_count": max_hour_count,
            "max_day_count": max_day_count,
            "now": now,
        }
        return render(request, "core/dev_stats.html", context)
