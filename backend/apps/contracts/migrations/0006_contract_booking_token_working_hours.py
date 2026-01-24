# Generated manually

import secrets

from django.db import migrations, models


def generate_tokens_for_existing_contracts(apps, schema_editor):
    """Generate booking tokens for existing contracts."""
    Contract = apps.get_model('contracts', 'Contract')
    for contract in Contract.objects.filter(booking_token__isnull=True):
        contract.booking_token = secrets.token_urlsafe(32)
        contract.save(update_fields=['booking_token'])


def reverse_generate_tokens(apps, schema_editor):
    """Reverse migration - no action needed."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0005_contract_has_monthly_planning_limit'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='booking_token',
            field=models.CharField(blank=True, help_text='Token for external booking link (auto-generated if empty)', max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='contract',
            name='working_hours',
            field=models.JSONField(blank=True, default=dict, help_text="Working hours for booking page (format: {'monday': [{'start': '09:00', 'end': '17:00'}], ...})"),
        ),
        migrations.RunPython(generate_tokens_for_existing_contracts, reverse_generate_tokens),
        migrations.AlterField(
            model_name='contract',
            name='booking_token',
            field=models.CharField(blank=True, help_text='Token for external booking link (auto-generated if empty)', max_length=64, null=True, unique=True),
        ),
    ]
