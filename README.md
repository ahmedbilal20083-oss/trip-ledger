# Trip Ledger

Trip Ledger is a simple trip expense manager I built with Python to help friends keep track of shared expenses during a trip.

The idea came from a common problem: when different people pay for food, fuel, tickets, groceries, or other expenses, it can become difficult to keep track of who paid what and who owes money at the end of the trip.

With Trip Ledger, users can create a trip, add participants, record expenses, and automatically calculate each person's share and balance. The application also suggests settlement transfers to make it easier to figure out who should pay whom.

I built this project while learning Python, using it to practice real-world programming concepts such as **Python, SQLite, JSON, data structures, calculations, input validation, and web development**.

### Features

* Create trips and add participants
* Add, edit, and delete expenses
* Track who paid for each expense
* Support for PKR and USD
* Expense categories such as food, groceries, rent, fuel, and tickets
* Automatically calculate individual shares and balances
* Show who owes money and who should receive money
* Suggest simple settlement transfers
* Store active trip data using SQLite
* Archive completed trips as JSON
* Preview and delete saved trips
* Includes both a web interface and command-line version

### Technologies

* **Python 3.10+**
* **SQLite**
* **HTML**
* **CSS**
* **JavaScript**
* **JSON**
* Python `dataclasses` and `sqlite3`

## How to Run

### Requirements

* Python 3.10 or newer
* A modern web browser

### Run the Web App

Open a terminal in the project folder and run:

```powershell
python web_app.py
```

On Windows, if `python` is not available:

```powershell
py web_app.py
```

Then open the following address in your browser:

```text
http://127.0.0.1:8000/
```

Keep the terminal running while using the application.

Press `Ctrl+C` in the terminal to stop the server.

### Run the Command-Line Version

The original command-line version is also included:

```powershell
python main.py
```

## Data Storage

The active trip is stored locally in:

```text
trip_expenses.db
```

When a trip is completed, its information is archived under:

```text
trips/
```

Each completed trip contains a:

```text
trip-summary.json
```

The JSON summary includes the trip name, participants, expenses, category totals, balances, settlement suggestions, and timestamps.

I chose JSON for the archived summaries because it keeps the data structured, readable, and easy to work with.

The database and archived trip files are kept out of Git because they may contain private expense information.


### What I Learned

This project helped me understand how a small application is built from different parts working together. I practiced Python classes and functions, dataclasses, lists and dictionaries, database operations, JSON file handling, input validation, calculations, and connecting a Python backend with a browser-based interface.

The most interesting part for me was building the **balance and settlement logic**, where the application compares what each person paid with their actual share and calculates the required payments between participants.

### Why I Built It

I wanted to build something more practical than a basic Python exercise. Instead of following only tutorials, I wanted to take a real-world problem and turn it into a working application.

Trip Ledger is still a learning project, but it helped me improve my Python skills and gave me experience with databases, backend logic, frontend development, and organizing a complete project.

### Future Improvements

* More flexible expense-splitting options
* Better settlement optimization
* Expense charts and analytics
* Automated testing
* User accounts
* Cloud database support
* Online deployment

This project is part of my ongoing journey of learning Python and software development.
