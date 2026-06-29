from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0021_userprofile_billing_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="billing_kleinunternehmer",
            field=models.BooleanField(
                default=False,
                verbose_name="Kleinunternehmerregelung (§19 UStG)",
                help_text=(
                    "Aktivieren wenn du die Kleinunternehmerregelung nutzt. "
                    'Fügt den Hinweis "Gemäß §19 Abs. 1 UStG wird keine Umsatzsteuer '
                    'berechnet." zur Rechnung hinzu.'
                ),
            ),
        ),
    ]
