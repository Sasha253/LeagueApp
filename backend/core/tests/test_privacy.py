from django.urls import reverse
from rest_framework.test import APIClient

from core.legal import DEFAULT_OPERATOR, UPDATED_ON


def test_privacy_policy_is_open_to_everyone(settings):
    settings.PRIVACY_OPERATOR_NAME = "Floodlit Leagues (Pty) Ltd"
    settings.PRIVACY_CONTACT_EMAIL = "privacy@example.com"

    response = APIClient().get(reverse("api-v1:privacy-policy"))

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Privacy policy"
    assert body["updated_on"] == UPDATED_ON.isoformat()
    assert body["operator"] == "Floodlit Leagues (Pty) Ltd"
    assert body["contact_email"] == "privacy@example.com"
    headings = [section["heading"] for section in body["sections"]]
    assert headings[:3] == ["Who we are", "What we keep", "What we never keep"]
    assert all(section["paragraphs"] for section in body["sections"])
    text = " ".join(p for section in body["sections"] for p in section["paragraphs"])
    assert "privacy@example.com" in text
    assert "Floodlit Leagues (Pty) Ltd runs League App" in text


def test_privacy_policy_says_card_data_and_camera_images_are_never_kept(settings):
    body = APIClient().get(reverse("api-v1:privacy-policy")).json()

    never = next(s for s in body["sections"] if s["heading"] == "What we never keep")
    text = " ".join(never["paragraphs"])
    assert "Card details" in text and "PayFast" in text
    assert "Camera images" in text


def test_privacy_policy_without_operator_or_email_still_reads(settings):
    settings.PRIVACY_OPERATOR_NAME = ""
    settings.PRIVACY_CONTACT_EMAIL = "  "

    body = APIClient().get(reverse("api-v1:privacy-policy")).json()

    assert body["operator"] == DEFAULT_OPERATOR
    assert body["contact_email"] == ""
    text = " ".join(p for section in body["sections"] for p in section["paragraphs"])
    assert "Ask your Club's Admin" in text


def test_privacy_policy_ignores_a_bad_token():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")

    assert client.get(reverse("api-v1:privacy-policy")).status_code == 200


def test_privacy_page_is_a_public_web_page(settings):
    settings.PRIVACY_OPERATOR_NAME = "Floodlit <Leagues>"
    settings.PRIVACY_CONTACT_EMAIL = "privacy@example.com"

    response = APIClient().get(reverse("privacy"))

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/html")
    html = response.content.decode()
    assert "<h1>Privacy policy</h1>" in html
    assert "Floodlit &lt;Leagues&gt;" in html  # escaped, never raw
    assert "Last updated Sat 24 Oct 2026" in html
    assert 'href="mailto:privacy@example.com"' in html
    assert "<h2>What we never keep</h2>" in html


def test_schema_documents_the_privacy_policy():
    response = APIClient().get(reverse("api-v1:schema"), {"format": "json"})

    assert "/api/v1/legal/privacy/" in response.json()["paths"]
