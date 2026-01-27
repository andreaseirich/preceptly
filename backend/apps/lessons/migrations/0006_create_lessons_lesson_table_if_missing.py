# Generated manually to fix missing lessons_lesson table

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0006_contract_booking_token_working_hours'),
        ('lessons', '0005_lessondocument'),
    ]

    operations = [
        # Create Session model (which uses db_table="lessons_lesson")
        migrations.CreateModel(
            name='Session',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(help_text='Session date')),
                ('start_time', models.TimeField(help_text='Start time')),
                ('duration_minutes', models.PositiveIntegerField(help_text='Duration in minutes', validators=[django.core.validators.MinValueValidator(1)])),
                ('status', models.CharField(choices=[('planned', 'Planned'), ('taught', 'Taught'), ('cancelled', 'Cancelled'), ('paid', 'Paid')], default='planned', help_text='Session status', max_length=20)),
                ('travel_time_before_minutes', models.PositiveIntegerField(default=0, help_text='Travel time before in minutes')),
                ('travel_time_after_minutes', models.PositiveIntegerField(default=0, help_text='Travel time after in minutes')),
                ('notes', models.TextField(blank=True, help_text='Notes for the session', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('contract', models.ForeignKey(help_text='Associated contract', on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='contracts.contract')),
            ],
            options={
                'db_table': 'lessons_lesson',
                'ordering': ['-date', '-start_time'],
                'verbose_name': 'Session',
                'verbose_name_plural': 'Sessions',
            },
        ),
        migrations.AddIndex(
            model_name='session',
            index=models.Index(fields=['date', 'start_time'], name='lessons_les_date_e38248_idx'),
        ),
        migrations.AddIndex(
            model_name='session',
            index=models.Index(fields=['status'], name='lessons_les_status_ff86f9_idx'),
        ),
    ]
