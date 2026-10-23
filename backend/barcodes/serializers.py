from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from fixtures.models import Fixture
from ledger.models import LEDGER_METHODS
from teams.serializers import NamedSerializer

from . import signing
from .models import BARCODE_MODES, SCAN_METHODS, Barcode
from .services import State, status_of


class BarcodeSeasonSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    ends_on = serializers.DateField(read_only=True)


class BarcodeMatchSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    kick_off = serializers.DateTimeField(
        read_only=True,
        help_text="Stored in UTC; sent with its offset. Show it in Africa/Johannesburg.",
    )
    home_team = NamedSerializer(read_only=True)
    away_team = NamedSerializer(read_only=True)
    pitch = NamedSerializer(read_only=True)


class BarcodeSerializer(serializers.ModelSerializer):
    """A Payment Barcode, as its Captain shows it at the gate."""

    team = NamedSerializer(
        read_only=True, allow_null=True, help_text="Empty for a friendly's Barcode."
    )
    holder = serializers.CharField(
        source="holder_name",
        read_only=True,
        help_text='Who it lets in: the Team\'s name, or "Friendly: Red Lions vs Old Boys".',
    )
    season = BarcodeSeasonSerializer(read_only=True)
    fixture = BarcodeMatchSerializer(
        read_only=True, allow_null=True, help_text="The match a per-match Barcode is for."
    )
    display_code = serializers.SerializerMethodField(
        help_text='The code as printed under the barcode: "RK 2710 4419".'
    )
    valid_until = serializers.SerializerMethodField(
        help_text="The last day it is valid on (South African date): its match's, or the "
        "Season's last day."
    )

    class Meta:
        model = Barcode
        fields = [
            "id",
            "code",
            "display_code",
            "mode",
            "team",
            "holder",
            "season",
            "fixture",
            "valid_until",
            "issued_at",
        ]
        read_only_fields = fields

    def get_display_code(self, barcode: Barcode) -> str:
        return signing.display(barcode.code)

    def get_valid_until(self, barcode: Barcode) -> str:
        if barcode.fixture is not None:
            return timezone.localdate(barcode.fixture.kick_off).isoformat()
        return barcode.season.ends_on.isoformat()


class CurrentBarcodeSerializer(serializers.Serializer):
    """The Captain's Barcode now, or why there is none (only a valid one is shown)."""

    state = serializers.ChoiceField(choices=State.choices, read_only=True)
    reason = serializers.CharField(read_only=True, help_text="Why there is no valid Barcode.")
    barcode = BarcodeSerializer(read_only=True, allow_null=True)


class AdminBarcodeSerializer(BarcodeSerializer):
    """A Team's Barcode as an Admin of its Club sees it: whether it is valid, and why not."""

    state = serializers.SerializerMethodField()
    reason = serializers.SerializerMethodField()
    issued_by = NamedSerializer(read_only=True, allow_null=True)
    revoked_by = NamedSerializer(read_only=True, allow_null=True)
    scans = serializers.IntegerField(
        source="scan_count", read_only=True, help_text="How often it was scanned."
    )

    class Meta(BarcodeSerializer.Meta):
        fields = [
            *BarcodeSerializer.Meta.fields,
            "state",
            "reason",
            "issued_by",
            "revoked_at",
            "revoked_by",
            "revoke_reason",
            "scans",
        ]
        read_only_fields = fields

    def _status(self, barcode: Barcode):
        if not hasattr(barcode, "_status"):
            barcode._status = status_of(barcode)
        return barcode._status

    @extend_schema_field(serializers.ChoiceField(choices=State.choices))
    def get_state(self, barcode: Barcode) -> str:
        return self._status(barcode).state

    def get_reason(self, barcode: Barcode) -> str:
        return self._status(barcode).reason


class RevokeBarcodeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, help_text="Why it no longer counts.")


class ScanRequestSerializer(serializers.Serializer):
    """A code scanned with the camera or typed in at the gate."""

    code = serializers.CharField(
        max_length=40, help_text='As scanned or typed: "RK 2710 4419", spaces optional.'
    )
    method = serializers.ChoiceField(choices=SCAN_METHODS.choices)
    fixture = serializers.PrimaryKeyRelatedField(
        queryset=Fixture.objects.none(),
        required=False,
        allow_null=True,
        help_text="The match the gate is checking for. Optional: without it, the Barcode's "
        "own match, or for a Season Barcode its Team's match today.",
    )

    def __init__(self, *args, club_id: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        # Only this club's matches: another club's id reads as not found.
        self.fields["fixture"].queryset = Fixture.objects.filter(club_id=club_id).select_related(
            "home_team", "away_team", "pitch"
        )


class ScanResultSerializer(serializers.Serializer):
    """What the gate shows after a scan: Paid or Not paid, for which Team and match, and
    why not. Everything here is decided by the backend."""

    id = serializers.IntegerField(read_only=True, help_text="The logged scan.")
    paid = serializers.BooleanField(read_only=True)
    state = serializers.ChoiceField(choices=State.scan_choices, read_only=True)
    reason = serializers.CharField(read_only=True, help_text="Why not paid; empty when paid.")
    scanned_at = serializers.DateTimeField(read_only=True)
    code = serializers.CharField(read_only=True, help_text="The code as scanned or typed.")
    display_code = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text='The Barcode\'s code as printed ("RK 2710 4419"); null when none matched.',
    )
    team = NamedSerializer(
        read_only=True, allow_null=True, help_text="Empty when none matched, or a friendly's."
    )
    holder = serializers.CharField(
        read_only=True,
        allow_null=True,
        help_text='Who the Barcode lets in: the Team, or "Friendly: …"; null when none matched.',
    )
    fixture = BarcodeMatchSerializer(
        read_only=True, allow_null=True, help_text="The match the scan was checked against."
    )
    mode = serializers.ChoiceField(choices=BARCODE_MODES.choices, read_only=True, allow_null=True)
    valid_until = serializers.DateField(
        read_only=True,
        allow_null=True,
        help_text="The Barcode's last valid day (South African date).",
    )
    paid_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        allow_null=True,
        help_text="What the Team (or the friendly) has paid, in rand; only on a Paid result.",
    )
    paid_methods = serializers.ListField(
        child=serializers.ChoiceField(choices=LEDGER_METHODS.choices),
        read_only=True,
        help_text="How the Team paid (card, cash, credit); only on a Paid result.",
    )
