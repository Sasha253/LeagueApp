"""Reads a table an Admin uploads as .xlsx or .csv, for the imports (FR-39, FR-53).

Only the first sheet of a workbook is read. The first row that isn't blank is the header;
headers are matched without regard to case, spaces or punctuation, and unknown columns are
ignored. Blank rows are skipped. Every cell comes back as stripped text.
"""

import csv
import io
import re
from collections.abc import Iterator
from dataclasses import dataclass

from openpyxl import load_workbook

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 500
MAX_COLUMNS = 26


class TableError(Exception):
    """The file as a whole can't be read. The message is for the Admin."""


@dataclass(frozen=True)
class Row:
    number: int  # As the spreadsheet numbers it: the header is row 1.
    cells: dict[str, str]  # Column key to text, "" when blank.


def header_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_table(upload, columns: dict[str, tuple[str, ...]], required: set[str]) -> list[Row]:
    """The rows of `upload`, keyed by `columns`: key to the headers it accepts, the first
    being the name the Admin sees. Raises TableError if the file can't be used."""
    if upload.size > MAX_BYTES:
        raise TableError("The file is over 5 MB.")
    name = (upload.name or "").lower()
    if name.endswith(".xlsx"):
        lines = _xlsx_lines(upload)
    elif name.endswith(".csv"):
        lines = _csv_lines(upload)
    else:
        raise TableError("Upload an .xlsx or .csv file.")

    header = None
    for _number, cells in lines:
        if any(cells):
            header = cells
            break
    if header is None:
        raise TableError("The file is empty.")

    accepted = {header_key(h): key for key, headers in columns.items() for h in headers}
    positions: dict[str, int] = {}
    for position, text in enumerate(header):
        key = accepted.get(header_key(text))
        if key is not None and key not in positions:
            positions[key] = position
    missing = [columns[key][0] for key in columns if key in required and key not in positions]
    if missing:
        names = ", ".join(f'"{name}"' for name in missing)
        raise TableError(f"The file has no {names} column. The template shows the columns.")

    rows = []
    for number, cells in lines:
        if not any(cells):
            continue
        if len(rows) == MAX_ROWS:
            raise TableError(f"The file has more than {MAX_ROWS} rows. Split it into smaller ones.")
        values = {
            key: cells[position] if position < len(cells) else ""
            for key, position in positions.items()
        }
        rows.append(Row(number=number, cells=values))
    return rows


def _xlsx_lines(upload) -> Iterator[tuple[int, list[str]]]:
    try:
        workbook = load_workbook(upload, read_only=True, data_only=True)
        sheet = workbook.worksheets[0]
    except Exception as error:  # openpyxl raises many kinds for a file that isn't a workbook.
        raise TableError("This file can't be read as an Excel workbook.") from error
    try:
        rows = sheet.iter_rows(max_col=MAX_COLUMNS, values_only=True)
        for number, values in enumerate(rows, start=1):
            yield number, [cell_text(value) for value in values]
    except Exception as error:
        raise TableError("This file can't be read as an Excel workbook.") from error
    finally:
        workbook.close()


def _csv_lines(upload) -> Iterator[tuple[int, list[str]]]:
    data = upload.read()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")  # Excel on Windows saves CSV so.
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    try:
        for number, cells in enumerate(reader, start=1):
            yield number, [cell.strip() for cell in cells[:MAX_COLUMNS]]
    except csv.Error as error:
        raise TableError("This file can't be read as CSV.") from error
