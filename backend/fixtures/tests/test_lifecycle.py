"""The Fixture status state machine: only allowed moves, every move logged."""

import pytest

from core.exceptions import Conflict
from fixtures import lifecycle
from fixtures.models import Fixture, FixtureTransition

S = Fixture.Status
ALL_PAIRS = [(a, b) for a in S.values for b in S.values]


@pytest.fixture
def fixture(make_fixture, lions_and_boys):
    return make_fixture(*lions_and_boys, friendly_eligible=True)


def test_the_table_names_every_status_and_only_statuses():
    assert set(lifecycle.TRANSITIONS) == set(S.values)
    for targets in lifecycle.TRANSITIONS.values():
        assert targets <= set(S.values)


def test_cancelled_and_played_are_final():
    assert lifecycle.TRANSITIONS[S.CANCELLED] == frozenset()
    assert lifecycle.TRANSITIONS[S.PLAYED] == frozenset()


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (S.SCHEDULED, S.CONFIRMING),
        (S.CONFIRMING, S.READY),
        (S.READY, S.PLAYED),
        (S.CONFIRMING, S.ONE_TEAM_OUT),
        (S.ONE_TEAM_OUT, S.REPLACEMENT_OFFERED),
        (S.REPLACEMENT_OFFERED, S.CONFIRMING),
        (S.ONE_TEAM_OUT, S.FRIENDLY),
        (S.FRIENDLY, S.PLAYED),
        (S.ONE_TEAM_OUT, S.CANCELLED),
        (S.READY, S.SCHEDULED),
    ],
)
def test_the_lifecycle_moves_are_allowed(from_status, to_status):
    assert lifecycle.can_move(from_status, to_status)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (S.SCHEDULED, S.READY),
        (S.SCHEDULED, S.PLAYED),
        (S.SCHEDULED, S.REPLACEMENT_OFFERED),
        (S.CANCELLED, S.SCHEDULED),
        (S.PLAYED, S.CANCELLED),
        (S.FRIENDLY, S.SCHEDULED),
        (S.ONE_TEAM_OUT, S.READY),
        (S.CONFIRMING, S.CONFIRMING),
    ],
)
def test_other_moves_are_not(from_status, to_status):
    assert not lifecycle.can_move(from_status, to_status)


@pytest.mark.django_db
@pytest.mark.parametrize(("from_status", "to_status"), ALL_PAIRS)
def test_transition_does_exactly_what_the_table_allows(
    make_fixture, lions_and_boys, from_status, to_status
):
    fixture = make_fixture(*lions_and_boys, status=from_status, friendly_eligible=True)
    allowed = lifecycle.can_move(from_status, to_status)

    if allowed:
        moved = lifecycle.transition(fixture, to_status, cause="system")
        assert moved.status == to_status
    else:
        with pytest.raises(Conflict):
            lifecycle.transition(fixture, to_status, cause="system")
        fixture.refresh_from_db()
        assert fixture.status == from_status
    assert fixture.transitions.count() == (2 if allowed else 1)


@pytest.mark.django_db
def test_every_move_is_logged_with_who_or_what_caused_it(fixture, make_user):
    admin = make_user("admin@example.com", name="Ada Admin")

    lifecycle.transition(fixture, S.CONFIRMING, cause=FixtureTransition.Cause.CHECKPOINT)
    lifecycle.transition(
        fixture, S.CANCELLED, cause=FixtureTransition.Cause.ADMIN, actor=admin, note="Rain"
    )

    log = list(
        fixture.transitions.values_list("from_status", "to_status", "cause", "actor", "note")
    )
    assert log == [
        ("", S.SCHEDULED, "admin", None, ""),
        (S.SCHEDULED, S.CONFIRMING, "checkpoint", None, ""),
        (S.CONFIRMING, S.CANCELLED, "admin", admin.pk, "Rain"),
    ]


@pytest.mark.django_db
def test_only_a_friendly_eligible_fixture_becomes_a_friendly(make_fixture, lions_and_boys):
    fixture = make_fixture(*lions_and_boys, status=S.ONE_TEAM_OUT)

    with pytest.raises(Conflict, match="isn't friendly-eligible"):
        lifecycle.transition(fixture, S.FRIENDLY, cause="system")

    fixture.refresh_from_db()
    assert fixture.status == S.ONE_TEAM_OUT


@pytest.mark.django_db
def test_the_log_is_never_changed_or_deleted(fixture):
    entry = fixture.transitions.get()
    entry.note = "edited"
    with pytest.raises(ValueError):
        entry.save()
    with pytest.raises(ValueError):
        entry.delete()
    assert fixture.transitions.get().note == ""


@pytest.mark.django_db
@pytest.mark.parametrize("status", [S.FRIENDLY, S.CANCELLED, S.PLAYED])
def test_friendly_eligible_is_fixed_once_the_match_is_decided(
    make_fixture, lions_and_boys, make_user, status
):
    fixture = make_fixture(*lions_and_boys, status=status)
    with pytest.raises(Conflict):
        lifecycle.set_friendly_eligible(fixture, True, make_user("a@example.com"))


@pytest.mark.django_db
def test_marking_friendly_eligible_records_who_and_when(make_fixture, lions_and_boys, make_user):
    admin = make_user("a@example.com")
    fixture = make_fixture(*lions_and_boys)

    fixture = lifecycle.set_friendly_eligible(fixture, True, admin)

    fixture.refresh_from_db()
    assert fixture.friendly_eligible is True
    assert fixture.friendly_eligible_changed_by == admin
    assert fixture.friendly_eligible_changed_at is not None
