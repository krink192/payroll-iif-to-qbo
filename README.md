# Payroll IIF -> QuickBooks Online Converter

Convert QuickBooks Desktop payroll / general-ledger **IIF** exports into the
**CSV** layout that QuickBooks Online accepts for journal-entry import.

QuickBooks Desktop can export an IIF file, but QuickBooks Online's journal
importer wants a specific CSV with account *names* (not numbers). This tool
bridges that gap: it reads the IIF, looks up account names from your chart of
accounts, and writes a balanced, import-ready CSV.

> **Runs entirely on your computer.** No internet connection is used and no
> data ever leaves your machine. It is pure Python standard library.

## Who it's for

Bookkeepers, accountants, and IT/MSP staff migrating payroll journal entries
from QuickBooks Desktop to QuickBooks Online.

## Features

- Converts one file or a whole batch.
- Reads the IIF layout from its header rows, so different export formats work.
- Translates account numbers to names using your chart of accounts.
- Checks every entry balances (debits = credits) and flags any that don't.
- Loads your chart by **Import** (a QuickBooks Online Account List export) or by
  typing accounts in by hand; both are saved and merged automatically.
- Ships with **no account data** — you load your own.

## Download and run

1. Download `PayrollConverter.exe` from the [Releases](../../releases) page.
2. Double-click it. (See the SmartScreen note below for the first run.)
3. Use **Import account list** to load your QuickBooks Online Account List
   export, or **Add a single account** for one-offs.
4. Choose your payroll `.iif` file(s) and click **Convert**. Each converted
   `.csv` is saved next to its source file, ready to import into QuickBooks
   Online.

### First-run SmartScreen note

Windows may show "Windows protected your PC" the first time you run a newly
downloaded program. Click **More info -> Run anyway**. This is normal for
independent software and is not specific to this tool.

## Build from source

Requires Python 3.8+ from [python.org](https://www.python.org/) ("Add to PATH").

```
pip install pyinstaller
pyinstaller --onefile --windowed --name PayrollConverter iif_to_qbo_gui.py
```

The executable appears in the `dist/` folder. You can also run without building:
`python iif_to_qbo_gui.py`.

## Verify your download

Each release lists a SHA-256 checksum. On Windows:

```
certutil -hashfile PayrollConverter.exe SHA256
```

Compare it to the value on the release page.

## Disclaimer

This project is **not affiliated with, endorsed by, or sponsored by Intuit Inc.
or Microsoft Corporation.** "QuickBooks," "QuickBooks Online," and "Intuit" are
trademarks of Intuit Inc. "Windows" is a trademark of Microsoft Corporation.
They are used here only to describe compatibility.

This software is provided "as is," without warranty of any kind. It does not
provide accounting advice. **Always review converted entries and test-import a
single entry before importing in bulk.** You are responsible for the accuracy
of your financial records.

## License

[MIT](LICENSE)
