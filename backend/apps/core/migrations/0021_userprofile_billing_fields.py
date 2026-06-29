from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0020_remove_is_premium_rename_premium_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="billing_name",
            field=models.CharField(
                blank=True,
                max_length=200,
                verbose_name="Name / Firma",
                help_text="Dein vollständiger Name oder Firmenname, der auf Rechnungen erscheint.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="billing_address",
            field=models.TextField(
                blank=True,
                verbose_name="Adresse",
                help_text="Straße, PLZ, Ort – wird auf Rechnungen angezeigt.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="billing_tax_number",
            field=models.CharField(
                blank=True,
                max_length=50,
                verbose_name="Steuernummer / USt-IdNr.",
                help_text="Deine persönliche Steuernummer oder Umsatzsteuer-ID.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="billing_contact",
            field=models.CharField(
                blank=True,
                max_length=300,
                verbose_name="Kontakt",
                help_text="E-Mail, Telefon, Website – erscheint auf Rechnungen.",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="billing_bank_iban",
            field=models.CharField(
                blank=True,
                max_length=34,
                verbose_name="IBAN",
                help_text="Bankverbindung für Rechnungen (optional).",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="billing_bank_bic",
            field=models.CharField(
                blank=True,
                max_length=11,
                verbose_name="BIC",
                help_text="BIC/SWIFT deiner Bank (optional).",
            ),
        ),
    ]
