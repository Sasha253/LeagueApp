"""Ledger entries are never changed or deleted: not by the ORM, the admin or the API (FR-50)."""

from decimal import Decimal

import pytest
from django.contrib import admin
from django.test import RequestFactory

from ledger import services
from ledger.models import LedgerEntry


@pytest.fixture
def entry(lions):
    return services.charge_league_fee(lions)


@pytest.mark.django_db
def test_an_entry_is_not_saved_again(entry):
    entry.amount = Decimal("1")

    with pytest.raises(ValueError):
        entry.save()


@pytest.mark.django_db
def test_an_entry_is_not_deleted(entry):
    with pytest.raises(ValueError):
        entry.delete()


@pytest.mark.django_db
def test_querysets_do_not_update_or_delete(entry):
    entries = LedgerEntry.objects.all()

    with pytest.raises(ValueError):
        entries.update(amount=Decimal("1"))
    with pytest.raises(ValueError):
        entries.delete()
    with pytest.raises(ValueError):
        LedgerEntry.objects.bulk_update([entry], ["amount"])
    assert LedgerEntry.objects.get(pk=entry.pk).amount == Decimal("350.00")


@pytest.mark.django_db
def test_the_django_admin_is_read_only(entry, make_user):
    model_admin = admin.site._registry[LedgerEntry]
    request = RequestFactory().get("/")
    request.user = make_user("root@example.com", is_superuser=True, is_staff=True)

    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request, entry)
    assert not model_admin.has_delete_permission(request, entry)
    assert model_admin.get_actions(request) == {}
