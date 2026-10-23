"""Seeds the values a new Club starts from, and gives every existing Club its settings.

The values are the PRD's (docs/PRD.md): T-36h Confirmations resent once 12 hours later,
T-6h readiness, a minimum of 5 Players per Division, and the proposed booking policy
(payment 24h before, 50% credit from then to 6h before, none after, 100% when the club
cancels, one free reschedule within 30 days). Fees start empty: each club's Admin sets
them (docs/DECISIONS.md). After this, they are data: edit them in the Django admin.
"""

from django.db import migrations

PRD_DEFAULTS = {
    "league_fee": None,
    "friendly_fee": None,
    "booking_hourly_fee": None,
    "division_min_players": 5,
    "confirmation_hours_before": 36,
    "confirmation_resend_after_hours": 12,
    "readiness_hours_before": 6,
    "booking_payment_cutoff_hours": 24,
    "booking_late_cancel_hours": 6,
    "booking_late_cancel_credit_percent": 50,
    "booking_no_show_credit_percent": 0,
    "booking_club_cancel_credit_percent": 100,
    "booking_reschedule_window_days": 30,
    "booking_reschedules_allowed": 1,
    "payment_mode": "gateway",
    "payment_provider": "payfast",
}


def seed(apps, schema_editor):
    SettingsDefaults = apps.get_model("clubs", "SettingsDefaults")
    ClubSettings = apps.get_model("clubs", "ClubSettings")
    Club = apps.get_model("clubs", "Club")
    if not SettingsDefaults.objects.exists():
        SettingsDefaults.objects.create(**PRD_DEFAULTS)
    for club in Club.objects.filter(settings__isnull=True):
        ClubSettings.objects.create(club=club, **PRD_DEFAULTS)


def unseed(apps, schema_editor):
    apps.get_model("clubs", "ClubSettings").objects.all().delete()
    apps.get_model("clubs", "SettingsDefaults").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("clubs", "0002_club_setup")]

    operations = [migrations.RunPython(seed, unseed)]
