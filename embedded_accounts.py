#!/usr/bin/env python3
"""Built-in chart of accounts (ships EMPTY).

The program is shipped with no accounts in this list. The client supplies their
own chart at run time, and it is merged in and remembered:

    * "Import account list" button - reads a Chart of Accounts CSV exported from
      QuickBooks Online (saved next to the program as imported_chart.csv); or
    * "Add a single account" fields - for one-off additions (saved next to the
      program as added_accounts.csv).

Both persist across runs and always merge. Until a chart is imported or accounts
are added, account numbers are written through to the output unchanged (and the
program reports them), so nothing is silently lost.

This file intentionally contains NO real client data. If a build for a specific
client should pre-load that client's chart, populate ``ACCOUNTS`` from their QBO
export and rebuild - but never commit real client data to shared source control.
"""

from __future__ import annotations

from typing import Dict

#: Account number -> account name. Ships empty by design (see module docstring).
ACCOUNTS: Dict[str, str] = {}
