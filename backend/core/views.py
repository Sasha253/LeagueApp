"""Project-level API views that belong to no single feature."""

import logging

from django.db import DatabaseError, connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.legal import privacy_policy

logger = logging.getLogger(__name__)

OK = "ok"
ERROR = "error"
HEALTH_STATES = [OK, ERROR]


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=HEALTH_STATES, help_text="The API's own health: the database's."
    )
    database = serializers.ChoiceField(choices=HEALTH_STATES)


class HealthView(APIView):
    """Liveness check for the app and for deployments. Open to everyone."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: HealthSerializer, 503: HealthSerializer})
    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            database = OK
        except DatabaseError:
            logger.exception("Health check could not reach the database")
            database = ERROR
        body = {"status": database, "database": database}
        return Response(body, status=200 if database == OK else 503)


class PrivacySectionSerializer(serializers.Serializer):
    heading = serializers.CharField()
    paragraphs = serializers.ListField(child=serializers.CharField(), help_text="Plain text.")


class PrivacyPolicySerializer(serializers.Serializer):
    title = serializers.CharField()
    updated_on = serializers.DateField()
    operator = serializers.CharField(help_text="Who runs the app (PRIVACY_OPERATOR_NAME).")
    contact_email = serializers.CharField(
        allow_blank=True, help_text="Where to write about personal information; may be empty."
    )
    sections = PrivacySectionSerializer(many=True)


class PrivacyPolicyView(APIView):
    """The privacy policy the app shows and the store listings link to. Open to everyone."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses={200: PrivacyPolicySerializer})
    def get(self, request: Request) -> Response:
        return Response(PrivacyPolicySerializer(privacy_policy()).data)


def privacy_page(request: HttpRequest) -> HttpResponse:
    """The same policy as a plain web page: the privacy URL in the store listings."""
    return render(request, "core/privacy.html", {"policy": privacy_policy()})
