"""Charges the league fee to Teams that were already active before the ledger existed.

From now on the fee is charged when the Admin confirms a Team (teams.rules.confirm_team).
A Team whose Division has no league fee (its own or the club's) is left uncharged.
"""

from django.db import migrations


def charge_active_teams(apps, schema_editor):
    Team = apps.get_model("teams", "Team")
    LedgerEntry = apps.get_model("ledger", "LedgerEntry")
    ClubSettings = apps.get_model("clubs", "ClubSettings")
    charged = LedgerEntry.objects.filter(kind="charge", category="league", fixture=None)
    teams = Team.objects.filter(status="active").exclude(pk__in=charged.values("team_id"))
    for team in teams.select_related("division__night", "season"):
        fee = team.division.league_fee
        if fee is None:
            club_settings = ClubSettings.objects.filter(club_id=team.club_id).first()
            fee = club_settings.league_fee if club_settings else None
        if not fee:
            continue
        LedgerEntry.objects.create(
            club_id=team.club_id,
            kind="charge",
            category="league",
            amount=fee,
            subject="team",
            team=team,
            reason=f"League fee, {team.season.name}",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0001_initial"),
        ("clubs", "0004_division_max_teams"),
        ("teams", "0001_initial"),
    ]

    operations = [migrations.RunPython(charge_active_teams, migrations.RunPython.noop)]
