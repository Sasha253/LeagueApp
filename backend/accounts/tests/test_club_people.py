"""A Club's Admins invite Admins and Referees by email, and remove them."""

import pytest
from django.urls import reverse

from accounts.models import ClubInvite, ClubRole
from clubs.models import Field
from conftest import PASSWORD

ADMIN = ClubRole.Role.ADMIN
REFEREE = ClubRole.Role.REFEREE


def invites_url(club):
    return reverse("api-v1:club-invites-list", kwargs={"club_id": club.pk})


def member_url(club, pk):
    return reverse("api-v1:club-members-detail", kwargs={"club_id": club.pk, "pk": pk})


@pytest.mark.django_db
def test_inviting_an_existing_account_gives_the_role_at_once(admin_of, make_user, club_a):
    referee = make_user("Ref@Example.com")
    client = admin_of(club_a)

    response = client.post(invites_url(club_a), {"email": " REF@example.com", "role": "referee"})

    assert response.status_code == 201
    assert response.json()["accepted"] is True
    assert ClubRole.objects.filter(user=referee, club=club_a, role=REFEREE).exists()
    assert client.get(invites_url(club_a)).json() == []


@pytest.mark.django_db
def test_an_invite_waits_until_that_email_signs_up(api, admin_of, club_a):
    client = admin_of(club_a)
    response = client.post(invites_url(club_a), {"email": "new.ref@example.com", "role": "referee"})
    assert response.json()["accepted"] is False
    assert [row["email"] for row in client.get(invites_url(club_a)).json()] == [
        "new.ref@example.com"
    ]

    signed_up = api.post(
        reverse("api-v1:register"),
        {
            "email": "New.Ref@example.com",
            "name": "Thabo",
            "password": PASSWORD,
            "is_booking_user": True,
        },
        format="json",
    )

    assert signed_up.status_code == 201
    assert signed_up.json()["user"]["club_roles"] == [
        {"club_id": club_a.pk, "club_name": "Club A", "role": "referee"}
    ]
    assert ClubInvite.objects.get().accepted_at is not None


@pytest.mark.django_db
def test_cant_invite_twice_or_someone_who_already_has_the_role(admin_of, club_a):
    client = admin_of(club_a)
    client.post(invites_url(club_a), {"email": "new@example.com", "role": "referee"})

    twice = client.post(invites_url(club_a), {"email": "new@example.com", "role": "referee"})
    already = client.post(invites_url(club_a), {"email": client.user.email, "role": "admin"})
    other_role = client.post(invites_url(club_a), {"email": "new@example.com", "role": "admin"})

    assert twice.status_code == 400 and "email" in twice.json()
    assert already.status_code == 400 and "email" in already.json()
    assert other_role.status_code == 201


@pytest.mark.django_db
def test_admin_cancels_an_open_invite(admin_of, club_a):
    client = admin_of(club_a)
    invite = client.post(invites_url(club_a), {"email": "new@example.com", "role": "admin"})
    pk = invite.json()["id"]

    url = reverse("api-v1:club-invites-detail", kwargs={"club_id": club_a.pk, "pk": pk})

    assert client.delete(url).status_code == 204
    assert not ClubInvite.objects.exists()


@pytest.mark.django_db
def test_lists_the_clubs_admins_and_referees(admin_of, make_user, give_role, club_a, club_b):
    referee = make_user("ref@example.com", name="Thabo Ref")
    give_role(referee, club_a, REFEREE)
    give_role(make_user("b@example.com"), club_b, ADMIN)
    client = admin_of(club_a)

    rows = client.get(reverse("api-v1:club-members-list", kwargs={"club_id": club_a.pk})).json()

    assert [(row["email"], row["role"]) for row in rows] == [
        (client.user.email, "admin"),
        ("ref@example.com", "referee"),
    ]


@pytest.mark.django_db
def test_removing_a_referee_takes_them_off_their_fields(admin_of, make_user, give_role, club_a):
    referee = make_user("ref@example.com")
    role = give_role(referee, club_a, REFEREE)
    field = Field.objects.create(club=club_a, name="Pitch 3", referee=referee)

    assert admin_of(club_a).delete(member_url(club_a, role.pk)).status_code == 204

    field.refresh_from_db()
    assert field.referee is None
    assert not ClubRole.objects.filter(pk=role.pk).exists()


@pytest.mark.django_db
def test_the_last_admin_cant_be_removed(admin_of, make_user, give_role, club_a):
    client = admin_of(club_a)
    own = ClubRole.objects.get(user=client.user, club=club_a)

    assert client.delete(member_url(club_a, own.pk)).status_code == 409

    second = give_role(make_user("second@example.com"), club_a, ADMIN)
    assert client.delete(member_url(club_a, second.pk)).status_code == 204
