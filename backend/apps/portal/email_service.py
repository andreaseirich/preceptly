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

    subject = _("Your Preceptly Portal Access")
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
    """Benachrichtigung an Tutor nach Portal-Buchung — geht an die E-Mail-Adresse des Tutors."""
    recipient = (tutor.email or "").strip()
    if not recipient:
        logger.warning(
            "Tutor %s hat keine E-Mail-Adresse; Portal-Buchungsbenachrichtigung übersprungen",
            tutor.username,
        )
        return
    student_name = session.contract.full_name
    date_str = session.date.strftime("%d.%m.%Y")
    time_str = session.start_time.strftime("%H:%M")
    topic = session.notes or "-"
    tutor_name = tutor.get_full_name() or tutor.username
    subject = f"Neue Portal-Buchung: {student_name} - {date_str}".replace("\n", " ").replace(
        "\r", " "
    )
    message = (
        f"Ein neuer Termin wurde über das Portal gebucht.\n\n"
        f"Schüler: {student_name}\n"
        f"Datum: {date_str}\n"
        f"Uhrzeit: {time_str} Uhr\n"
        f"Thema: {topic}\n"
        f"Tutor: {tutor_name}\n"
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Portal-Buchungsbenachrichtigung fehlgeschlagen für Session %s", session.pk
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
