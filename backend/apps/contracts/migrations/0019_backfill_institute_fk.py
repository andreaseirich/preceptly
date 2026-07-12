from django.db import migrations


def backfill(apps, schema_editor):
    Contract = apps.get_model("contracts", "Contract")
    Institute = apps.get_model("contracts", "Institute")
    UserProfile = apps.get_model("core", "UserProfile")

    contracts_with_institute = Contract.objects.exclude(institute__isnull=True).exclude(
        institute=""
    )

    # (user_id, institute_name_lower) -> Institute instance
    resolved = {}

    for contract in contracts_with_institute.only("id", "user_id", "institute"):
        name = contract.institute.strip()
        if not name:
            continue
        cache_key = (contract.user_id, name.lower())
        institute = resolved.get(cache_key)
        if institute is None:
            institute = Institute.objects.filter(
                user_id=contract.user_id, institute_name__iexact=name
            ).first()
            if institute is None:
                institute = Institute.objects.create(user_id=contract.user_id, institute_name=name)
            resolved[cache_key] = institute
        contract.institute_fk_id = institute.pk
        contract.save(update_fields=["institute_fk"])

    # Carry the old global per-tutor settings onto every tiered institute of
    # that tutor, matching the runtime behaviour before this migration (the
    # global setting applied to whichever institute(s) had tiered pay).
    for profile in UserProfile.objects.all():
        pct = profile.tutor_no_show_pay_percent or 0
        cutoff = profile.tutorspace_tier_count_from
        if not pct and not cutoff:
            continue
        tiered_institutes = [
            inst for inst in Institute.objects.filter(user_id=profile.user_id) if inst.tiers
        ]
        for institute in tiered_institutes:
            update_fields = []
            if pct:
                institute.tutor_no_show_pay_percent = pct
                update_fields.append("tutor_no_show_pay_percent")
            if cutoff:
                institute.tier_count_from = cutoff
                update_fields.append("tier_count_from")
            if update_fields:
                institute.save(update_fields=update_fields)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0018_contract_institute_fk"),
        ("core", "0026_revocationrequest"),
    ]

    operations = [
        migrations.RunPython(backfill, noop_reverse),
    ]
