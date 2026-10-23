"""Sending push notifications, behind one small interface.

`get_sender()` returns the sender named by the PUSH_SENDER setting:

- FirebaseSender: Firebase Cloud Messaging through firebase-admin, for iOS and Android.
  Credentials come from the environment (FIREBASE_CREDENTIALS_FILE, a service account
  JSON file, or FIREBASE_CREDENTIALS_JSON, its contents); never from the repo.
- LogSender: writes each push to the log. The local default, so `make run` needs no
  Firebase project.
- FakeSender: keeps every push in memory, for tests.

A sender never raises for a failed push: it reports a PushResult for every message.
"""

import json
import logging
from dataclasses import dataclass, field
from functools import cache

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PushMessage:
    token: str
    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PushResult:
    token: str
    ok: bool
    error: str = ""
    # The token is no longer valid (app removed, token rotated): forget it.
    token_invalid: bool = False


class PushSender:
    def send(self, messages: list[PushMessage]) -> list[PushResult]:
        raise NotImplementedError


class LogSender(PushSender):
    def send(self, messages: list[PushMessage]) -> list[PushResult]:
        for message in messages:
            logger.info("Push to %s…: %s", message.token[:12], message.title)
        return [PushResult(token=m.token, ok=True) for m in messages]


class FakeSender(PushSender):
    """Records pushes in `FakeSender.sent`. Tokens in `failing` fail; in `invalid`, are dead."""

    sent: list[PushMessage] = []
    failing: set[str] = set()
    invalid: set[str] = set()

    @classmethod
    def reset(cls) -> None:
        cls.sent = []
        cls.failing = set()
        cls.invalid = set()

    def send(self, messages: list[PushMessage]) -> list[PushResult]:
        results = []
        for message in messages:
            if message.token in self.invalid:
                results.append(PushResult(message.token, False, "Unregistered", True))
            elif message.token in self.failing:
                results.append(PushResult(message.token, False, "Unavailable"))
            else:
                type(self).sent.append(message)
                results.append(PushResult(message.token, True))
        return results


class FirebaseSender(PushSender):
    APP_NAME = "league-app-push"

    def _app(self):
        import firebase_admin
        from firebase_admin import credentials

        try:
            return firebase_admin.get_app(self.APP_NAME)
        except ValueError:
            pass
        if settings.FIREBASE_CREDENTIALS_JSON:
            cert = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
        elif settings.FIREBASE_CREDENTIALS_FILE:
            cert = credentials.Certificate(settings.FIREBASE_CREDENTIALS_FILE)
        else:
            raise RuntimeError(
                "Set FIREBASE_CREDENTIALS_FILE or FIREBASE_CREDENTIALS_JSON to send push."
            )
        return firebase_admin.initialize_app(cert, name=self.APP_NAME)

    def send(self, messages: list[PushMessage]) -> list[PushResult]:
        if not messages:
            return []
        from firebase_admin import messaging

        try:
            app = self._app()
        except Exception as error:  # Misconfigured: every push fails, the inbox still has it.
            logger.exception("Firebase is not set up")
            return [PushResult(m.token, False, f"Firebase not set up: {error}") for m in messages]

        results = []
        # FCM takes at most 500 messages per batch.
        for start in range(0, len(messages), 500):
            batch = messages[start : start + 500]
            fcm = [
                messaging.Message(
                    token=m.token,
                    notification=messaging.Notification(title=m.title, body=m.body),
                    data=m.data,
                    apns=messaging.APNSConfig(
                        payload=messaging.APNSPayload(messaging.Aps(sound="default"))
                    ),
                    android=messaging.AndroidConfig(priority="high"),
                )
                for m in batch
            ]
            try:
                response = messaging.send_each(fcm, app=app)
            except Exception as error:
                logger.exception("Firebase batch failed")
                results += [PushResult(m.token, False, str(error)[:300]) for m in batch]
                continue
            for message, sent in zip(batch, response.responses, strict=True):
                if sent.success:
                    results.append(PushResult(message.token, True))
                else:
                    error = sent.exception
                    dead = isinstance(
                        error, messaging.UnregisteredError | messaging.SenderIdMismatchError
                    )
                    results.append(PushResult(message.token, False, str(error)[:300], dead))
        return results


@cache
def _sender_class(path: str) -> type[PushSender]:
    return import_string(path)


def get_sender() -> PushSender:
    return _sender_class(settings.PUSH_SENDER)()
