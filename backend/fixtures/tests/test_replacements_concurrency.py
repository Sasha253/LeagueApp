"""Two Captains accepting the same slot at the same moment: only one Team wins (FR-15).

Its own module: the threads need committed data (a transactional test), while the other
replacement tests run inside one transaction each.
"""

import threading

import pytest
from django.db import connection

from core.exceptions import Conflict
from fixtures import replacements
from fixtures.models import ReplacementCandidate, ReplacementOffer
from fixtures.tests import test_replacements as base

player = base.player
match = base.match
clock = base.clock
admin = base.admin
others = base.others
lions_out = base.lions_out


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_two_teams_accepting_at_once_only_one_wins(lions_out):
    fixture, people, teams = lions_out
    candidates = [
        (ReplacementCandidate.objects.get(offer__fixture=fixture, team=teams[t]), people[c])
        for t, c in (("bulls", "bongi"), ("geckos", "gugu"))
    ]
    barrier = threading.Barrier(2)
    results = []

    def run(candidate, captain):
        try:
            barrier.wait()
            replacements.accept(candidate, captain)
            results.append("won")
        except Conflict as error:
            results.append(str(error.detail))
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=pair) for pair in candidates]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["Another Team took this slot first.", "won"]
    offer = ReplacementOffer.objects.get(fixture=fixture)
    fixture.refresh_from_db()
    assert offer.status == ReplacementOffer.Status.ACCEPTED
    assert fixture.home_team == offer.accepted_team
