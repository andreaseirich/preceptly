# Generated manually for stripe_customer_id uniqueness

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_userprofile_stripe_stripewebhookevent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="stripe_customer_id",
            field=models.CharField(
                blank=True,
                help_text="Stripe Customer ID",
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
    ]
