# Trip Ledger

Trip Ledger is a local trip expense manager for shared travel and group spending. It lets a group create a trip, add expenses, track who paid, and automatically calculate balances and settlement suggestions.

## Features

- Create a trip with a name and a list of friends
- Add, edit, and delete expenses
- Track each expense with:
  - description
  - amount
  - payer
  - category
  - currency (`PKR` or `USD`)
  - split method
- Supported categories:
  - food
  - groceries
  - rent
  - fuel
  - tickets
- View trip totals, per-person balances, and category totals
- Automatically calculate who owes and who should receive money
- Suggest settlement transfers between participants
- Save the active trip in SQLite
- End the trip and archive the completed summary as JSON
- Preview and delete saved trips from the web app
- Store completed trip data in `trip-summary.json` files instead of spreadsheet files

## Requirements

- Python 3.10 or newer
- Modern web browser

This project uses Python's standard library only. No extra package installation is required.

## Run the web app

From the Trip Ledger project folder, run:

```powershell
python web_app.py
```

If `python` is not available on Windows, use:

```powershell
py web_app.py
```

Then open this URL in your browser:

```text
http://127.0.0.1:8000/
```

Keep the terminal running while using the app. Press `Ctrl+C` to stop the server.

## Optional CLI

The original command-line version is still available:

```powershell
python main.py
```

## Saved data

The app creates local files in the project folder:

- `trip_expenses.db`: working database for the current active trip
- `trips/`: archived trip folders, each containing a `trip-summary.json` file

These files are intentionally kept local because they may contain private trip information.

Each saved trip summary contains:

- trip name
- participant names
- full expense list
- category totals
- balances by person
- settlement suggestions
- created and updated timestamps

The data is stored as JSON for easy reading and portability.

## Project files

- `main.py`: core trip logic, SQLite handling, calculations, and CLI behavior
- `web_app.py`: local HTTP server, API routes, and archive management
- `index.html`: web app layout
- `index.js`: frontend logic and API calls
- `style.css`: page styling and responsive layout

## Notes

- There is no Excel export in the current version.
- Completed trips are saved as JSON summaries under the `trips/` directory.
- Archived trip data can be reviewed from the app homepage and deleted if needed.
