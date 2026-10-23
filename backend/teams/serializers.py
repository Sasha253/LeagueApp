from rest_framework import serializers

from accounts.models import PlayerProfile
from clubs.models import Division, Night, Season
from clubs.serializers import ClubSummarySerializer

from .models import JoinRequest, Team, TeamMembership


class NamedSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class TeamSerializer(serializers.ModelSerializer):
    """A Team as Players see it when they search."""

    club = ClubSummarySerializer(read_only=True)
    season = NamedSerializer(read_only=True)
    division = NamedSerializer(read_only=True)
    weekday = serializers.ChoiceField(
        source="division.night.weekday", choices=Night.Weekday.choices, read_only=True
    )
    captain_name = serializers.CharField(
        source="captain.name", read_only=True, allow_null=True, default=None
    )
    players = serializers.SerializerMethodField(help_text="Players in the Team now.")

    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "club",
            "season",
            "division",
            "weekday",
            "captain_id",
            "captain_name",
            "players",
            "status",
        ]

    def get_players(self, team: Team) -> int:
        count = getattr(team, "player_count", None)
        return team.current_memberships().count() if count is None else count


class TeamRequestSerializer(serializers.Serializer):
    """A Captain's request for a new Team."""

    season = serializers.PrimaryKeyRelatedField(queryset=Season.objects.select_related("club"))
    division = serializers.PrimaryKeyRelatedField(
        queryset=Division.objects.select_related("night__club__settings")
    )
    name = serializers.CharField(max_length=60)


class MemberSerializer(serializers.ModelSerializer):
    """A Player in a Team."""

    player_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(source="player.name", read_only=True)
    position = serializers.ChoiceField(
        source="player.player_profile.position",
        choices=PlayerProfile.Position.choices,
        read_only=True,
        allow_null=True,
        default=None,
    )
    is_captain = serializers.SerializerMethodField()

    class Meta:
        model = TeamMembership
        fields = ["player_id", "name", "position", "is_captain", "joined_at"]

    def get_is_captain(self, membership: TeamMembership) -> bool:
        return membership.team.captain_id == membership.player_id


class MyTeamSerializer(serializers.ModelSerializer):
    """One of the signed-in Player's memberships, now or before."""

    team = TeamSerializer(read_only=True)
    is_captain = serializers.SerializerMethodField()

    class Meta:
        model = TeamMembership
        fields = ["id", "team", "joined_at", "left_at", "is_captain"]

    def get_is_captain(self, membership: TeamMembership) -> bool:
        return membership.left_at is None and membership.team.captain_id == membership.player_id


class JoinRequestSerializer(serializers.ModelSerializer):
    team = TeamSerializer(read_only=True)
    player_id = serializers.IntegerField(read_only=True)
    player_name = serializers.CharField(source="player.name", read_only=True)
    position = serializers.ChoiceField(
        source="player.player_profile.position",
        choices=PlayerProfile.Position.choices,
        read_only=True,
        allow_null=True,
        default=None,
    )

    class Meta:
        model = JoinRequest
        fields = [
            "id",
            "team",
            "player_id",
            "player_name",
            "position",
            "status",
            "created_at",
            "decided_at",
        ]


class AdminTeamSerializer(TeamSerializer):
    """A Team as its Club's Admin sees it, with who asked, who decided and its Players."""

    requested_by_name = serializers.CharField(
        source="requested_by.name", read_only=True, allow_null=True, default=None
    )
    decided_by_name = serializers.CharField(
        source="decided_by.name", read_only=True, allow_null=True, default=None
    )
    members = MemberSerializer(source="current_members", many=True, read_only=True)

    class Meta(TeamSerializer.Meta):
        fields = [
            *TeamSerializer.Meta.fields,
            "requested_by_name",
            "requested_at",
            "decided_by_name",
            "decided_at",
            "decline_reason",
            "members",
        ]


class DeclineTeamSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True)


class AssignCaptainSerializer(serializers.Serializer):
    player = serializers.IntegerField(help_text="The user id of a Player in the Team.")


class SeasonOptionSerializer(serializers.ModelSerializer):
    club = ClubSummarySerializer(read_only=True)

    class Meta:
        model = Season
        fields = ["id", "club", "name", "starts_on", "ends_on"]


class DivisionOptionSerializer(serializers.ModelSerializer):
    """A Division a Captain can choose for a new Team in one Season."""

    weekday = serializers.ChoiceField(
        source="night.weekday", choices=Night.Weekday.choices, read_only=True
    )
    effective_league_fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, allow_null=True
    )
    teams = serializers.IntegerField(
        source="team_count", read_only=True, help_text="Active Teams this Season."
    )
    is_open = serializers.SerializerMethodField(
        help_text="Takes Team requests: its league fee is set and it isn't full."
    )

    class Meta:
        model = Division
        fields = [
            "id",
            "name",
            "weekday",
            "min_players",
            "effective_league_fee",
            "max_teams",
            "teams",
            "is_open",
        ]

    def get_is_open(self, division: Division) -> bool:
        full = division.max_teams is not None and division.team_count >= division.max_teams
        return division.effective_league_fee is not None and not full
