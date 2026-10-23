"""Signing Barcode codes (NFR Barcode integrity).

A code is 10 characters of Crockford base32: the first 50 bits of an HMAC-SHA256, keyed by
BARCODE_SIGNING_KEY, over a random nonce and the Barcode's whole subject (club, Team, mode,
Season, match). So a code

- can't be guessed: 50 bits that look random, and only signed-in Referees and Admins of
  the Barcode's club can look one up;
- can't be made without the key, even by someone who can write to the database;
- names one subject: change the Team, match or Season on the record and the check fails.

Ten characters fit the gate's "type the code" fallback ("RK 2710 4419") and a Code 128
barcode a phone camera reads easily.
"""

import hmac
import secrets

from django.conf import settings
from django.utils.crypto import salted_hmac

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32: no I, L, O or U.
LENGTH = 10
BITS = LENGTH * 5
KEY_SALT = "leagueapp.barcodes.v1"
# What people mistype for a Crockford character.
_READS_AS = str.maketrans({"O": "0", "I": "1", "L": "1"})


def new_nonce() -> str:
    return secrets.token_hex(16)


def _message(barcode) -> str:
    return "|".join(
        [
            "v1",
            barcode.nonce,
            f"club:{barcode.club_id}",
            f"team:{barcode.team_id}",
            f"mode:{barcode.mode}",
            f"season:{barcode.season_id}",
            f"fixture:{barcode.fixture_id or '-'}",
        ]
    )


def sign(barcode) -> str:
    """The code for `barcode`, from its nonce and subject."""
    secret = settings.BARCODE_SIGNING_KEY or None  # None: derived from SECRET_KEY.
    digest = salted_hmac(KEY_SALT, _message(barcode), secret=secret, algorithm="sha256").digest()
    number = int.from_bytes(digest, "big") >> (len(digest) * 8 - BITS)
    chars = []
    for _ in range(LENGTH):
        chars.append(ALPHABET[number & 31])
        number >>= 5
    return "".join(reversed(chars))


def is_signed(barcode) -> bool:
    """Whether the stored code is the one its nonce and subject sign to."""
    return hmac.compare_digest(barcode.code, sign(barcode))


def normalise(entered: str) -> str | None:
    """A scanned or typed code as stored: capitals, no spaces or dashes, the usual
    misreadings fixed. None if it can't be a code."""
    code = "".join(entered.split()).replace("-", "").upper().translate(_READS_AS)
    if len(code) != LENGTH or any(char not in ALPHABET for char in code):
        return None
    return code


def display(code: str) -> str:
    """As printed under the barcode: "RK 2710 4419"."""
    return f"{code[:2]} {code[2:6]} {code[6:]}"
