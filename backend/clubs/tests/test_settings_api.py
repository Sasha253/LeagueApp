import pytest
from django.urls import reverse


def url(club):
    return reverse("api-v1:club-settings", kwargs={"club_id": club.pk})


@pytest.mark.django_db
def test_admin_reads_the_settings_with_what_is_missing(admin_of, club_a):
    response = admin_of(club_a).get(url(club_a))

    assert response.status_code == 200
    body = response.json()
    assert body["league_fee"] is None
    assert body["confirmation_hours_before"] == 36
    assert body["missing"] == ["league_fee", "friendly_fee", "booking_hourly_fee"]


@pytest.mark.django_db
def test_admin_sets_the_fees_as_decimals(admin_of, club_a):
    client = admin_of(club_a)

    response = client.patch(
        url(club_a),
        {"league_fee": "350", "friendly_fee": "70.50", "booking_hourly_fee": "600"},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["league_fee"], body["friendly_fee"]) == ("350.00", "70.50")
    assert body["missing"] == []
    assert body["updated_by_name"] == client.user.name


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"league_fee": "-1"}, "league_fee"),
        ({"booking_late_cancel_credit_percent": 101}, "booking_late_cancel_credit_percent"),
        ({"division_min_players": 0}, "division_min_players"),
        ({"readiness_hours_before": 36}, "readiness_hours_before"),
        ({"confirmation_resend_after_hours": 30}, "confirmation_resend_after_hours"),
        ({"booking_late_cancel_hours": 24}, "booking_late_cancel_hours"),
        ({"replacement_close_hours_before": 6}, "replacement_close_hours_before"),
        ({"readiness_hours_before": 2}, "replacement_close_hours_before"),
        ({"payment_mode": "bitcoin"}, "payment_mode"),
    ],
)
def test_refuses_values_that_dont_make_sense(admin_of, club_a, change, field):
    response = admin_of(club_a).patch(url(club_a), change, format="json")

    assert response.status_code == 400
    assert field in response.json()


@pytest.mark.django_db
def test_switches_to_cash_only(admin_of, club_a):
    response = admin_of(club_a).patch(url(club_a), {"payment_mode": "cash_only"}, format="json")

    assert response.status_code == 200
    club_a.settings.refresh_from_db()
    assert club_a.settings.payment_mode == "cash_only"
