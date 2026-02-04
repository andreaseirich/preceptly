# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_userprofile_stripe_customer_id_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="stripe_email_last_synced",
            field=models.CharField(
                blank=True,
                help_text="Last email synced to Stripe Customer (skip modify if unchanged)",
                max_length=254,
                null=True,
            ),
        ),
    ]
