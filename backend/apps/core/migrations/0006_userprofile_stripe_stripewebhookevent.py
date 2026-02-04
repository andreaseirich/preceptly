# Generated manually for Stripe subscription support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_userprofile_next_invoice_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="stripe_customer_id",
            field=models.CharField(
                blank=True,
                help_text="Stripe Customer ID",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="stripe_subscription_id",
            field=models.CharField(
                blank=True,
                help_text="Stripe Subscription ID",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="stripe_price_id",
            field=models.CharField(
                blank=True,
                help_text="Stripe Price ID for current plan",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="premium_source",
            field=models.CharField(
                blank=True,
                help_text="Source of premium: 'stripe', 'manual', or null",
                max_length=20,
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="StripeWebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.CharField(db_index=True, max_length=255, unique=True)),
                ("event_type", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("payload_summary", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "Stripe Webhook Event",
                "verbose_name_plural": "Stripe Webhook Events",
            },
        ),
    ]
