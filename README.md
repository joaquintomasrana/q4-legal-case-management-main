# Q4 Legal Case Management

A desktop application for law practices to manage legal case files — parties, procedural steps, deadlines, fees, expenses and document attachments — built with Python and Tkinter, persisting everything to a local SQLite database.

Designed for solo practitioners and small firms that want a fast, offline tool with zero setup: no server, no accounts, no external dependencies.

## Features

### Case management

- Create, edit and delete case files with number, title, jurisdiction/court, start date, case type, status (`active` / `archived` / `closed`) and free-form notes.
- Live search and filtering by number, title, status and court — accent-insensitive, so "Pérez" and "perez" both match.
- Sortable columns (click any header; dates sort chronologically).
- Duplicate case numbers are detected and rejected gracefully.
- A "Last Activity" column shows the date of each case's most recent procedural step at a glance.

### Per-case detail view

- **Parties** — plaintiffs, defendants, third parties, experts, witnesses, with contact details.
- **Procedural Steps** — a dated timeline of everything that happened in the case.
- **Deadlines** — color-coded: red when overdue, yellow when due within 5 days, green when completed.
- **Fees & Expenses** — amounts in ARS or USD with per-currency totals and payment method tracking.
- **Attachments** — files are copied into a per-case folder and can be opened directly from the app.

### Global views

- **All Deadlines** — every deadline across active cases in one table, with status filtering and one-click status changes.
- **Collected Fees** — all fees across cases with currency filtering and running totals.

### Data safety

- Automatic rotating backups: every launch snapshots the database, keeping the 10 most recent copies in `backups/`.
- Schema migrations run automatically on startup — older databases are upgraded transparently.
- Deleting a case cascades cleanly: all related records and attachment files are removed.

## Tech stack

- **Python 3.10+** — standard library only, no external packages.
- **Tkinter / ttk** — native desktop UI with a custom theme.
- **SQLite** — single-file local database with foreign keys and CHECK constraints.

## Getting started

Run from source:

```bash
git clone https://github.com/joaquintomasrana/q4-legal-case-management.git
cd q4-legal-case-management
python main.py
```

That's it. The database (`expedientes.db`) is created automatically on first run.

### Requirements

- Python 3.10 or higher (Tkinter is included in the standard Windows/macOS installers).

## Usage notes

- **Dates** are entered and displayed as `DD/MM/YYYY`; they are stored internally as ISO (`YYYY-MM-DD`) so sorting and comparisons are always correct.
- **Dialogs**: `Enter` saves, `Escape` cancels.
- **Double-click** a case row to jump straight to its Procedural Steps tab.
- **Amounts** accept dots as thousands separators (`1.500.000` → `1500000`).

## Importing cases from CSV

A helper script bulk-imports cases from a CSV file with two columns (`case title`, `case type`):

```bash
python importar_csv.py cases.csv
```

Rows with missing columns or an empty title are skipped and reported.

## Data storage

| Location | Contents |
| --- | --- |
| `expedientes.db` | SQLite database with all case data |
| `adjuntos/<case_id>/` | Attached files, one folder per case |
| `backups/` | Rotating database backups (last 10 launches) |

All three live next to the application, so backing up the whole folder backs up everything.

## Packaging a standalone executable

The app supports being frozen with [PyInstaller](https://pyinstaller.org/) — when packaged, the database, attachments and backups are kept next to the executable:

```bash
pip install pyinstaller pillow
pyinstaller --onefile --windowed --icon=icon.png --name Q4-Legal-Case-Management main.py
```

The binary is generated in `dist/`. (Pillow is only needed at build time, to convert the PNG icon.)

## Project structure

```text
q4-legal-case-management/
|-- main.py                    # Entry point: DPI setup, DB init, main loop
|-- database.py                # SQLite layer: schema, migrations, backups, queries
|-- models.py                  # Dataclasses shared between the DB layer and the UI
|-- importar_csv.py            # CSV bulk-import script
|-- ui/
|   |-- app.py                 # Main window and sidebar navigation
|   |-- expedientes.py         # Case list panel (search, filters, sorting)
|   |-- detalle_expediente.py  # Case detail window with tabs
|   |-- vencimientos.py        # Global deadlines panel
|   |-- honorarios.py          # Global fees panel
|   |-- dialogs.py             # Generic form dialog, validation, date helpers
|   `-- styles.py              # ttk theme and color palette
|-- tests/
|   `-- test_database.py       # unittest suite for the database layer
`-- docs/
    `-- ARCHITECTURE.md        # Design decisions and database schema
```

For a deeper look at the design — layering, database schema, the migration system and other decisions — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Running tests

```bash
python -m unittest discover -v
```

The suite covers the database layer — CRUD, accent-insensitive search, cascade deletes, backup rotation and the legacy migration path — against throwaway databases in temporary directories. It also runs on every push via GitHub Actions.

## Notes

- The application is designed for local, single-user use.
- On Windows it enables per-monitor DPI awareness for a sharp UI on high-resolution displays.
- The UI is in English; the database file and folder names (`expedientes.db`, `adjuntos/`) are kept stable for backward compatibility with existing installations.

## License

[MIT](LICENSE)
