from django.db import migrations, models, models
import django.db.models.deletion


def copy_lessonplan_student_to_contract(apps, schema_editor):
    Contract = apps.get_model("contracts", "Contract")
    LessonPlan = apps.get_model("lesson_plans", "LessonPlan")
    for plan in LessonPlan.objects.all():
        c = Contract.objects.filter(student_id=plan.student_id).first()
        if c:
            plan.contract_id = c.pk
            plan.save(update_fields=["contract_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("lesson_plans", "0003_alter_lessonplan_lesson"),
        ("contracts", "0010_contract_copy_student_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="lessonplan",
            name="contract",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lesson_plans",
                to="contracts.contract",
            ),
        ),
        migrations.RunPython(copy_lessonplan_student_to_contract, migrations.RunPython.noop),
        migrations.RemoveIndex(model_name="lessonplan", name="lesson_plan_student_893e49_idx"),
        migrations.RemoveField(model_name="lessonplan", name="student"),
        migrations.AddIndex(
            model_name="lessonplan",
            index=models.Index(fields=["contract", "-created_at"], name="lesson_plan_contract_idx"),
        ),
        migrations.AlterField(
            model_name="lessonplan",
            name="contract",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lesson_plans",
                to="contracts.contract",
            ),
        ),
    ]
