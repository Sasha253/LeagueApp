import pytest

from barcodes import signing
from barcodes.models import Barcode


def make(**fields) -> Barcode:
    values = {
        "club_id": 1,
        "team_id": 2,
        "mode": Barcode.Mode.MATCH,
        "season_id": 3,
        "fixture_id": 4,
        "nonce": "a" * 32,
    }
    values.update(fields)
    barcode = Barcode(**values)
    barcode.code = signing.sign(barcode)
    return barcode


def test_a_code_is_ten_crockford_characters():
    code = make().code
    assert len(code) == 10
    assert all(char in signing.ALPHABET for char in code)


def test_the_same_barcode_signs_the_same_way():
    assert make().code == make().code


@pytest.mark.parametrize(
    "change",
    [{"team_id": 9}, {"fixture_id": 5}, {"season_id": 8}, {"club_id": 7}, {"nonce": "b" * 32}],
)
def test_changing_the_subject_or_nonce_breaks_the_signature(change):
    barcode = make()
    for name, value in change.items():
        setattr(barcode, name, value)
    assert not signing.is_signed(barcode)


def test_a_season_barcode_signs_differently_from_a_match_one():
    assert make().code != make(mode=Barcode.Mode.SEASON, fixture_id=None).code


def test_the_key_signs(settings):
    settings.BARCODE_SIGNING_KEY = "one-key"
    first = make().code
    settings.BARCODE_SIGNING_KEY = "another-key"
    assert make().code != first
    barcode = make()
    settings.BARCODE_SIGNING_KEY = "one-key"
    assert not signing.is_signed(barcode)


def test_without_its_own_key_it_signs_with_one_from_the_secret_key(settings):
    settings.BARCODE_SIGNING_KEY = ""
    first = make().code
    settings.SECRET_KEY = "a-different-secret-key-for-this-test"
    assert make().code != first


@pytest.mark.parametrize(
    ("entered", "code"),
    [
        ("RK27104419", "RK27104419"),
        ("rk 2710 4419", "RK27104419"),
        ("RL-2710-4419", "R127104419"),  # L reads as 1: Crockford has no L.
        ("  ab cd ef gh oi ", "ABCDEFGH01"),
    ],
)
def test_what_the_gate_types_is_normalised(entered, code):
    assert signing.normalise(entered) == code


@pytest.mark.parametrize("entered", ["", "SHORT", "RL271044199", "RL2710441U", "RL27104!19"])
def test_what_cant_be_a_code_is_refused(entered):
    assert signing.normalise(entered) is None


def test_display_groups_it_like_the_design():
    assert signing.display("RK27104419") == "RK 2710 4419"
