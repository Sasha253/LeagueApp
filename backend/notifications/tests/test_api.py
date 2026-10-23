"""The inbox and device endpoints: everyone sees and changes only their own."""

import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from fixtures import lifecycle
from fixtures.models import Fixture
from notifications import services
from notifications.models import DeviceToken, Kind, Notification

INBOX = reverse("api-v1:inbox")
SUMMARY = reverse("api-v1:inbox-summary")
DEVICES = reverse("api-v1:devices")


def signed_in(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def url(name, notification):
    return reverse(f"api-v1:{name}", kwargs={"notification_id": notification.pk})


@pytest.fixture
def sipho_inbox(match):
    """Sipho has an Update, a Confirmation, and a closed Player Request.

    The match is taking replies (its Confirmations went out), so the Confirmation can be
    answered (fixtures/confirmations.py).
    """
    fixture, people = match
    lifecycle.transition(fixture, Fixture.Status.CONFIRMING, cause="checkpoint")
    sipho = people["sipho"]
    note = {"club": fixture.club, "fixture": fixture}
    update = services.notify(Kind.UPDATE, [sipho], title="Pitch changed", **note)[0]
    confirmation = services.notify(Kind.CONFIRMATION, [sipho], title="Lions vs Boys", **note)[0]
    request = services.notify(Kind.PLAYER_REQUEST, [sipho], title="Join?", **note)[0]
    services.close(Notification.objects.filter(pk=request.pk))
    return sipho, {"update": update, "confirmation": confirmation, "request": request}


@pytest.mark.django_db
def test_inbox_lists_my_notifications_with_unanswered_on_top(sipho_inbox, match):
    sipho, sent = sipho_inbox
    services.notify(Kind.UPDATE, [match[1]["thandi"]], club=match[0].club, title="Not Sipho's")

    rows = signed_in(sipho).get(INBOX).json()

    assert [r["id"] for r in rows] == [
        sent["confirmation"].pk,
        sent["request"].pk,
        sent["update"].pk,
    ]
    top = rows[0]
    assert top["needs_reply"] is True and top["can_answer"] is True
    assert [a["key"] for a in top["actions"]] == ["confirm", "decline"]
    assert rows[1]["needs_reply"] is False  # Closed.


@pytest.mark.django_db
def test_inbox_filters(sipho_inbox):
    sipho, sent = sipho_inbox
    client = signed_in(sipho)
    needs = client.get(INBOX, {"filter": "needs_reply"}).json()
    assert [r["id"] for r in needs] == [sent["confirmation"].pk]
    updates = client.get(INBOX, {"filter": "updates"}).json()
    assert [r["id"] for r in updates] == [sent["update"].pk]
    assert client.get(INBOX, {"filter": "loud"}).status_code == 400


@pytest.mark.django_db
def test_general_carries_the_find_a_match_link(match):
    fixture, people = match
    services.notify(Kind.GENERAL, [people["sipho"]], club=fixture.club, title="Cancelled")
    [row] = signed_in(people["sipho"]).get(INBOX).json()
    assert row["actions"] == [{"key": "find_match", "label": "Find a match", "action": "open"}]
    assert row["needs_reply"] is False


@pytest.mark.django_db
def test_summary_counts_unread_and_needs_reply(sipho_inbox):
    sipho, sent = sipho_inbox
    client = signed_in(sipho)
    assert client.get(SUMMARY).json() == {"unread": 3, "needs_reply": 1}
    client.post(url("notification-read", sent["update"]))
    assert client.get(SUMMARY).json() == {"unread": 2, "needs_reply": 1}


@pytest.mark.django_db
def test_answer_and_change_it(sipho_inbox):
    sipho, sent = sipho_inbox
    client = signed_in(sipho)
    answer_url = url("notification-answer", sent["confirmation"])

    first = client.post(answer_url, {"answer": "confirm"}, format="json")
    assert first.status_code == 200
    assert first.json()["answer"] == "confirm"
    assert first.json()["read_at"] is not None
    changed = client.post(answer_url, {"answer": "decline"}, format="json")
    assert changed.json()["answer"] == "decline"
    assert client.get(SUMMARY).json()["needs_reply"] == 0


@pytest.mark.django_db
def test_answers_that_dont_fit_are_refused(sipho_inbox):
    sipho, sent = sipho_inbox
    client = signed_in(sipho)
    assert (
        client.post(url("notification-answer", sent["update"]), {"answer": "confirm"}).status_code
        == 409
    )
    assert (
        client.post(url("notification-answer", sent["request"]), {"answer": "accept"}).status_code
        == 409
    )
    assert (
        client.post(
            url("notification-answer", sent["confirmation"]), {"answer": "maybe"}
        ).status_code
        == 400
    )


@pytest.mark.django_db
def test_no_answer_after_answer_by(match):
    fixture, people = match
    [late] = services.notify(
        Kind.CONFIRMATION,
        [people["sipho"]],
        club=fixture.club,
        title="Late",
        answer_by=timezone.now() - dt.timedelta(seconds=1),
    )
    answer = signed_in(people["sipho"]).post(
        url("notification-answer", late), {"answer": "confirm"}
    )
    assert answer.status_code == 409


@pytest.mark.django_db
def test_someone_elses_notification_is_404(sipho_inbox, match):
    _, sent = sipho_inbox
    thandi = signed_in(match[1]["thandi"])
    for name in ("notification", "notification-read"):
        method = thandi.get if name == "notification" else thandi.post
        assert method(url(name, sent["confirmation"])).status_code == 404
    answer = thandi.post(url("notification-answer", sent["confirmation"]), {"answer": "confirm"})
    assert answer.status_code == 404
    sent["confirmation"].refresh_from_db()
    assert sent["confirmation"].answer == "" and sent["confirmation"].read_at is None


@pytest.mark.django_db
def test_signed_out_users_get_nothing(sipho_inbox):
    assert APIClient().get(INBOX).status_code == 401
    assert APIClient().post(DEVICES, {"token": "t", "platform": "ios"}).status_code == 401


# Devices


@pytest.mark.django_db
def test_register_a_device_and_again(make_user):
    user = make_user()
    client = signed_in(user)
    first = client.post(DEVICES, {"token": "fcm-token", "platform": "ios"}, format="json")
    assert first.status_code == 201
    assert "token" not in first.json()
    again = client.post(DEVICES, {"token": "fcm-token", "platform": "ios"}, format="json")
    assert again.status_code == 200
    assert DeviceToken.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_a_token_moves_to_the_account_now_signed_in(make_user):
    old = make_user("old@example.com")
    new = make_user("new@example.com")
    signed_in(old).post(DEVICES, {"token": "shared-phone", "platform": "android"})
    signed_in(new).post(DEVICES, {"token": "shared-phone", "platform": "android"})
    assert DeviceToken.objects.get(token="shared-phone").user == new


@pytest.mark.django_db
def test_bad_device_input_is_refused(make_user):
    client = signed_in(make_user())
    assert client.post(DEVICES, {"token": "", "platform": "ios"}).status_code == 400
    assert client.post(DEVICES, {"token": "t", "platform": "fax"}).status_code == 400


@pytest.mark.django_db
def test_remove_only_my_own_device(make_user):
    mine = make_user("mine@example.com")
    other = make_user("other@example.com")
    device_id = signed_in(mine).post(DEVICES, {"token": "t1", "platform": "ios"}).json()["id"]
    device_url = reverse("api-v1:device", kwargs={"device_id": device_id})

    assert signed_in(other).delete(device_url).status_code == 404
    assert signed_in(mine).delete(device_url).status_code == 204
    assert not DeviceToken.objects.exists()


def test_django_admin_cannot_write_notifications_or_devices():
    from django.contrib import admin

    for model in (Notification, DeviceToken):
        model_admin = admin.site._registry[model]
        assert not model_admin.has_add_permission(None)
        assert not model_admin.has_change_permission(None)
