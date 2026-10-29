"""Token auth for the app (no session cookies: the installed app runs on its own origin).

Login, refresh and logout are simplejwt's views. Refresh tokens rotate, and logout
blacklists the refresh token so it can't be used again.

A superuser can also sign in as a test user, who has no password (accounts/testers.py).
"""

import logging

from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from .models import User
from .permissions import IsSuperuser
from .serializers import (
    MeSerializer,
    RegisteredSerializer,
    RegisterSerializer,
    TesterSerializer,
    tokens_for,
)

logger = logging.getLogger(__name__)


class AuthRateThrottle(AnonRateThrottle):
    scope = "auth"


class RegisterView(generics.CreateAPIView):
    """Creates an account and signs it in."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(responses={201: RegisteredSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        body = {**tokens_for(user), "user": MeSerializer(user).data}
        return Response(body, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """Signs in with email and password. Answers with an access and a refresh token."""

    throttle_classes = [AuthRateThrottle]


class RefreshView(TokenRefreshView):
    """Swaps a refresh token for a new access token and a new refresh token."""


class LogoutView(TokenBlacklistView):
    """Signs out: the refresh token can't be used again."""


class MeView(generics.RetrieveUpdateAPIView):
    """The signed-in user, their Player profile and the roles they hold at each Club."""

    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "options"]

    def get_object(self):
        return self.request.user


def testers():
    # Never a superuser: signing in as one would hand out every club.
    return User.objects.filter(is_test_account=True, is_active=True, is_superuser=False)


class TesterListView(generics.ListAPIView):
    """The test users a superuser can sign in as (superuser only)."""

    serializer_class = TesterSerializer
    permission_classes = [IsSuperuser]
    pagination_class = None

    def get_queryset(self):
        return (
            testers()
            .select_related("player_profile")
            .prefetch_related("club_roles__club")
            .order_by("pk")
        )


class TesterLoginView(generics.GenericAPIView):
    """Signs a superuser in as a test user: answers with that user's tokens."""

    serializer_class = RegisteredSerializer
    permission_classes = [IsSuperuser]

    def get_queryset(self):
        return testers()

    @extend_schema(request=None, responses={200: RegisteredSerializer})
    def post(self, request, *args, **kwargs):
        user = self.get_object()
        logger.info("%s signed in as test user %s", request.user.email, user.email)
        return Response({**tokens_for(user), "user": MeSerializer(user).data})
