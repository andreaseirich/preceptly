from django.db import migrations


def migrate_student_links_forward(apps, schema_editor):
    """Kopiert jeden StudentPortalLink in die vereinheitlichte ParentStudentLink-Tabelle.

    Bei Verträgen, die sowohl einen Student- als auch einen separaten
    Eltern-Login haben (Ein-Kind-Familie mit zwei Accounts), bleibt der
    Schüler-Login bestehen; der separate Eltern-Account wird deaktiviert,
    nicht gelöscht (Nachrichtenhistorie bleibt erhalten)."""
    StudentPortalLink = apps.get_model("portal", "StudentPortalLink")
    ParentStudentLink = apps.get_model("portal", "ParentStudentLink")

    for spl in StudentPortalLink.objects.select_related("portal_user", "contract").all():
        # Bereits vorhandene separate Eltern-Accounts für denselben Vertrag deaktivieren
        # (Schüler-Login gewinnt), aber deren Historie erhalten.
        other_parent_links = ParentStudentLink.objects.filter(contract_id=spl.contract_id).exclude(
            parent_id=spl.portal_user_id
        )
        for pl in other_parent_links:
            if pl.is_active:
                pl.is_active = False
                pl.save(update_fields=["is_active"])
            parent_django_user = pl.parent.user
            if parent_django_user.is_active:
                parent_django_user.is_active = False
                parent_django_user.save(update_fields=["is_active"])

        # StudentPortalLink -> ParentStudentLink übernehmen (falls noch nicht vorhanden)
        ParentStudentLink.objects.get_or_create(
            parent_id=spl.portal_user_id,
            contract_id=spl.contract_id,
            defaults={
                "invite_token": spl.invite_token,
                "invite_token_created_at": spl.invite_token_created_at,
                "is_active": spl.is_active,
                "reset_token": spl.reset_token,
                "reset_token_created_at": spl.reset_token_created_at,
            },
        )


def migrate_student_links_backward(apps, schema_editor):
    # Kein Rückweg nötig: StudentPortalLink-Tabelle existiert zu diesem
    # Migrationszeitpunkt noch unverändert, die kopierten Zeilen in
    # ParentStudentLink werden beim Zurückrollen einfach stehen gelassen.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0007_unify_parent_link"),
    ]

    operations = [
        migrations.RunPython(migrate_student_links_forward, migrate_student_links_backward),
    ]
