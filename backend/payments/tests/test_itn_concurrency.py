"""PayFast sending the same ITN twice at the same moment: one card entry only.

Its own module: the threads need committed data (a transactional test).
"""

import threading
from decimal import Decimal

import pytest
from django.db import connection

from ledger.models import LedgerEntry
from payments import services
from payments.models import GatewayNotification

from .conftest import PAYFAST_IP, itn_fields


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_the_same_itn_twice_at_once_records_one_payment(owing, people):
    payment = services.start_payment(
        team=owing, player=people["sipho"], amount=Decimal("100"), credit="none"
    )
    fields = itn_fields(payment)
    barrier = threading.Barrier(2)
    outcomes = []

    def run():
        try:
            barrier.wait()
            outcomes.append(services.handle_notification("payfast", fields, PAYFAST_IP).outcome)
        finally:
            connection.close()

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["accepted", "repeat"]
    assert LedgerEntry.objects.filter(kind="payment", method="card").count() == 1
    assert GatewayNotification.objects.count() == 2
