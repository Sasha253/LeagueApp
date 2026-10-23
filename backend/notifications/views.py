"""The inbox and device registration. Everyone sees and changes only their own.

Someone else's notification or device is a 404, so ids reveal nothing.
"""

from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import ACTIONS, DeviceToken, Notification
from .serializers import (
    AnswerSerializer,
    DeviceTokenSerializer,
    InboxSummarySerializer,
    NotificationSerializer,
)

INBOX_LIMIT = 100
ANSWERABLE_KINDS = [
    kind for kind, actions in ACTIONS.items() if any(a == "answer" for *_, a in actions)
]


def needs_reply(now) -> Q:
    return Q(kind__in=ANSWERABLE_KINDS, answer="", closed_at__isnull=True) & (
        Q(answer_by__isnull=True) | Q(answer_by__gt=now)
    )


def own(request, notification_id: int) -> Notification:
    return get_object_or_404(Notification, pk=notification_id, recipient=request.user)


class InboxView(APIView):
    """The signed-in user's notifications: unanswered ones on top, then newest first."""

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "filter",
                OpenApiTypes.STR,
                enum=["all", "needs_reply", "updates"],
                description="Needs reply: can be answered and isn't yet. Updates: no answer "
                "buttons (Reminder, General, Update).",
            )
        ],
        responses=NotificationSerializer(many=True),
    )
    def get(self, request):
        now = timezone.now()
        queryset = Notification.objects.filter(recipient=request.user)
        chosen = request.query_params.get("filter", "all")
        if chosen == "needs_reply":
            queryset = queryset.filter(needs_reply(now))
        elif chosen == "updates":
            queryset = queryset.exclude(kind__in=ANSWERABLE_KINDS)
        elif chosen != "all":
            raise ValidationError({"filter": "Use all, needs_reply or updates."})
        queryset = queryset.annotate(
            pinned=Case(
                When(needs_reply(now), then=Value(0)), default=Value(1), output_field=IntegerField()
            )
        ).order_by("pinned", "-created_at", "-pk")[:INBOX_LIMIT]
        return Response(NotificationSerializer(queryset, many=True).data)


class InboxSummaryView(APIView):
    @extend_schema(responses=InboxSummarySerializer)
    def get(self, request):
        mine = Notification.objects.filter(recipient=request.user)
        data = {
            "unread": mine.filter(read_at__isnull=True).count(),
            "needs_reply": mine.filter(needs_reply(timezone.now())).count(),
        }
        return Response(InboxSummarySerializer(data).data)


class NotificationDetailView(APIView):
    @extend_schema(responses=NotificationSerializer)
    def get(self, request, notification_id: int):
        return Response(NotificationSerializer(own(request, notification_id)).data)


class MarkReadView(APIView):
    @extend_schema(request=None, responses=NotificationSerializer)
    def post(self, request, notification_id: int):
        notification = services.mark_read(own(request, notification_id))
        return Response(NotificationSerializer(notification).data)


class AnswerView(APIView):
    """Confirm or decline, accept or decline. The answer can be changed while it is open."""

    @extend_schema(request=AnswerSerializer, responses=NotificationSerializer)
    def post(self, request, notification_id: int):
        notification = own(request, notification_id)
        given = AnswerSerializer(data=request.data)
        given.is_valid(raise_exception=True)
        notification = services.answer(notification, given.validated_data["answer"])
        return Response(NotificationSerializer(notification).data)


class DeviceListView(APIView):
    """Registers this phone for push. A token already known is moved to this account."""

    @extend_schema(request=DeviceTokenSerializer, responses=DeviceTokenSerializer)
    def post(self, request):
        given = DeviceTokenSerializer(data=request.data)
        given.is_valid(raise_exception=True)
        device, created = DeviceToken.objects.update_or_create(
            token=given.validated_data["token"],
            defaults={
                "user": request.user,
                "platform": given.validated_data["platform"],
                "last_seen_at": timezone.now(),
            },
        )
        return Response(
            DeviceTokenSerializer(device).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class DeviceDetailView(APIView):
    """Forgets this phone (on logout), so it gets no more pushes for this account."""

    @extend_schema(responses={204: None})
    def delete(self, request, device_id: int):
        get_object_or_404(DeviceToken, pk=device_id, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
