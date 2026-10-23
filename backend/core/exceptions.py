from rest_framework import status
from rest_framework.exceptions import APIException


class Conflict(APIException):
    """The request is fine, but the record's current state doesn't allow it."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "This can't be done right now."
    default_code = "conflict"
