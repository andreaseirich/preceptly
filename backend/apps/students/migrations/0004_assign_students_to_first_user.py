# Data migration: Assign existing students to first user

from django.db import migrations


def assign_students_to_user(apps, schema_editor):
    """Assign all students without user to the first existing user."""
    Student = apps.get_model("students", "Student")
    User = apps.get_model("auth", "User")

    unassigned = Student.objects.filter(user__isnull=True)
    if not unassigned.exists():
        return

    first_user = User.objects.order_by("id").first()
    if not first_user:
        raise RuntimeError(
            "Multi-tenancy migration requires at least one user. "
            "Please create a user first, then run migrate again."
        )
    unassigned.update(user=first_user)


def reverse_assign(apps, schema_editor):
    """Reverse: set user to null (only if we need to rollback)."""
    Student = apps.get_model("students", "Student")
    Student.objects.all().update(user=None)


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0003_student_user"),
    ]

    operations = [
        migrations.RunPython(assign_students_to_user, reverse_assign),
    ]
