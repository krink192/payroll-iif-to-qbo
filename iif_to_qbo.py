#!/usr/bin/env python3
"""IIF -> QuickBooks Online journal-entry CSV converter (engine).

This module is the conversion engine. It reads a QuickBooks Desktop IIF
general-ledger / payroll export and writes a CSV in the layout QuickBooks
Online (QBO) accepts for journal-entry import.

It can be used three ways:
    * imported by the graphical front end (``iif_to_qbo_gui.py``);
    * run from the command line on a file or a folder; or
    * imported by other Python code via :func:`convert_file`.

Core design notes
-----------------
* IIF is tab-delimited text whose column order is declared by header rows
  (``!TRNS`` / ``!SPL``). Fields are therefore resolved *by name*, never by a
  fixed position, so differing export layouts all parse correctly.
* In IIF the ``TRNS`` line is itself a posting line; ``SPL`` lines are the
  remaining postings. Every ``TRNS`` and ``SPL`` becomes one output row.
* Sign convention: a positive amount is a debit, a negative amount is a credit.
  A valid entry sums to zero, so debits equal credits.

No third-party packages are required; the standard library only.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

__version__ = "2.0.0"

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

#: Column header written to every QuickBooks Online journal-import CSV.
QBO_HEADER: List[str] = [
    "*JournalNo", "*JournalDate", "*AccountName", "*Debits", "*Credits",
    "Description", "Name", "Currency", "Location", "Class",
]

#: Date formats accepted in an IIF file, tried in order. Output is MM/DD/YYYY.
_DATE_INPUT_FORMATS: Tuple[str, ...] = (
    "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%d/%m/%Y",
)
_DATE_OUTPUT_FORMAT = "%m/%d/%Y"

#: Header labels that identify the account-number column in a chart-of-accounts
#: CSV (case-insensitive, exact match).
_NUM_KEYS: Tuple[str, ...] = (
    "account #", "account number", "number", "acct #", "acct",
    "gl account number", "no.", "no",
)
#: Header labels that identify the account-name column.
_NAME_KEYS: Tuple[str, ...] = ("full name", "account name", "name", "account")

#: Text encodings attempted when reading an IIF file, in order.
_ENCODINGS: Tuple[str, ...] = ("utf-8-sig", "cp1252", "latin-1")

#: Tolerance (currency units) when checking that an entry balances.
_BALANCE_TOLERANCE = 0.005


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class JournalLine:
    """A single posting line within a journal entry."""
    account: str
    amount: float
    name: str = ""
    klass: str = ""
    memo: str = ""


@dataclass
class JournalEntry:
    """One journal entry: a transaction date, a document number, and its lines."""
    date: str
    docnum: str
    lines: List[JournalLine] = field(default_factory=list)

    def total_debits(self) -> float:
        return sum(l.amount for l in self.lines if l.amount > 0)

    def total_credits(self) -> float:
        return -sum(l.amount for l in self.lines if l.amount < 0)

    def is_balanced(self) -> bool:
        return abs(self.total_debits() - self.total_credits()) <= _BALANCE_TOLERANCE


@dataclass
class ConversionResult:
    """Summary of converting a single IIF file."""
    source_name: str
    output_name: str
    entries: int
    unbalanced: List[Tuple[str, float, float]] = field(default_factory=list)
    unmapped: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Low-level parsing helpers
# --------------------------------------------------------------------------- #

def read_rows(path: Path) -> List[List[str]]:
    """Read an IIF file into a list of token rows.

    The text encoding (UTF-8, then common Windows code pages) and the delimiter
    (tab, falling back to comma) are auto-detected. A CSV reader is used so that
    quoted fields containing the delimiter do not break tokenisation.

    Args:
        path: Path to the IIF file.

    Returns:
        A list of non-empty rows, each a list of string fields.

    Raises:
        IOError: If the file cannot be decoded with any known encoding.
    """
    text: Optional[str] = None
    for encoding in _ENCODINGS:
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise IOError(f"Could not decode {path.name} with any known encoding")

    delimiter = "\t"
    for line in text.splitlines():
        if line.startswith("!"):
            delimiter = "\t" if "\t" in line else ","
            break

    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    return [row for row in reader if row]


def parse_amount(raw: Optional[str]) -> float:
    """Parse an IIF amount into a float.

    Handles currency symbols, thousands separators, and parentheses used to
    denote a negative value. Blank or unparseable input yields ``0.0``.
    """
    if raw is None:
        return 0.0
    s = raw.strip().replace("$", "").replace(",", "").replace(" ", "")
    if not s:
        return 0.0
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        value = float(s)
    except ValueError:
        return 0.0
    return -value if negative else value


def normalize_date(raw: str) -> str:
    """Convert an IIF date string to MM/DD/YYYY.

    The original string is returned unchanged if it matches no known format, so
    that no data is silently lost.
    """
    if not raw:
        return ""
    raw = raw.strip()
    for fmt in _DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime(_DATE_OUTPUT_FORMAT)
        except ValueError:
            continue
    return raw


# --------------------------------------------------------------------------- #
# Chart-of-accounts loading
# --------------------------------------------------------------------------- #

def _read_csv_rows(path: Path) -> List[List[str]]:
    """Read a comma-delimited CSV into a list of non-empty rows."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [row for row in csv.reader(handle) if any(c.strip() for c in row)]


def _find_account_header(rows: Sequence[Sequence[str]]) -> Optional[Tuple[int, int, int]]:
    """Locate the header row of a chart-of-accounts CSV.

    Scans the first several rows (report exports often carry title rows above
    the header) for a row that contains both an account-number column and an
    account-name column.

    Returns:
        ``(number_index, name_index, header_row_index)`` or ``None`` if no
        recognizable header is found.
    """
    for i, row in enumerate(rows[:15]):
        lowered = [c.strip().lower() for c in row]
        num_idx = next((j for j, h in enumerate(lowered) if h in _NUM_KEYS), None)
        name_idx = next((j for j, h in enumerate(lowered) if h in _NAME_KEYS), None)
        if num_idx is not None and name_idx is not None:
            return num_idx, name_idx, i
    return None


def looks_like_account_map(path: Path) -> bool:
    """Return True only if the file is recognizably a chart-of-accounts CSV.

    Detection is by content (a header with both a number and a name column),
    so a payroll file or a converted journal CSV in the same folder is never
    mistaken for a chart of accounts.
    """
    try:
        rows = _read_csv_rows(path)
    except OSError:
        return False
    return bool(rows) and _find_account_header(rows) is not None


def load_account_map(path: Path) -> Dict[str, str]:
    """Load an account-number -> account-name mapping from a CSV.

    Accepts either a simple two-column ``number,name`` file or a full Chart of
    Accounts report exported from QuickBooks Online. Title rows above the header
    are skipped, and the number/name columns are located by their headers
    wherever they appear.

    Returns:
        A dict mapping account number (str) to account name (str). Empty if the
        file contains no usable rows.
    """
    rows = _read_csv_rows(path)
    if not rows:
        return {}

    found = _find_account_header(rows)
    if found is not None:
        num_idx, name_idx, header_at = found
        data = rows[header_at + 1:]
    else:                                        # no header: assume columns 0, 1
        num_idx, name_idx, data = 0, 1, rows

    mapping: Dict[str, str] = {}
    for row in data:
        if len(row) <= max(num_idx, name_idx):
            continue
        key, value = row[num_idx].strip(), row[name_idx].strip()
        if key and value:
            mapping[key] = value
    return mapping


# --------------------------------------------------------------------------- #
# IIF parsing
# --------------------------------------------------------------------------- #

def parse_entries(rows: Sequence[Sequence[str]]) -> List[JournalEntry]:
    """Group token rows into journal entries.

    Column maps are rebuilt whenever a new ``!`` header line appears, so a file
    containing several header sections is handled correctly. A ``TRNS`` line
    begins an entry (and is its first posting line); each ``SPL`` adds a line;
    ``ENDTRNS`` closes the entry.

    Args:
        rows: Token rows as produced by :func:`read_rows`.

    Returns:
        The list of parsed :class:`JournalEntry` objects.
    """
    col_maps: Dict[str, Dict[str, int]] = {}
    current: Optional[JournalEntry] = None
    entries: List[JournalEntry] = []

    def field_value(record_type: str, tokens: Sequence[str], name: str) -> str:
        idx = col_maps.get(record_type, {}).get(name)
        if idx is None or idx >= len(tokens):
            return ""
        return tokens[idx].strip()

    def build_line(record_type: str, tokens: Sequence[str]) -> JournalLine:
        return JournalLine(
            account=field_value(record_type, tokens, "ACCNT"),
            amount=parse_amount(field_value(record_type, tokens, "AMOUNT")),
            name=field_value(record_type, tokens, "NAME"),
            klass=field_value(record_type, tokens, "CLASS"),
            memo=field_value(record_type, tokens, "MEMO"),
        )

    for tokens in rows:
        tag = tokens[0].strip()

        if tag.startswith("!"):                  # header: record the column layout
            record_type = tag[1:]
            col_maps[record_type] = {name.strip(): i for i, name in enumerate(tokens)}
        elif tag == "TRNS":
            current = JournalEntry(
                date=normalize_date(field_value("TRNS", tokens, "DATE")),
                docnum=field_value("TRNS", tokens, "DOCNUM"),
                lines=[build_line("TRNS", tokens)],
            )
        elif tag == "SPL" and current is not None:
            current.lines.append(build_line("SPL", tokens))
        elif tag == "ENDTRNS" and current is not None:
            entries.append(current)
            current = None

    if current is not None:                      # file ended without ENDTRNS
        entries.append(current)
    return entries


# --------------------------------------------------------------------------- #
# Output generation
# --------------------------------------------------------------------------- #

def _entry_to_rows(entry: JournalEntry, journal_no: str, currency: str) -> List[List[str]]:
    """Render one entry as QBO CSV rows.

    Date and currency appear only on the first line of the entry; the journal
    number repeats on every line.
    """
    rows: List[List[str]] = []
    for i, line in enumerate(entry.lines):
        debit = f"{line.amount:g}" if line.amount > 0 else ""
        credit = f"{abs(line.amount):g}" if line.amount < 0 else ""
        rows.append([
            journal_no,
            entry.date if i == 0 else "",
            line.account,
            debit,
            credit,
            line.memo,
            line.name,
            currency if i == 0 else "",
            "",                                  # Location: no native IIF field
            line.klass,
        ])
    return rows


def convert_file(path: Path, currency: str, account_map: Dict[str, str]) -> ConversionResult:
    """Convert a single IIF file to ``<name>.csv`` beside it.

    Account numbers are translated to names via ``account_map``; numbers absent
    from the map are written as-is and reported. Each entry is checked for
    balance. The source IIF is never modified.

    Args:
        path: The IIF file to convert.
        currency: Currency code placed on the first line of each entry.
        account_map: Mapping of account number to account name.

    Returns:
        A :class:`ConversionResult` summarising the conversion.
    """
    entries = parse_entries(read_rows(path))

    # Only strip a genuine ".iif" extension; otherwise keep the whole name so a
    # dotted name such as "GL_11_29.24_PR" is not truncated.
    if path.suffix.lower() == ".iif":
        out_path = path.with_suffix(".csv")
    else:
        out_path = path.with_name(path.name + ".csv")

    unmapped: set[str] = set()
    for entry in entries:                        # translate numbers -> names
        for line in entry.lines:
            if not line.account:
                continue
            if line.account in account_map:
                line.account = account_map[line.account]
            else:
                unmapped.add(line.account)

    unbalanced: List[Tuple[str, float, float]] = []
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(QBO_HEADER)
        for index, entry in enumerate(entries, start=1):
            journal_no = entry.docnum or str(index)
            if not entry.is_balanced():
                unbalanced.append((journal_no, entry.total_debits(), entry.total_credits()))
            writer.writerows(_entry_to_rows(entry, journal_no, currency))

    return ConversionResult(
        source_name=path.name,
        output_name=out_path.name,
        entries=len(entries),
        unbalanced=unbalanced,
        unmapped=sorted(unmapped),
    )


# --------------------------------------------------------------------------- #
# Command-line interface
# --------------------------------------------------------------------------- #

def _looks_like_iif(path: Path) -> bool:
    """True if the file's first line is an IIF header (picks up extensionless
    exports in directory mode)."""
    try:
        with path.open("r", encoding="latin-1") as handle:
            return handle.readline().startswith("!")
    except OSError:
        return False


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Command-line entry point. Converts a file or a folder of IIF files."""
    parser = argparse.ArgumentParser(
        description="Convert QuickBooks IIF exports to QuickBooks Online journal CSVs.")
    parser.add_argument("path", nargs="?", default=".",
                        help="An IIF file, or a folder of IIF files (default: current folder).")
    parser.add_argument("--currency", default="USD",
                        help="Currency code for the first line of each entry (default: USD).")
    parser.add_argument("--map", dest="map_path", default=None,
                        help="Chart-of-accounts CSV. Defaults to account_map.csv beside the files.")
    args = parser.parse_args(argv)

    target = Path(args.path)
    if target.is_dir():
        files = sorted(p for p in target.iterdir()
                       if p.is_file() and (p.suffix.lower() == ".iif" or _looks_like_iif(p)))
        search_dir = target
    elif target.is_file():
        files = [target]
        search_dir = target.parent
    else:
        print(f"Path not found: {target}")
        return 1

    if not files:
        print(f"No IIF files found in {target}")
        return 1

    account_map: Dict[str, str] = {}
    map_path = Path(args.map_path) if args.map_path else (search_dir / "account_map.csv")
    if map_path.is_file():
        account_map = load_account_map(map_path)
        print(f"Loaded {len(account_map)} account name(s) from {map_path.name}\n")
    else:
        print("No account map found - account NUMBERS will be written as-is.\n")

    print(f"Found {len(files)} file(s) to convert.\n")
    for path in files:
        try:
            result = convert_file(path, args.currency, account_map)
        except Exception as exc:                 # noqa: BLE001 - report and continue
            print(f"  ERROR  {path.name}: {exc}")
            continue
        print(f"  OK     {result.source_name}  ->  {result.output_name}   "
              f"({result.entries} entries)")
        for jno, debits, credits in result.unbalanced:
            print(f"         WARNING: journal {jno} out of balance "
                  f"(debits {debits:.2f} vs credits {credits:.2f})")
        if result.unmapped:
            print(f"         NOTE: no name mapped for account(s): {', '.join(result.unmapped)}")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
