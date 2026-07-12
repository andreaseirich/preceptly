import re
from decimal import Decimal, InvalidOperation

from django.db import migrations

# Mirrors apps.contracts.tutorspace_compensation.TIERS at the time this migration was
# written — used only as a fallback when a TutorSpace tier's label can't be parsed.
_BUILTIN_TUTORSPACE_RATES_BY_HOURS_FROM = {
    0: Decimal("13"),
    50: Decimal("14"),
    150: Decimal("15"),
    450: Decimal("16"),
    1000: Decimal("17"),
}

_NUMBER_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


def _rate_from_label(label):
    match = _NUMBER_RE.search(label or "")
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        return None


def backfill_rates(apps, schema_editor):
    InstituteTierConfig = apps.get_model("contracts", "InstituteTierConfig")
    for config in InstituteTierConfig.objects.all():
        is_tutorspace = config.institute_name.strip().lower() == "tutorspace"
        changed = False
        new_tiers = []
        for tier in config.tiers or []:
            if not isinstance(tier, dict):
                new_tiers.append(tier)
                continue
            if "rate" in tier:
                new_tiers.append(tier)
                continue
            rate = _rate_from_label(tier.get("label", ""))
            if rate is None and is_tutorspace:
                rate = _BUILTIN_TUTORSPACE_RATES_BY_HOURS_FROM.get(
                    tier.get("hours_from"), Decimal("0")
                )
            if rate is None:
                rate = Decimal("0")
            new_tiers.append({**tier, "rate": float(rate)})
            changed = True
        if changed:
            config.tiers = new_tiers
            config.save(update_fields=["tiers"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0014_institute_tier_config_no_show"),
    ]

    operations = [
        migrations.RunPython(backfill_rates, noop_reverse),
    ]
