from django.db import migrations, models
import django.db.models.deletion


def copy_portal_student_to_contract(apps, schema_editor):
    Contract = apps.get_model("contracts", "Contract")
    StudentPortalLink = apps.get_model("portal", "StudentPortalLink")
    ParentStudentLink = apps.get_model("portal", "ParentStudentLink")
    ProgressNote = apps.get_model("portal", "ProgressNote")
    PortalMessage = apps.get_model("portal", "PortalMessage")

    for link in StudentPortalLink.objects.all():
        c = Contract.objects.filter(student_id=link.student_id).first()
        if c:
            link.contract_id = c.pk
            link.save(update_fields=["contract_id"])

    for link in ParentStudentLink.objects.all():
        c = Contract.objects.filter(student_id=link.student_id).first()
        if c:
            link.contract_id = c.pk
            link.save(update_fields=["contract_id"])

    for note in ProgressNote.objects.all():
        c = Contract.objects.filter(student_id=note.student_id).first()
        if c:
            note.contract_id = c.pk
            note.save(update_fields=["contract_id"])

    for msg in PortalMessage.objects.all():
        c = Contract.objects.filter(student_id=msg.student_id).first()
        if c:
            msg.contract_id = c.pk
            msg.save(update_fields=["contract_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0002_parentstudentlink_invite_token_is_active"),
        ("contracts", "0010_contract_copy_student_data"),
    ]

    operations = [
        # 1. Add nullable contract FKs
        migrations.AddField(
            model_name="studentportallink",
            name="contract",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="portal_link",
                to="contracts.contract",
            ),
        ),
        migrations.AddField(
            model_name="parentstudentlink",
            name="contract",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="parent_links",
                to="contracts.contract",
            ),
        ),
        migrations.AddField(
            model_name="progressnote",
            name="contract",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="progress_notes",
                to="contracts.contract",
            ),
        ),
        migrations.AddField(
            model_name="portalmessage",
            name="contract",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="portal_messages",
                to="contracts.contract",
            ),
        ),
        # 2. Data migration
        migrations.RunPython(copy_portal_student_to_contract, migrations.RunPython.noop),
        # 3. Remove old unique_together, student FKs
        migrations.AlterUniqueTogether(name="parentstudentlink", unique_together=set()),
        migrations.RemoveField(model_name="studentportallink", name="student"),
        migrations.RemoveField(model_name="parentstudentlink", name="student"),
        migrations.RemoveField(model_name="progressnote", name="student"),
        migrations.RemoveField(model_name="portalmessage", name="student"),
        # 4. Make contract FKs non-null
        migrations.AlterField(
            model_name="studentportallink",
            name="contract",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="portal_link",
                to="contracts.contract",
            ),
        ),
        migrations.AlterField(
            model_name="parentstudentlink",
            name="contract",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="parent_links",
                to="contracts.contract",
            ),
        ),
        migrations.AlterField(
            model_name="progressnote",
            name="contract",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="progress_notes",
                to="contracts.contract",
            ),
        ),
        migrations.AlterField(
            model_name="portalmessage",
            name="contract",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="portal_messages",
                to="contracts.contract",
            ),
        ),
        # 5. Restore unique_together with new field
        migrations.AlterUniqueTogether(
            name="parentstudentlink",
            unique_together={("parent", "contract")},
        ),
    ]
