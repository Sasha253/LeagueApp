"""The income planner (FR-47) and the Outstanding list with Remind and Mark cash paid
(FR-48), for the Club's Admins only."""

import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from clubs.models import Season
from finance import planner, services
from fixtures.models import Fixture
from ledger import services as ledger
from ledger.models import LedgerEntry
from notifications.models import Kind, Notification


def url(name, club):
    return reverse(f"api-v1:club-finance-{name}", kwargs={"club_id": club.pk})


def signed_in(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def week_day(season, week, days=0):
    """A date in `week` of the Season (week 1 starts on its first day)."""
    return season.starts_on + dt.timedelta(days=7 * (week - 1) + days)


@pytest.fixture
def squad(make_user, make_team, tuesday):
    thandi = make_user("thandi@example.com", position="outfield", name="Thandi")
    sipho = make_user("sipho@example.com", position="outfield", name="Sipho")
    pieter = make_user("pieter@example.com", position="outfield", name="Pieter")
    zola = make_user("zola@example.com", position="outfield", name="Zola")
    for user in (thandi, pieter):
        user.player_profile.nights.add(tuesday)
    lions = make_team("Red Lions", thandi, sipho)
    boys = make_team("Old Boys", pieter)
    owls = make_team("Night Owls", zola)
    for team in (lions, boys, owls):
        ledger.charge_league_fee(team)
    return {
        "thandi": thandi,
        "sipho": sipho,
        "pieter": pieter,
        "zola": zola,
        "lions": lions,
        "boys": boys,
        "owls": owls,
    }


# Planner (FR-47)


@pytest.fixture
def planned(squad, season, make_fixture):
    """Lions v Boys in weeks 1, 3, 6 and 9 (the week 2 match is cancelled); Owls have no
    Fixtures. Today is in week 5. Lions paid R 200 cash today."""
    lions, boys = squad["lions"], squad["boys"]
    for week in (1, 3, 6, 9):
        make_fixture(lions, boys, date=week_day(season, week, 1))
    make_fixture(lions, boys, date=week_day(season, 2, 1), status=Fixture.Status.CANCELLED)
    ledger.record_payment(team=lions, amount=Decimal("200"), method="cash", recorded_by=None)
    return squad


@pytest.mark.django_db
def test_planner_spreads_fees_over_the_fixture_list(planned, admin_of, club_a, season):
    answer = admin_of(club_a).get(url("planner", club_a), {"season": season.pk})

    assert answer.status_code == 200
    body = answer.json()
    weeks = {w["week"]: w for w in body["weeks"]}
    assert len(weeks) == 13
    assert weeks[1]["starts_on"] == season.starts_on.isoformat()
    assert weeks[13]["ends_on"] == season.ends_on.isoformat()
    assert body["current_week"] == 5
    assert [w["week"] for w in body["weeks"] if w["is_due"]] == [1, 2, 3, 4, 5]
    # R 350 a Team over 4 Fixtures: R 87.50 each, both Teams.
    for week in (1, 3, 6, 9):
        assert weeks[week]["expected"] == "175.00"
        assert weeks[week]["matches"] == 1
    assert weeks[2]["expected"] == "0.00"
    assert weeks[2]["matches"] == 0  # cancelled
    # Lions' R 200 covers their weeks 1 and 3 and R 25 of week 6; Boys paid nothing.
    assert weeks[1]["covered"] == "87.50"
    assert weeks[1]["short"] == "87.50"
    assert weeks[6]["covered"] == "25.00"
    assert weeks[6]["short"] == "0.00"  # not due yet
    assert weeks[5]["received"] == "200.00"
    assert body["unscheduled"] == "350.00"  # Owls: no Fixtures yet
    assert body["season_expected"] == "1050.00"
    assert body["due_to_date"] == "350.00"
    assert body["covered_to_date"] == "175.00"
    assert body["behind"] == "175.00"
    assert body["received"] == "200.00"


@pytest.mark.django_db
def test_planner_expected_matches_the_summary(planned, club_a, season):
    plan = planner.planner(club_a, season)
    summary = services.season_summary(club_a, season)

    assert plan.season_expected == summary.totals.expected


@pytest.mark.django_db
def test_one_team_paying_ahead_never_hides_another_short(planned, club_a, season):
    ledger.record_payment(
        team=planned["lions"], amount=Decimal("150"), method="card", recorded_by=None
    )

    plan = planner.planner(club_a, season)

    week_1 = plan.weeks[0]
    assert week_1.covered == Decimal("87.50")  # Lions only; Boys still owe theirs
    assert plan.behind == Decimal("175.00")


@pytest.mark.django_db
def test_planner_before_the_season_has_nothing_due(planned, club_a, season):
    plan = planner.planner(club_a, season, today=season.starts_on - dt.timedelta(days=1))

    assert plan.current_week is None
    assert plan.due_to_date == Decimal("0.00")
    assert all(w.short == 0 for w in plan.weeks)


def test_split_puts_the_odd_cents_last():
    assert planner._split(Decimal("100.00"), 3) == [
        Decimal("33.33"),
        Decimal("33.33"),
        Decimal("33.34"),
    ]


@pytest.mark.django_db
def test_week_of_puts_dates_outside_the_season_at_its_ends(season):
    assert planner.week_of(season, season.starts_on - dt.timedelta(days=9), 13) == 1
    assert planner.week_of(season, season.ends_on + dt.timedelta(days=9), 13) == 13
    assert planner.week_of(season, week_day(season, 4, 6), 13) == 4


@pytest.mark.django_db
def test_planner_filters_by_division(planned, admin_of, club_a, season, friday_division):
    answer = admin_of(club_a).get(
        url("planner", club_a), {"season": season.pk, "division": friday_division.pk}
    )

    assert answer.status_code == 200
    assert answer.json()["season_expected"] == "0.00"


# Outstanding list (FR-48)


@pytest.fixture
def owing(squad, make_team, make_user):
    """Lions owe R 250 (Sipho paid R 100 card); Boys owe R 350; Owls have paid; a
    withdrawn Team still owes."""
    ledger.record_payment(
        team=squad["lions"],
        amount=Decimal("100"),
        method="card",
        recorded_by=None,
        player=squad["sipho"],
    )
    ledger.record_payment(
        team=squad["owls"], amount=Decimal("350"), method="cash", recorded_by=None
    )
    gone = make_team("Gone FC", make_user("gone@example.com", position="outfield", name="Gone"))
    ledger.charge_league_fee(gone)
    gone.status = "withdrawn"
    gone.save()
    return squad


@pytest.mark.django_db
def test_outstanding_lists_teams_and_players_largest_first(owing, admin_of, club_a, season):
    answer = admin_of(club_a).get(url("outstanding", club_a), {"season": season.pk})

    assert answer.status_code == 200
    body = answer.json()
    assert body["total"] == "600.00"
    assert [(t["team"]["name"], t["outstanding"]) for t in body["teams"]] == [
        ("Old Boys", "350.00"),
        ("Red Lions", "250.00"),
    ]
    lions = body["teams"][1]
    assert lions["unpaid_players"] == ["Thandi", "Sipho"]
    assert lions["division"]["name"] == "Division 2"
    # Share R 175 each; Sipho paid R 100.
    assert [(p["player"]["name"], p["owes"], p["gets_notifications"]) for p in body["players"]] == [
        ("Pieter", "350.00", True),
        ("Thandi", "175.00", True),
        ("Sipho", "75.00", False),
    ]
    sipho = body["players"][2]
    assert (sipho["share"], sipho["paid"], sipho["team"]["name"]) == (
        "175.00",
        "100.00",
        "Red Lions",
    )


@pytest.mark.django_db
def test_player_owes_no_more_than_the_team(owing, admin_of, club_a, season):
    ledger.record_payment(
        team=owing["lions"], amount=Decimal("200"), method="cash", recorded_by=None
    )  # for the whole Team: R 50 left

    body = admin_of(club_a).get(url("outstanding", club_a), {"season": season.pk}).json()

    owes = {p["player"]["name"]: p["owes"] for p in body["players"]}
    assert owes["Thandi"] == "50.00"
    assert owes["Sipho"] == "50.00"


@pytest.mark.django_db
def test_outstanding_shows_the_first_short_week(owing, club_a, season, make_fixture):
    make_fixture(owing["lions"], owing["boys"], date=week_day(season, 2, 1))
    make_fixture(owing["lions"], owing["boys"], date=week_day(season, 4, 1))

    from finance import outstanding

    owed = {row.team.name: row for row in outstanding.outstanding(club_a, season).teams}
    assert owed["Old Boys"].short_since_week == 2
    # Lions: R 175 a match; their R 100 covers only part of week 2.
    assert owed["Red Lions"].short_since_week == 2
    ledger.record_payment(
        team=owing["lions"], amount=Decimal("75"), method="cash", recorded_by=None
    )
    owed = {row.team.name: row for row in outstanding.outstanding(club_a, season).teams}
    assert owed["Red Lions"].short_since_week == 4


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["planner", "outstanding"])
def test_only_this_clubs_admins(name, owing, admin_of, club_a, club_b, season):
    admin_a = admin_of(club_a)
    admin_b = admin_of(club_b)
    assert admin_b.get(url(name, club_a), {"season": season.pk}).status_code == 403
    assert (
        signed_in(owing["thandi"]).get(url(name, club_a), {"season": season.pk}).status_code == 403
    )
    other = Season.objects.create(
        club=club_b, name="B", starts_on=season.starts_on, ends_on=season.ends_on
    )
    assert admin_a.get(url(name, club_a), {"season": other.pk}).status_code == 404
    assert admin_a.get(url(name, club_a)).status_code == 400


# Remind


@pytest.mark.django_db
def test_remind_a_team_tells_only_those_opted_into_its_night(owing, admin_of, club_a):
    answer = admin_of(club_a).post(
        url("outstanding-remind", club_a), {"team_id": owing["lions"].pk}, format="json"
    )

    assert answer.status_code == 200
    assert [u["name"] for u in answer.json()["sent_to"]] == ["Thandi"]
    assert [u["name"] for u in answer.json()["not_reached"]] == ["Sipho"]
    [note] = Notification.objects.filter(kind=Kind.UPDATE)
    assert note.recipient == owing["thandi"]
    assert note.club == club_a
    assert note.title == "Payment due: Red Lions"
    assert "R 250" in note.body


@pytest.mark.django_db
def test_remind_a_player_with_their_share(owing, admin_of, club_a):
    answer = admin_of(club_a).post(
        url("outstanding-remind", club_a),
        {"team_id": owing["lions"].pk, "player_id": owing["thandi"].pk},
        format="json",
    )

    assert answer.status_code == 200
    [note] = Notification.objects.all()
    assert note.recipient == owing["thandi"]
    assert "R 175" in note.body


@pytest.mark.django_db
def test_remind_a_player_not_opted_in_sends_nothing(owing, admin_of, club_a):
    answer = admin_of(club_a).post(
        url("outstanding-remind", club_a),
        {"team_id": owing["lions"].pk, "player_id": owing["sipho"].pk},
        format="json",
    )

    assert answer.status_code == 200
    assert answer.json() == {
        "sent_to": [],
        "not_reached": [{"id": owing["sipho"].pk, "name": "Sipho"}],
    }
    assert not Notification.objects.exists()


@pytest.mark.django_db
def test_remind_refusals(owing, admin_of, club_a, club_b):
    admin_a = admin_of(club_a)
    admin_b = admin_of(club_b)
    remind = url("outstanding-remind", club_a)
    paid = admin_a.post(remind, {"team_id": owing["owls"].pk}, format="json")
    assert paid.status_code == 409
    outsider = admin_a.post(
        remind, {"team_id": owing["lions"].pk, "player_id": owing["pieter"].pk}, format="json"
    )
    assert outsider.status_code == 400
    assert admin_b.post(remind, {"team_id": owing["lions"].pk}, format="json").status_code == 403
    other_club = admin_b.post(
        url("outstanding-remind", club_b), {"team_id": owing["lions"].pk}, format="json"
    )
    assert other_club.status_code == 404
    assert not Notification.objects.exists()


# Mark cash paid


@pytest.mark.django_db
def test_mark_a_team_cash_paid(owing, admin_of, club_a):
    admin = admin_of(club_a)
    answer = admin.post(
        url("outstanding-cash", club_a),
        {"team_id": owing["boys"].pk, "amount": "350.00"},
        format="json",
    )

    assert answer.status_code == 201
    entry = LedgerEntry.objects.get(pk=answer.json()["id"])
    assert (entry.kind, entry.method, entry.amount) == ("payment", "cash", Decimal("350.00"))
    assert entry.team == owing["boys"]
    assert entry.user is None
    assert entry.recorded_by == admin.user
    assert ledger.team_balance(owing["boys"]).is_paid


@pytest.mark.django_db
def test_mark_a_player_cash_paid(owing, admin_of, club_a):
    answer = admin_of(club_a).post(
        url("outstanding-cash", club_a),
        {"team_id": owing["lions"].pk, "player_id": owing["thandi"].pk, "amount": "175"},
        format="json",
    )

    assert answer.status_code == 201
    entry = LedgerEntry.objects.get(pk=answer.json()["id"])
    assert entry.user == owing["thandi"]
    assert ledger.team_balance(owing["lions"]).outstanding == Decimal("75.00")


@pytest.mark.django_db
def test_mark_cash_paid_refuses_a_changed_amount(owing, admin_of, club_a):
    before = LedgerEntry.objects.count()
    answer = admin_of(club_a).post(
        url("outstanding-cash", club_a),
        {"team_id": owing["lions"].pk, "amount": "350"},
        format="json",
    )

    assert answer.status_code == 409
    assert "R 250" in answer.json()["detail"]
    assert LedgerEntry.objects.count() == before


@pytest.mark.django_db
def test_mark_cash_paid_refusals(owing, admin_of, club_a, club_b):
    admin_a = admin_of(club_a)
    admin_b = admin_of(club_b)
    cash = url("outstanding-cash", club_a)
    before = LedgerEntry.objects.count()
    body = {"team_id": owing["boys"].pk, "amount": "350"}
    assert admin_b.post(cash, body, format="json").status_code == 403
    assert signed_in(owing["pieter"]).post(cash, body, format="json").status_code == 403
    paid = admin_a.post(cash, {"team_id": owing["owls"].pk, "amount": "1"}, format="json")
    assert paid.status_code == 409
    assert admin_b.post(url("outstanding-cash", club_b), body, format="json").status_code == 404
    assert LedgerEntry.objects.count() == before


@pytest.mark.django_db
def test_received_counts_in_the_week_it_was_taken(planned, club_a, season, time_machine):
    moment = timezone.make_aware(dt.datetime.combine(week_day(season, 2, 3), dt.time(10)))
    time_machine.move_to(moment, tick=False)
    ledger.record_payment(
        team=planned["boys"], amount=Decimal("50"), method="card", recorded_by=None
    )

    plan = planner.planner(club_a, season, today=week_day(season, 5))

    assert plan.weeks[1].received == Decimal("50.00")
