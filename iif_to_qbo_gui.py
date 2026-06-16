#!/usr/bin/env python3
"""Payroll Converter - graphical front end.

A simple desktop window over the conversion engine in :mod:`iif_to_qbo`. The
operator picks one or more QuickBooks Desktop payroll IIF files and clicks
Convert; each is written as a QuickBooks Online journal-import CSV beside the
original.

Account names come from three merged sources, in priority order (later wins):

    1. the built-in sample chart (:mod:`embedded_accounts`);
    2. an imported chart - a QuickBooks Online "Account List" export brought in
       with the Import button and saved beside the program; and
    3. accounts typed into the Add fields, saved beside the program.

The program ships with no real client data. The client imports their own chart
once, or adds accounts as needed; both persist and always merge in.

This module contains only presentation and file-management logic; all parsing
and conversion lives in :mod:`iif_to_qbo`.
"""

from __future__ import annotations

import csv
import os
import shutil
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext
from typing import Dict, List, Tuple

from iif_to_qbo import (
    __version__, convert_file, load_account_map, looks_like_account_map,
)
from embedded_accounts import ACCOUNTS as EMBEDDED_ACCOUNTS

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

#: Filename under which an imported chart is saved in the program's folder.
IMPORTED_CHART_FILE = "imported_chart.csv"
#: Filename under which manually added accounts are saved.
ADDED_ACCOUNTS_FILE = "added_accounts.csv"
#: Currency code written to the first line of each journal entry.
DEFAULT_CURRENCY = "USD"

# Visual palette (modern, flat).
BG = "#EEF1F6"
CARD = "#FFFFFF"
ACCENT = "#2563EB"
ACCENT_DARK = "#1E40AF"
ACCENT_SOFT = "#EEF2FF"
TEXT = "#1F2937"
MUTED = "#6B7280"
BORDER = "#D9DEE7"
OK_GREEN = "#15803D"
WARN_AMBER = "#B45309"
FONT = "Segoe UI"          # standard on Windows; Tk falls back if absent


# --------------------------------------------------------------------------- #
# Chart-of-accounts resolution
# --------------------------------------------------------------------------- #

def program_folder() -> Path:
    """Return the folder the program runs from.

    Works whether running as a plain script or as a PyInstaller-built ``.exe``.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def resolve_account_map() -> Tuple[Dict[str, str], str]:
    """Build the active account map by MERGING all available sources.

    Starts from the built-in sample chart, then layers on every chart-of-accounts
    CSV found in the program's folder (the imported chart, manually added
    accounts, or any chart file dropped in). Later files override earlier ones,
    and the newest file wins any conflict.

    Returns:
        ``(mapping, source_description)`` where ``mapping`` is account number ->
        name and ``source_description`` is a short human-readable summary.
    """
    folder = program_folder()
    mapping: Dict[str, str] = dict(EMBEDDED_ACCOUNTS)
    externals = sorted(
        (p for p in folder.glob("*")
         if p.is_file() and p.suffix.lower() in (".csv", ".txt")
         and looks_like_account_map(p)),
        key=lambda p: p.stat().st_mtime,         # oldest first; newest applied last
    )
    applied: List[str] = []
    for path in externals:
        try:
            extra = load_account_map(path)
        except OSError:
            continue
        if extra:
            mapping.update(extra)
            applied.append(path.name)

    if applied:
        source = ", ".join(applied)
    elif mapping:
        source = "built-in"
    else:
        source = "none yet \u2014 Import or Add accounts to begin"
    return mapping, source


# --------------------------------------------------------------------------- #
# Application window
# --------------------------------------------------------------------------- #

class ConverterApp:
    """The main application window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.iif_files: List[str] = []
        self.account_map, self.map_source = resolve_account_map()

        root.title("Payroll Converter")
        root.geometry("740x800")
        root.minsize(700, 740)
        root.configure(bg=BG)

        self._build_header()
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(16, 16))
        self._build_file_card(body)
        self._build_convert_button(body)
        self._build_account_card(body)        # pinned to the bottom, always visible
        self._build_results(body)             # expands to fill the space in between
        self._build_footer()
        self.update_status()

    # -- UI construction --------------------------------------------------- #
    def _card(self, parent: tk.Widget, title: str, side: str = "top") -> tk.Frame:
        """Create a titled white 'card' container and return its body frame."""
        outer = tk.Frame(parent, bg=CARD, highlightbackground=BORDER,
                         highlightthickness=1, bd=0)
        outer.pack(fill="x", pady=(0, 14), side=side)
        tk.Label(outer, text=title, bg=CARD, fg=TEXT,
                 font=(FONT, 13, "bold")).pack(anchor="w", padx=16, pady=(12, 0))
        body = tk.Frame(outer, bg=CARD)
        body.pack(fill="x", padx=16, pady=(6, 14))
        return body

    def _accent_button(self, parent: tk.Widget, text: str, command, big: bool = False) -> tk.Button:
        return tk.Button(parent, text=text, command=command, bg=ACCENT, fg="white",
                         activebackground=ACCENT_DARK, activeforeground="white",
                         relief="flat", cursor="hand2", bd=0,
                         font=(FONT, 13 if big else 11, "bold"),
                         padx=18, pady=(12 if big else 7))

    def _ghost_button(self, parent: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(parent, text=text, command=command, bg=CARD, fg=ACCENT,
                         activebackground=ACCENT_SOFT, activeforeground=ACCENT_DARK,
                         relief="flat", cursor="hand2",
                         highlightbackground=BORDER, highlightthickness=1, bd=0,
                         font=(FONT, 11, "bold"), padx=14, pady=7)

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=ACCENT)
        header.pack(fill="x")
        inner = tk.Frame(header, bg=ACCENT)
        inner.pack(fill="x", padx=24, pady=18)
        tk.Label(inner, text="Payroll Converter", bg=ACCENT, fg="white",
                 font=(FONT, 22, "bold")).pack(anchor="w")
        tk.Label(inner,
                 text="Turn any .IIF payroll file into a QuickBooks Online Import .csv",
                 bg=ACCENT, fg="#DBEAFE", font=(FONT, 11)).pack(anchor="w", pady=(2, 0))

    def _build_file_card(self, parent: tk.Widget) -> None:
        body = self._card(parent, "1.  Choose your payroll file(s)")
        tk.Label(body, bg=CARD, fg=MUTED, font=(FONT, 10), justify="left",
                 text="Pick one file, or several at once (hold Ctrl and click each)."
                 ).pack(anchor="w")
        row = tk.Frame(body, bg=CARD)
        row.pack(fill="x", pady=(10, 0))
        self.files_label = tk.Label(row, bg=CARD, fg=MUTED, anchor="w",
                                    font=(FONT, 12), text="No files chosen")
        self.files_label.pack(side="left", fill="x", expand=True)
        self._ghost_button(row, "Choose\u2026", self.choose_files).pack(side="right")

    def _build_convert_button(self, parent: tk.Widget) -> None:
        self._accent_button(parent, "Convert", self.convert, big=True).pack(
            fill="x", pady=(0, 14))

    def _build_results(self, parent: tk.Widget) -> None:
        wrap = tk.Frame(parent, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1, bd=0)
        wrap.pack(fill="both", expand=True, pady=(0, 14))
        tk.Label(wrap, text="Results", bg=CARD, fg=TEXT,
                 font=(FONT, 13, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        self.results = scrolledtext.ScrolledText(
            wrap, font=("Consolas", 11), height=8, wrap="word", state="disabled",
            relief="flat", bg="#FBFCFE", fg=TEXT, bd=0, padx=10, pady=8)
        self.results.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def _build_account_card(self, parent: tk.Widget) -> None:
        body = self._card(parent, "Account list", side="bottom")
        self.status_label = tk.Label(body, bg=CARD, fg=MUTED, font=(FONT, 10),
                                     anchor="w", justify="left")
        self.status_label.pack(anchor="w")

        imp = tk.Frame(body, bg=CARD)
        imp.pack(fill="x", pady=(8, 0))
        tk.Label(imp, text="Import account list (from QuickBooks)", bg=CARD,
                 fg=TEXT, font=(FONT, 11, "bold")).pack(side="left", anchor="w")
        self._ghost_button(imp, "Import account list\u2026", self.import_chart).pack(side="right")

        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=12)

        arow = tk.Frame(body, bg=CARD)
        arow.pack(fill="x")
        tk.Label(arow, text="Add account  \u2014  Number", bg=CARD, fg=TEXT,
                 font=(FONT, 11, "bold")).pack(side="left")
        self.num_entry = tk.Entry(arow, font=(FONT, 12), width=8, relief="flat",
                                  highlightbackground=BORDER, highlightthickness=1)
        self.num_entry.pack(side="left", padx=(6, 14), ipady=3)
        tk.Label(arow, text="Name", bg=CARD, fg=TEXT, font=(FONT, 11, "bold")).pack(side="left")
        self.name_entry = tk.Entry(arow, font=(FONT, 12), relief="flat",
                                   highlightbackground=BORDER, highlightthickness=1)
        self.name_entry.pack(side="left", fill="x", expand=True, padx=(6, 14), ipady=3)
        self._ghost_button(arow, "Add", self.add_account).pack(side="right")

    def _build_footer(self) -> None:
        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer, bg=BG, fg="#9AA3B2", font=(FONT, 9),
                 text=f"Payroll Converter v{__version__}").pack(pady=(0, 8))

    # -- display helpers --------------------------------------------------- #
    def refresh_labels(self) -> None:
        count = len(self.iif_files)
        if count == 0:
            self.files_label.config(text="No files chosen", fg=MUTED)
        elif count == 1:
            self.files_label.config(text=Path(self.iif_files[0]).name, fg=TEXT)
        else:
            self.files_label.config(text=f"{count} files chosen", fg=TEXT)

    def update_status(self) -> None:
        self.status_label.config(
            text=f"{len(self.account_map)} accounts in use  \u2022  source: {self.map_source}")

    def say(self, text: str, clear: bool = False) -> None:
        """Append a line to the results box (optionally clearing it first)."""
        self.results.config(state="normal")
        if clear:
            self.results.delete("1.0", "end")
        self.results.insert("end", text + "\n")
        self.results.see("end")
        self.results.config(state="disabled")
        self.root.update_idletasks()

    # -- actions ----------------------------------------------------------- #
    def choose_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Choose your payroll file(s)",
            filetypes=[("Payroll files", "*.iif *.IIF *.txt"), ("All files", "*.*")])
        if paths:
            self.iif_files = list(paths)
            self.refresh_labels()

    def convert(self) -> None:
        if not self.iif_files:
            self.say("Please choose at least one payroll file first.", clear=True)
            return

        # Re-resolve every run so a freshly imported or added account takes effect.
        self.account_map, self.map_source = resolve_account_map()
        self.update_status()

        self.say("Working\u2026", clear=True)
        last_folder = None
        for path in map(Path, self.iif_files):
            try:
                result = convert_file(path, DEFAULT_CURRENCY, self.account_map)
            except Exception as exc:             # noqa: BLE001 - report and continue
                self.say(f"\u2717  {path.name}: could not convert ({exc})")
                continue
            last_folder = path.parent
            self.say(f"\u2713  Created {result.output_name}  ({result.entries} entries)")
            for jno, debits, credits in result.unbalanced:
                self.say(f"     \u26a0  Journal {jno} does not balance: "
                         f"debits {debits:.2f} vs credits {credits:.2f}. Check this entry.")
            if result.unmapped:
                self.say(f"     \u26a0  No account name found for: "
                         f"{', '.join(result.unmapped)}.")
                self.say("        Add the name below, or import an updated account list.")

        self.say("\nDone. Converted file(s) are saved next to your payroll file(s).")
        if last_folder is not None:
            self._offer_open_folder(last_folder)

    def import_chart(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose your QuickBooks Online Account List export (CSV)",
            filetypes=[("CSV files", "*.csv *.txt"), ("All files", "*.*")])
        if not path:
            return
        source = Path(path)
        if not looks_like_account_map(source):
            self.say("That file does not look like a chart of accounts.\n"
                     "In QuickBooks Online, export the Account List report with the "
                     "Account # column turned on, then import that CSV.", clear=True)
            return
        dest = program_folder() / IMPORTED_CHART_FILE
        try:
            if source.resolve() != dest.resolve():
                shutil.copyfile(source, dest)
        except Exception as exc:                 # noqa: BLE001
            self.say(f"Could not import the file: {exc}", clear=True)
            return
        self.account_map, self.map_source = resolve_account_map()
        self.update_status()
        imported = len(load_account_map(dest))
        self.say(f"Imported {imported} accounts from \u201C{source.name}\u201D.\n"
                 f"They are saved and have been merged into the account list.",
                 clear=True)

    def add_account(self) -> None:
        number = self.num_entry.get().strip()
        name = self.name_entry.get().strip()
        if not number or not name:
            self.say("Type both an account number and a name, then click Add.", clear=True)
            return

        path = program_folder() / ADDED_ACCOUNTS_FILE
        existing: Dict[str, str] = {}
        if path.is_file():
            try:
                existing = load_account_map(path)
            except OSError:
                existing = {}
        replacing = number in existing
        existing[number] = name

        try:
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Number", "Name"])
                for key, value in sorted(existing.items()):
                    writer.writerow([key, value])
        except OSError as exc:
            self.say(f"Could not save the account: {exc}", clear=True)
            return

        self.account_map, self.map_source = resolve_account_map()
        self.update_status()
        verb = "Updated" if replacing else "Added"
        self.say(f"{verb} account {number} = {name}.\n"
                 f"It is saved and will be used from now on.", clear=True)
        self.num_entry.delete(0, "end")
        self.name_entry.delete(0, "end")

    def _offer_open_folder(self, folder: Path) -> None:
        """Show a button that opens the folder containing the converted files."""
        def open_folder() -> None:
            try:
                if sys.platform.startswith("win"):
                    os.startfile(folder)          # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    os.system(f'open "{folder}"')
                else:
                    os.system(f'xdg-open "{folder}"')
            except Exception:                     # noqa: BLE001
                pass
        if not hasattr(self, "_open_btn"):
            self._open_btn = self._ghost_button(
                self.root, "Open the folder with my files", open_folder)
            self._open_btn.pack(pady=(0, 10))
        else:
            self._open_btn.config(command=open_folder)


def main() -> None:
    """Launch the application."""
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
