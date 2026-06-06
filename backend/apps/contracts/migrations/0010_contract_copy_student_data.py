from django.db import migrations


def copy_student_to_contract(apps, schema_editor):
    Contract = apps.get_model("contracts", "Contract")
    for contract in Contract.objects.select_related("student"):
        if not contract.student_id:
            continue
        s = contract.student
        contract.user_id = s.user_id
        contract.first_name = s.first_name
        contract.last_name = s.last_name
        contract.email = s.email
        contract.phone = s.phone
        contract.school = s.school
        contract.grade = s.grade
        contract.subjects = s.subjects
        contract.is_adult = s.is_adult
        contract.booking_code_hash = s.booking_code_hash
        contract.save(
            update_fields=[
                "user_id",
                "first_name",
                "last_name",
                "email",
                "phone",
                "school",
                "grade",
                "subjects",
                "is_adult",
                "booking_code_hash",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0009_contract_add_student_fields"),
    ]

    operations = [
        migrations.RunPython(copy_student_to_contract, migrations.RunPython.noop),
    ]
