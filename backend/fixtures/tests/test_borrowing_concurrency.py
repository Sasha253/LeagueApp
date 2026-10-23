"""Two Players accepting the last place at the same moment: only one joins (FR-37).

Its own module: the threads need committed data (a transactional test), while the other
request tests run inside one transaction each.
"""

import threading

import pytest
from django.db import connection

from core.exceptions import Conflict
from fixtures import borrowing
from fixtures.models import BorrowedPlayer, PlayerRequest
from fixtures.tests import test_borrowing as base
from notifications import services as notifications
from notifications.models import Kind, Notification

player = base.player
match = base.match
clock = base.clock
outsiders = base.outsiders


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_two_players_accepting_at_once_only_one_joins(match, outsiders, clock):
    fixture, people = match
    clock(fixture, hours=48)
    borrowing.raise_request(fixture, people["thandi"], "player", 1)
    invites = [
        Notification.objects.get(kind=Kind.PLAYER_REQUEST, recipient=outsiders[name])
        for name in ("lerato", "nomvula")
    ]
    barrier = threading.Barrier(2)
    results = []

    def run(invite):
        try:
            barrier.wait()
            notifications.answer(invite, "accept")
            results.append("joined")
        except Conflict as error:
            results.append(str(error.detail))
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(invite,)) for invite in invites]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count("joined") == 1
    assert len(results) == 2
    assert BorrowedPlayer.objects.count() == 1
    assert PlayerRequest.objects.get().status == PlayerRequest.Status.FILLED
    assert Notification.objects.filter(kind=Kind.PLAYER_REQUEST, answer="accept").count() == 1
