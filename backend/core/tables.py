"""Reads the workbook an Admin uploads for the league import (FR-39, FR-53).

A workbook holds several sheets, each a table. Sheets are found by name and headers by
text, both without regard to case, spaces or punctuation; other sheets and unknown columns
are ignored. In each sheet the first row that isn't blank is the header, and blank rows are
skipped. Every cell comes back as stripped text.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass

from django.db import models
from openpyxl import load_workbook

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 1000  # In each sheet.
MAX_COLUMNS = 26


class ImportAction(models.TextChoices):
    """What the import does with a row, in every sheet."""

    CREATE = "create", "New"
    UPDATE = "update", "Changes"
    UNCHANGED = "unchanged", "No change"
    ERROR = "error", "Has errors"


class TableError(Exception):
    """The file as a whole can't be read. The message is for the Admin."""


@dataclass(frozen=True)
class Row:
    number: int  # As the spreadsheet numbers it: the header is row 1.
    cells: dict[str, str]  # Column key to text, "" when blank.


@dataclass(frozen=True)
class Sheet:
    names: tuple[str, ...]  # The names it may have; the first is the one the Admin sees.
    columns: dict[str, tuple[str, ...]]  # Key to the headers it accepts, the first shown.
    required: frozenset[str]

    @property
    def name(self) -> str:
        return self.names[0]


def header_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_workbook(upload, sheets: dict[str, Sheet]) -> dict[str, list[Row]]:
    """The rows of each of `sheets` that `upload` has, by key. A sheet it doesn't have is
    left out. Raises TableError if the file can't be used or has none of the sheets."""
    if upload.size > MAX_BYTES:
        raise TableError("The file is over 5 MB.")
    if not (upload.name or "").lower().endswith(".xlsx"):
        raise TableError("Upload an Excel workbook (.xlsx). The template shows its sheets.")
    try:
        workbook = load_workbook(upload, read_only=True, data_only=True)
    except Exception as error:  # openpyxl raises many kinds for a file that isn't a workbook.
        raise TableError("This file can't be read as an Excel workbook.") from error
    try:
        by_name = {}
        for worksheet in workbook.worksheets:
            by_name.setdefault(header_key(worksheet.title), worksheet)
        found = {}
        for key, sheet in sheets.items():
            worksheet = next(
                (by_name[n] for n in map(header_key, sheet.names) if n in by_name), None
            )
            if worksheet is not None:
                found[key] = _rows(_lines(worksheet), sheet)
    finally:
        workbook.close()
    if not found:
        names = ", ".join(f'"{sheet.name}"' for sheet in sheets.values())
        raise TableError(f"The workbook has none of the sheets {names}. The template shows them.")
    return found


def _rows(lines: Iterator[tuple[int, list[str]]], sheet: Sheet) -> list[Row]:
    header = None
    for _number, cells in lines:
        if any(cells):
            header = cells
            break
    if header is None:
        return []

    accepted = {header_key(h): key for key, headers in sheet.columns.items() for h in headers}
    positions: dict[str, int] = {}
    for position, text in enumerate(header):
        key = accepted.get(header_key(text))
        if key is not None and key not in positions:
            positions[key] = position
    missing = [
        sheet.columns[key][0]
        for key in sheet.columns
        if key in sheet.required and key not in positions
    ]
    if missing:
        names = ", ".join(f'"{name}"' for name in missing)
        raise TableError(
            f"The {sheet.name} sheet has no {names} column. The template shows the columns."
        )

    rows = []
    for number, cells in lines:
        if not any(cells):
            continue
        if len(rows) == MAX_ROWS:
            raise TableError(
                f"The {sheet.name} sheet has more than {MAX_ROWS} rows. Import it in parts."
            )
        values = {
            key: cells[position] if position < len(cells) else ""
            for key, position in positions.items()
        }
        rows.append(Row(number=number, cells=values))
    return rows


def _lines(worksheet) -> Iterator[tuple[int, list[str]]]:
    try:
        rows = worksheet.iter_rows(max_col=MAX_COLUMNS, values_only=True)
        for number, values in enumerate(rows, start=1):
            yield number, [cell_text(value) for value in values]
    except Exception as error:
        raise TableError("This file can't be read as an Excel workbook.") from error
