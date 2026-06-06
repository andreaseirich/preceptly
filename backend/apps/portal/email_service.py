from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.translation import gettext as _


def send_portal_invite(student, portal_link, recipient_email, role="student"):
    """Send activation email to student or parent.

    portal_link may be a StudentPortalLink (student) or a ParentStudentLink (parent).
    Both have invite_token. The tutor is accessed via portal_user (student) or parent (parent).
    """
    site_url = getattr(settings, "SITE_URL", "https://preceptly.up.railway.app")
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
