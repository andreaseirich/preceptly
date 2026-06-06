from django.db import migrations, models
import django.db.models.deletion


def copy_document_student_to_contract(apps, schema_editor):
    Contract = apps.get_model("contracts", "Contract")
    StudentDocument = apps.get_model("students", "StudentDocument")
    for doc in StudentDocument.objects.all():
        c = Contract.objects.filter(student_id=doc.student_id).first()
        if c:
            doc.new_student = c
            doc.save(update_fields=["new_student_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0009_studentdocument"),
        ("contracts", "0010_contract_copy_student_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentdocument",
            name="new_student",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="documents",
                to="contracts.contract",
                verbose_name="Schüler/Vertrag",
            ),
        ),
        migrations.RunPython(copy_document_student_to_contract, migrations.RunPython.noop),
        migrations.RemoveField(model_name="studentdocument", name="student"),
        migrations.RenameField(
            model_name="studentdocument", old_name="new_student", new_name="student"
        ),
        migrations.AlterField(
            model_name="studentdocument",
            name="student",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="documents",
                to="contracts.contract",
                verbose_name="Schüler/Vertrag",
            ),
        ),
    ]
