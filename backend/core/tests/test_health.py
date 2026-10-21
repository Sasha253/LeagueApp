from unittest import mock

import pytest
from django.db import DatabaseError
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_is_ok_when_the_database_answers():
    response = APIClient().get(reverse("api-v1:health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_health_is_503_when_the_database_fails():
    with mock.patch("core.views.connection.cursor", side_effect=DatabaseError):
        response = APIClient().get(reverse("api-v1:health"))

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "error"}


def test_schema_documents_the_health_endpoint():
    response = APIClient().get(reverse("api-v1:schema"), {"format": "json"})

    assert response.status_code == 200
    assert "/api/v1/health/" in response.json()["paths"]
