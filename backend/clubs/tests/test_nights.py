import pytest
from django.urls import reverse

from clubs.models import Night

NIGHTS = reverse("api-v1:nights")


@pytest.mark.django_db
def test_lists_every_clubs_nights_for_choosing_opt_ins(api, make_user, tuesday, club_b):
    friday_b = Night.objects.create(club=club_b, weekday=Night.Weekday.FRIDAY)
    api.force_authenticate(make_user())

    response = api.get(NIGHTS)

    assert response.status_code == 200
    assert response.json() == [
        {"id": tuesday.id, "club": {"id": tuesday.club_id, "name": "Club A"}, "weekday": 1},
        {"id": friday_b.id, "club": {"id": club_b.id, "name": "Club B"}, "weekday": 4},
    ]


@pytest.mark.django_db
def test_needs_sign_in(api):
    assert api.get(NIGHTS).status_code == 401
