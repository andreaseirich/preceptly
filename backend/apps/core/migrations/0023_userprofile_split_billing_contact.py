from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_userprofile_billing_kleinunternehmer"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userprofile",
            name="billing_contact",
        ),
        migrations.AddField(
            model_name="userprofile",
            name="billing_email",
            field=models.EmailField(
                blank=True,
                max_length=254,
                verbose_name="E-Mail (Rechnungen)",
                help_text="Deine geschäftliche E-Mail-Adresse für Rechnungen.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="billing_phone",
            field=models.CharField(
                blank=True,
                max_length=30,
                verbose_name="Telefon",
                help_text="Deine Telefonnummer (optional).",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="billing_website",
            field=models.URLField(
                blank=True,
                verbose_name="Website",
                help_text="Deine Website (optional, z. B. https://example.de).",
            ),
        ),
    ]
