"""Token auth for the app (no session cookies: the installed app runs on its own origin).

Login, refresh and logout are simplejwt's views. Refresh tokens rotate, and logout
blacklists the refresh token so it can't be used again.
"""

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

from .serializers import MeSerializer, RegisteredSerializer, RegisterSerializer, tokens_for


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
