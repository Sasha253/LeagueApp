"""A new Club starts from the seeded defaults: data, not constants in code."""

from decimal import Decimal

import pytest

from clubs.models import Club, ClubSettings, SettingsDefaults

PRD = {
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


@pytest.mark.django_db
def test_the_defaults_are_seeded_with_the_prd_values():
    defaults = SettingsDefaults.objects.get()

    for name, value in PRD.items():
        assert getattr(defaults, name) == value, name
    assert defaults.league_fee is None
    assert defaults.friendly_fee is None
    assert defaults.booking_hourly_fee is None


@pytest.mark.django_db
def test_a_new_club_gets_settings_copied_from_the_defaults():
    club = Club.objects.create(name="New Club")

    for name, value in PRD.items():
        assert getattr(club.settings, name) == value, name


@pytest.mark.django_db
def test_changing_the_defaults_changes_new_clubs_only(club_a):
    SettingsDefaults.objects.update(division_min_players=7, league_fee=Decimal("400"))

    club = Club.objects.create(name="Later Club")

    assert club.settings.division_min_players == 7
    assert club.settings.league_fee == Decimal("400")
    club_a.settings.refresh_from_db()
    assert club_a.settings.division_min_players == 5


@pytest.mark.django_db
def test_the_fees_are_missing_until_the_admin_sets_them(club_a):
    assert club_a.settings.missing == ["league_fee", "friendly_fee", "booking_hourly_fee"]

    ClubSettings.objects.filter(club=club_a).update(league_fee=Decimal("350"))
    club_a.settings.refresh_from_db()

    assert club_a.settings.missing == ["friendly_fee", "booking_hourly_fee"]


@pytest.mark.django_db
def test_a_club_cant_be_created_without_defaults():
    SettingsDefaults.objects.all().delete()

    with pytest.raises(SettingsDefaults.DoesNotExist):
        Club.objects.create(name="No Defaults")
