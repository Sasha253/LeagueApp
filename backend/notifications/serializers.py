from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import ACTIONS, NOTIFICATION_ACTIONS, Answer, DeviceToken, Notification


class ActionSerializer(serializers.Serializer):
    key = serializers.CharField(read_only=True, help_text="An answer, or `find_match`.")
    label = serializers.CharField(read_only=True)
    action = serializers.ChoiceField(
        choices=NOTIFICATION_ACTIONS,
        read_only=True,
        help_text="`answer` posts to the answer endpoint; `open` only opens a screen.",
    )


class NotificationSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()
    needs_reply = serializers.SerializerMethodField(
        help_text="It can be answered now and has no answer yet."
    )
    can_answer = serializers.SerializerMethodField(
        help_text="It can be answered (or the answer changed) now."
    )
    fixture_id = serializers.IntegerField(read_only=True, allow_null=True)
    booking_id = serializers.IntegerField(read_only=True, allow_null=True)
    club_id = serializers.IntegerField(read_only=True)
    answer = serializers.ChoiceField(choices=Answer.choices, allow_blank=True, read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "kind",
            "title",
            "body",
            "club_id",
            "fixture_id",
            "booking_id",
            "created_at",
            "read_at",
            "answer",
            "answered_at",
            "answer_by",
            "actions",
            "can_answer",
            "needs_reply",
        ]
        read_only_fields = fields

    @extend_schema_field(ActionSerializer(many=True))
    def get_actions(self, obj) -> list[dict]:
        return [{"key": k, "label": label, "action": a} for k, label, a in ACTIONS[obj.kind]]

    def get_can_answer(self, obj) -> bool:
        return obj.is_answerable(timezone.now())

    def get_needs_reply(self, obj) -> bool:
        return not obj.answer and obj.is_answerable(timezone.now())


class AnswerSerializer(serializers.Serializer):
    answer = serializers.ChoiceField(choices=Answer.choices)


class InboxSummarySerializer(serializers.Serializer):
    unread = serializers.IntegerField(read_only=True)
    needs_reply = serializers.IntegerField(read_only=True)


class DeviceTokenSerializer(serializers.ModelSerializer):
    token = serializers.CharField(max_length=512, write_only=True)

    class Meta:
        model = DeviceToken
        fields = ["id", "token", "platform", "created_at", "last_seen_at"]
        read_only_fields = ["id", "created_at", "last_seen_at"]
        # The token is unique, but registering it again (or from another account) is
        # allowed: the view moves it. So no unique validator here.
        extra_kwargs = {"token": {"validators": []}}
