# Payroll IIF to QBO Converter

Convert QuickBooks Desktop payroll / general-ledger **IIF** exports into the
**CSV** layout that QuickBooks Online accepts for journal-entry import.

QuickBooks Desktop can export an IIF file, but QuickBooks Online's journal
importer expects a specific CSV that uses account *names* (not numbers). This
tool bridges that gap: it reads the IIF, looks up account names from your chart
of accounts, checks that every entry balances, and writes a clean,
import-ready CSV.

> **Runs entirely on your computer.** No internet connection is used and no data
> ever leaves your machine. It is built with the Python standard library only.

---

## Who it's for

Bookkeepers, accountants, and IT/MSP staff moving payroll journal entries from
QuickBooks Desktop to QuickBooks Online.

## Features

- Converts one file or a whole batch in one click.
- Reads the column layout from the IIF header rows, so different export formats
  all work.
- Translates account numbers to account names using your chart of accounts.
- Verifies each entry balances (debits = credits) and flags any that don't.
- Loads your chart two ways, both saved and merged automatically:
  - **Import account list** — a QuickBooks Online "Account List" export (CSV); or
  - **Add a single account** — type a number and name for one-off additions.
- Ships with **no account data** — you supply your own.

---

## Download and run

1. Download `PayrollConverter.exe` from the
   [Releases page](https://github.com/krink192/payroll-iif-to-qbo/releases).
2. Double-click it. (See the SmartScreen note below for the first run.)
3. Click **Import account list** and choose your QuickBooks Online Account List
   export, or use **Add a single account** for one-offs.
4. Click **Choose**, select your payroll `.iif` file(s), and click **Convert**.
   Each converted `.csv` is saved next to its source file, ready to import into
   QuickBooks Online.

> **Code signing:** release binaries are code-signed via the
> [SignPath Foundation](https://signpath.org/), which provides free code-signing
> certificates to qualifying open-source projects. See
> [CODE_SIGNING.md](CODE_SIGNING.md). Until signing is fully configured, release
> binaries are unsigned — verify the published SHA-256 checksum (below).

### First-run SmartScreen note

Windows may show "Windows protected your PC" the first time you run a newly
downloaded program. Click **More info → Run anyway**. This is normal for
independent software and is not specific to this tool.

---

## Importing into QuickBooks Online

Open the journal-entry import in QuickBooks Online (typically the gear menu →
Import Data → Journal Entries, or **+ New** → Journal Entry import, depending on
your view) and choose the `.csv` this tool produced. **Import one entry as a
test before importing a large batch.**

## Updating your account list

If accounts are added or renamed in QuickBooks Online, just click **Import
account list** again and choose a fresh export, or **Add a single account**.
Everything you import or add is remembered and merged, so nothing is lost.

---

## Build from source

Requires Python 3.8+ from [python.org](https://www.python.org/) (check "Add to
PATH" during install).

```
pip install pyinstaller
pyinstaller --onefile --windowed --name PayrollConverter iif_to_qbo_gui.py
```

The executable appears in the `dist/` folder. You can also run it without
building:

```
python iif_to_qbo_gui.py
```

There are no third-party runtime dependencies — only the Python standard
library and Tkinter (included with Python). PyInstaller is the only build-time
tool.

## Verify your download

Each release includes a SHA-256 checksum. On Windows:

```
certutil -hashfile PayrollConverter.exe SHA256
```

Compare the result to the value published with the release.

## Test files

The `test_files/` folder contains fictional sample data for trying the tool:
four sample `.iif` files and a sample chart of accounts to import. Three samples
convert cleanly; `sample_4_HAS_BAD_ACCOUNT.iif` intentionally references an
account that isn't in the sample chart so you can see the "no account name
found" warning.

---

## Disclaimer

This project is **not affiliated with, endorsed by, or sponsored by Intuit Inc.
or Microsoft Corporation.** "QuickBooks," "QuickBooks Online," and "Intuit" are
trademarks of Intuit Inc. "Windows" is a trademark of Microsoft Corporation.
They are used here only to describe compatibility.

This software is provided "as is," without warranty of any kind. It does not
provide accounting advice. **Always review converted entries and test-import a
single entry before importing in bulk.** You are responsible for the accuracy of
your financial records.

## License

[MIT](LICENSE)
