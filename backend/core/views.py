"""Project-level API views that belong to no single feature."""

import logging

from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

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
