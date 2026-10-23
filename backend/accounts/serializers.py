from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from clubs.models import Night

from .models import ClubInvite, ClubRole, PlayerProfile, User, normalize_email

NO_ROLE = "Choose at least one: Player or Booking User."


class PlayerProfileSerializer(serializers.ModelSerializer):
    nights = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Night.objects.all(),
        required=False,
        help_text="The Nights to get notifications for.",
    )

    class Meta:
        model = PlayerProfile
        fields = ["position", "nights"]


class ClubRoleSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source="club.name", read_only=True)

    class Meta:
        model = ClubRole
        fields = ["club_id", "club_name", "role"]


class MeSerializer(serializers.ModelSerializer):
    """The signed-in user. `player` is null when the user is not a Player."""

    player = PlayerProfileSerializer(source="player_profile", allow_null=True, required=False)
    club_roles = ClubRoleSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "name", "phone", "is_booking_user", "player", "club_roles"]
        read_only_fields = ["id", "email"]

    def validate(self, attrs):
        instance = self.instance
        is_player = (
            attrs["player_profile"] is not None
            if "player_profile" in attrs
            else bool(instance and instance.is_player)
        )
        is_booking_user = attrs.get(
            "is_booking_user", instance.is_booking_user if instance else False
        )
        if not (is_player or is_booking_user):
            raise serializers.ValidationError(NO_ROLE)
        return attrs

    @transaction.atomic
    def update(self, instance: User, validated_data):
        has_player = "player_profile" in validated_data
        player = validated_data.pop("player_profile", None)
        instance = super().update(instance, validated_data)
        if has_player:
            save_player_profile(instance, player)
        return instance


def save_player_profile(user: User, data: dict | None) -> None:
    """Creates, updates or (with None) removes the user's PlayerProfile."""
    profile = getattr(user, "player_profile", None) if user.is_player else None
    if data is None:
        if profile:
            profile.delete()
            user._state.fields_cache.pop("player_profile", None)
        return
    nights = data.pop("nights", None)
    if profile is None:
        profile = PlayerProfile.objects.create(user=user, **data)
        user.player_profile = profile
    else:
        for field, value in data.items():
            setattr(profile, field, value)
        profile.save()
    if nights is not None:
        profile.nights.set(nights)


class RegisterSerializer(MeSerializer):
    """A new account: a Player, a Booking User or both."""

    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta(MeSerializer.Meta):
        fields = [*MeSerializer.Meta.fields, "password"]
        read_only_fields = ["id"]
        extra_kwargs = {"email": {"validators": []}}

    def validate_email(self, value: str) -> str:
        email = normalize_email(value)
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    def validate(self, attrs):
        attrs = super().validate(attrs)
        candidate = User(email=attrs["email"], name=attrs.get("name", ""))
        try:
            password_validation.validate_password(attrs["password"], candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": list(error.messages)}) from error
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        player = validated_data.pop("player_profile", None)
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        save_player_profile(user, player)
        ClubInvite.accept_open_invites(user)
        return user


class ClubMemberSerializer(serializers.ModelSerializer):
    """An Admin or Referee of the Club, for its People screen."""

    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ClubRole
        fields = ["id", "user_id", "name", "email", "role"]


class ClubInviteSerializer(serializers.ModelSerializer):
    """Invites an email to be an Admin or Referee of the Club in the URL.

    An account with that email gets the role at once (`accepted` is true). Otherwise the
    invite stays open until someone signs up with that email.
    """

    accepted = serializers.SerializerMethodField()

    class Meta:
        model = ClubInvite
        fields = ["id", "email", "role", "created_at", "accepted"]
        read_only_fields = ["created_at"]
        # The open-invite constraint is checked in validate(), with a clearer message.
        validators = []

    def get_accepted(self, invite: ClubInvite) -> bool:
        return invite.accepted_at is not None

    def validate_email(self, value: str) -> str:
        return normalize_email(value)

    def validate(self, attrs):
        club = self.context["club"]
        email, role = attrs["email"], attrs["role"]
        label = ClubRole.Role(role).label
        if ClubRole.objects.filter(club=club, role=role, user__email=email).exists():
            raise serializers.ValidationError({"email": f"Already a {label} at this club."})
        if club.invites.filter(email=email, role=role, accepted_at__isnull=True).exists():
            raise serializers.ValidationError({"email": f"Already invited as {label}."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        invite = super().create(validated_data)
        user = User.objects.filter(email=invite.email, is_active=True).first()
        if user is not None:
            invite.accept(user)
        return invite


class TokenPairSerializer(serializers.Serializer):
    """What register and login answer with."""

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class RegisteredSerializer(TokenPairSerializer):
    """The new account, signed in."""

    user = MeSerializer(read_only=True)


def tokens_for(user: User) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}
