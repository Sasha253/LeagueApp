import pytest
from django.urls import reverse
from rest_framework.test import APIClient


def preflight(origin):
    return APIClient().options(
        reverse("api-v1:health"),
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
    )


@pytest.mark.parametrize("origin", ["capacitor://localhost", "https://localhost"])
def test_the_installed_app_may_call_the_api(origin):
    response = preflight(origin)

    assert response["Access-Control-Allow-Origin"] == origin


def test_other_origins_may_not_call_the_api():
    response = preflight("https://evil.example")

    assert "Access-Control-Allow-Origin" not in response
