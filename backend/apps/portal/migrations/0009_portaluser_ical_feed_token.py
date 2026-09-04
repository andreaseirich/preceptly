import uuid

from django.db import migrations, models


def assign_unique_tokens(apps, schema_editor):
    """The AddField below intentionally leaves the column nullable with no
    default - a single default value applied via ALTER TABLE would give
    every existing row the SAME token (verified the hard way: this exact
    mistake took the site down on first deploy). Assign a fresh uuid4()
    per row here instead, before the next migration makes the column
    required and unique."""
    PortalUser = apps.get_model("portal", "PortalUser")
    for portal_user in PortalUser.objects.filter(ical_feed_token__isnull=True):
        portal_user.ical_feed_token = uuid.uuid4()
        portal_user.save(update_fields=["ical_feed_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0008_migrate_student_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="portaluser",
            name="ical_feed_token",
            field=models.UUIDField(null=True, blank=True, editable=False),
        ),
        migrations.RunPython(assign_unique_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="portaluser",
            name="ical_feed_token",
            field=models.UUIDField(
                default=uuid.uuid4,
                unique=True,
                editable=False,
                help_text=(
                    "Unguessable token identifying this user's read-only calendar "
                    "feed URL - the token itself is the auth, no login required."
                ),
            ),
        ),
    ]
