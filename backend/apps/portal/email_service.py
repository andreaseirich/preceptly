import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def send_portal_invite(student, portal_link, recipient_email, role="student"):
    """Send activation email to student or parent.

    portal_link may be a StudentPortalLink (student) or a ParentStudentLink (parent).
    Both have invite_token. The tutor is accessed via portal_user (student) or parent (parent).
    """
    # Empfängeradresse gegen Header-Injection und ungültige Adressen prüfen
    try:
        validate_email(recipient_email)
    except ValidationError:
        raise ValueError(f"Ungültige Empfänger-E-Mail-Adresse: {recipient_email!r}") from None

    # SITE_URL muss explizit konfiguriert sein – kein unsicherer Fallback auf Production
    if not hasattr(settings, "SITE_URL"):
        raise ImproperlyConfigured("settings.SITE_URL muss konfiguriert sein.")
    site_url = settings.SITE_URL

    activate_url = f"{site_url}/portal/activate/{portal_link.invite_token}/"
    # StudentPortalLink exposes portal_user; ParentStudentLink exposes parent (a PortalUser)
    portal_user = getattr(portal_link, "portal_user", None) or portal_link.parent
    tutor_name = portal_user.tutor.get_full_name() or portal_user.tutor.username

    context = {
        "student": student,
        "activate_url": activate_url,
        "tutor_name": tutor_name,
        "role": role,
        "site_url": site_url,
    }

    subject = _("Dein Preceptly Portal-Zugang")
    html_message = render_to_string("portal/email/invite.html", context)
    plain_message = render_to_string("portal/email/invite.txt", context)

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_email],
        html_message=html_message,
        fail_silently=False,
    )


def send_booking_notification_portal(session, tutor):
    """Benachrichtigung an Tutor nach Portal-Buchung: E-Mail und/oder Push,
    je nach NotificationPreference des Tutors (Typ "portal_booking")."""
    from apps.core.push_service import is_channel_enabled, send_push_notification

    student_name = session.contract.full_name
    date_str = session.date.strftime("%d.%m.%Y")
    time_str = session.start_time.strftime("%H:%M")
    topic = session.notes or "-"
    tutor_name = tutor.get_full_name() or tutor.username
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    dashboard_url = f"{site_url}/contracts/{session.contract.pk}/" if site_url else ""

    recipient = (tutor.email or "").strip()
    if recipient and is_channel_enabled(tutor, "portal_booking", "email"):
        subject = f"Neue Buchung: {student_name} — {date_str}".replace("\n", " ").replace("\r", " ")
        context = {
            "student_name": student_name,
            "date_str": date_str,
            "time_str": time_str,
            "topic": topic,
            "tutor_name": tutor_name,
            "site_url": site_url,
            "dashboard_url": dashboard_url,
        }
        html_message = render_to_string("portal/email/booking_notification.html", context)
        plain_message = render_to_string("portal/email/booking_notification.txt", context)
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                html_message=html_message,
                fail_silently=False,
            )
        except Exception:
            logger.exception(
                "Portal-Buchungsbenachrichtigung fehlgeschlagen für Session %s", session.pk
            )
    elif not recipient:
        logger.warning(
            "Tutor %s hat keine E-Mail-Adresse; Portal-Buchungsbenachrichtigung (E-Mail) übersprungen",
            tutor.username,
        )

    send_push_notification(
        tutor,
        "portal_booking",
        title=f"Neue Buchung: {student_name}",
        body=f"{date_str} um {time_str} Uhr",
        url=dashboard_url or None,
    )


def send_activation_notification(portal_user, contract):
    """Benachrichtigung an Tutor nach Portal-Aktivierung (fail_silently)."""
    notification_email = (getattr(settings, "NOTIFICATION_EMAIL", None) or "").strip()
    if not notification_email:
        logger.warning(
            "NOTIFICATION_EMAIL nicht gesetzt; Aktivierungsbenachrichtigung übersprungen"
        )
        return
    student_name = contract.full_name
    role_display = "Schüler" if portal_user.role == "student" else "Elternteil"
    timestamp = timezone.now().strftime("%d.%m.%Y %H:%M")
    subject = f"Portal-Zugang aktiviert: {student_name}".replace("\n", " ").replace("\r", " ")
    message = (
        f"Ein Portal-Zugang wurde aktiviert.\n\n"
        f"Schüler: {student_name}\n"
        f"Rolle: {role_display}\n"
        f"Zeitpunkt: {timestamp}\n"
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Aktivierungsbenachrichtigung fehlgeschlagen für PortalUser %s", portal_user.pk
        )


def send_login_reminder(contract, recipient_email, tutor_name, role="student", recipient_user=None):
    """Login-Erinnerung an bereits aktive Portal-Nutzer senden (E-Mail und/oder Push).

    `recipient_user` is the recipient's Django User (student's or parent's portal
    account), used to check their NotificationPreference (type "login_reminder") and
    to send a push notification. If not passed, email is always sent (preserves the
    old always-on-email behavior for call sites that don't have the user object).
    """
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    try:
        validate_email(recipient_email)
    except ValidationError:
        raise ValueError(f"Ungültige Empfänger-E-Mail-Adresse: {recipient_email!r}") from None

    if not hasattr(settings, "SITE_URL"):
        raise ImproperlyConfigured("settings.SITE_URL muss konfiguriert sein.")
    site_url = settings.SITE_URL

    login_url = f"{site_url}/portal/login/"

    send_email = True
    if recipient_user is not None:
        from apps.core.push_service import is_channel_enabled, send_push_notification

        send_email = is_channel_enabled(recipient_user, "login_reminder", "email")
        send_push_notification(
            recipient_user,
            "login_reminder",
            title="Dein Preceptly Portal-Zugang",
            body=f"Erinnerung von {tutor_name}: Logg dich in dein Portal ein.",
            url=login_url,
        )

    if not send_email:
        return

    context = {
        "contract": contract,
        "recipient_email": recipient_email,
        "tutor_name": tutor_name,
        "role": role,
        "site_url": site_url,
        "login_url": login_url,
        "password_reset_url": f"{site_url}/portal/password-reset/",
    }

    subject = _("Dein Preceptly Portal-Zugang")
    html_message = render_to_string("portal/email/login_reminder.html", context)
    plain_message = render_to_string("portal/email/login_reminder.txt", context)

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_email],
        html_message=html_message,
        fail_silently=False,
    )
