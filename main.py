"""Simple trip expense manager for a group of friends."""

from dataclasses import dataclass
import sqlite3

EXPENSE_CATEGORIES = ("food", "groceries", "rent", "fuel", "tickets")
CATEGORY_LABELS = {
	"food": "Food",
	"groceries": "Groceries",
	"rent": "Rent",
	"fuel": "Fuel",
	"tickets": "Tickets",
}
CATEGORY_ALIASES = {
	"foods": "food",
	"transport": "food",
	"accommodation": "rent",
	"activities": "food",
	"shopping": "food",
	"other": "food",
	"hotel": "food",
	"medical": "food",
	"groceries": "groceries",
}
CURRENCY_DESCRIPTIONS = {"USD": "Dollars", "PKR": "Pakistani Rupees"}


@dataclass
class Expense:
	expense_id: str
	description: str
	amount: float
	paid_by: str
	category: str
	currency: str = "PKR"
	currency_description: str = "Pakistani Rupees"
	split_method: str = "Equal"


def normalize_category(category: str) -> str:
	value = str(category).strip().lower()
	value = CATEGORY_ALIASES.get(value, value)
	if value not in EXPENSE_CATEGORIES:
		raise ValueError("Choose a valid expense category.")
	return value


class TripExpenses:
	def __init__(self, friends: list[str] | None = None, database_path: str = "trip_expenses.db") -> None:
		self.database = sqlite3.connect(database_path, timeout=10)
		self.database.execute("PRAGMA busy_timeout = 10000")
		self.database.execute("PRAGMA foreign_keys = ON")
		self.database.execute(
			"CREATE TABLE IF NOT EXISTS friends ("
			"id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)"
		)
		self.database.execute(
			"CREATE TABLE IF NOT EXISTS expenses ("
			"id INTEGER PRIMARY KEY, expense_id TEXT, description TEXT NOT NULL, "
			"amount REAL NOT NULL CHECK(amount > 0), "
			"paid_by TEXT NOT NULL REFERENCES friends(name), category TEXT NOT NULL DEFAULT 'food', "
			"currency TEXT NOT NULL DEFAULT 'PKR', currency_description TEXT NOT NULL DEFAULT 'Pakistani Rupees', split_method TEXT NOT NULL DEFAULT 'Equal')"
		)
		self.database.execute(
			"CREATE TABLE IF NOT EXISTS trip_metadata ("
			"trip_id TEXT PRIMARY KEY, trip_name TEXT NOT NULL, currency TEXT NOT NULL DEFAULT 'PKR', "
			"created_at TEXT NOT NULL, updated_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active')"
		)
		columns = [row[1] for row in self.database.execute("PRAGMA table_info(expenses)")]
		for column, definition in {"expense_id": "TEXT", "currency": "TEXT NOT NULL DEFAULT 'PKR'", "currency_description": "TEXT NOT NULL DEFAULT 'Pakistani Rupees'", "split_method": "TEXT NOT NULL DEFAULT 'Equal'"}.items():
			if column not in columns:
				self.database.execute(f"ALTER TABLE expenses ADD COLUMN {column} {definition}")
		for column in ("expense_date", "participants", "notes"):
			if column in columns:
				self.database.execute(f"ALTER TABLE expenses DROP COLUMN {column}")
		self.database.execute(
			"UPDATE expenses SET expense_id = COALESCE(expense_id, 'expense-' || id)"
		)
		self.database.commit()

		stored_friends = self.database.execute(
			"SELECT name FROM friends ORDER BY id"
		).fetchall()
		self.friends = [row[0] for row in stored_friends]
		if not self.friends and friends:
			self.friends = list(friends)
			self.database.executemany(
				"INSERT INTO friends (name) VALUES (?)",
				((friend,) for friend in self.friends),
			)
			self.database.commit()

		self.expenses = []
		for row in self.database.execute(
			"SELECT expense_id, description, amount, paid_by, category, currency, currency_description, split_method FROM expenses ORDER BY id"
		):
			expense_id, description, amount, paid_by, category, currency, currency_description, split_method = row
			category = normalize_category(category)
			currency_description = CURRENCY_DESCRIPTIONS.get(currency, currency_description)
			self.expenses.append(Expense(expense_id, description, amount, paid_by, category, currency, currency_description, split_method))
		self.database.executemany(
			"UPDATE expenses SET category = ? WHERE expense_id = ?",
			((expense.category, expense.expense_id) for expense in self.expenses),
		)
		self.database.commit()

	def add_expense(
		self, description: str, amount: float, paid_by: str, category: str = "food",
		currency: str = "PKR", split_method: str = "Equal"
	) -> None:
		if amount <= 0:
			raise ValueError("The amount must be greater than zero.")
		if paid_by not in self.friends:
			raise ValueError("The payer must be one of the trip friends.")
		category = normalize_category(category)
		if currency not in {"USD", "PKR"}:
			raise ValueError("Choose USD or PKR as the currency.")
		currency_description = CURRENCY_DESCRIPTIONS[currency]
		expense_id = f"expense-{self.database.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM expenses').fetchone()[0]}"
		self.database.execute(
			"INSERT INTO expenses (expense_id, description, amount, paid_by, category, currency, currency_description, split_method) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
			(expense_id, description, amount, paid_by, category, currency, currency_description, split_method),
		)
		self.database.commit()
		self.expenses.append(Expense(expense_id, description, amount, paid_by, category, currency, currency_description, split_method))

	def delete_expense(self, expense_id: str) -> None:
		if not self.database.execute("SELECT 1 FROM expenses WHERE expense_id = ?", (expense_id,)).fetchone():
			raise ValueError("The expense was not found.")
		self.database.execute("DELETE FROM expenses WHERE expense_id = ?", (expense_id,))
		self.database.commit()
		self.expenses = [expense for expense in self.expenses if expense.expense_id != expense_id]

	def update_expense(self, expense_id: str, description: str, amount: float, paid_by: str, category: str, currency: str = "PKR", split_method: str = "Equal") -> None:
		if amount <= 0:
			raise ValueError("The amount must be greater than zero.")
		if paid_by not in self.friends:
			raise ValueError("The payer must be one of the trip friends.")
		category = normalize_category(category)
		if currency not in {"USD", "PKR"}:
			raise ValueError("Choose USD or PKR as the currency.")
		currency_description = CURRENCY_DESCRIPTIONS[currency]
		current = next((expense for expense in self.expenses if expense.expense_id == expense_id), None)
		if current is None:
			raise ValueError("The expense was not found.")
		self.database.execute(
			"UPDATE expenses SET description = ?, amount = ?, paid_by = ?, category = ?, currency = ?, currency_description = ?, split_method = ? WHERE expense_id = ?",
			(description, amount, paid_by, category, currency, currency_description, split_method, expense_id),
		)
		self.database.commit()
		self.expenses = [
			Expense(expense.expense_id, description, amount, paid_by, category, currency, currency_description, split_method)
			if expense.expense_id == expense_id else expense
			for expense in self.expenses
		]

	def metadata(self) -> dict[str, str] | None:
		row = self.database.execute("SELECT trip_id, trip_name, currency, created_at, updated_at, status FROM trip_metadata LIMIT 1").fetchone()
		if not row:
			return None
		return dict(zip(("trip_id", "trip_name", "currency", "created_at", "updated_at", "status"), row))

	def set_metadata(self, metadata: dict[str, str]) -> None:
		self.database.execute("DELETE FROM trip_metadata")
		self.database.execute(
			"INSERT INTO trip_metadata (trip_id, trip_name, currency, created_at, updated_at, status) VALUES (?, ?, ?, ?, ?, ?)",
			(tuple(metadata[key] for key in ("trip_id", "trip_name", "currency", "created_at", "updated_at", "status"))),
		)
		self.database.commit()

	def close(self) -> None:
		self.database.close()

	def reset(self) -> None:
		"""Clear the active trip while keeping the SQLite database available."""
		self.database.execute("DELETE FROM expenses")
		self.database.execute("DELETE FROM friends")
		self.database.execute("DELETE FROM trip_metadata")
		self.database.commit()
		self.friends = []
		self.expenses = []

	def total_spent(self) -> float:
		return sum(expense.amount for expense in self.expenses)

	def shares(self) -> dict[str, float]:
		# Divide the trip total equally among all friends.
		share = self.total_spent() / len(self.friends)
		return {friend: share for friend in self.friends}

	def paid_totals(self) -> dict[str, float]:
		totals = {friend: 0.0 for friend in self.friends}
		for expense in self.expenses:
			totals[expense.paid_by] += expense.amount
		return totals

	def currency_paid_totals(self) -> dict[str, dict[str, float]]:
		return {
			currency: {friend: sum(expense.amount for expense in self.expenses if expense.currency == currency and expense.paid_by == friend) for friend in self.friends}
			for currency in ("USD", "PKR")
		}

	def currency_balances(self) -> dict[str, dict[str, float]]:
		return {
			currency: {
				friend: paid - self.currency_totals().get(currency, 0.0) / len(self.friends)
				for friend, paid in self.currency_paid_totals()[currency].items()
			}
			for currency in ("USD", "PKR")
		}

	def currency_settlements(self) -> list[tuple[str, str, float, str]]:
		transfers = []
		for currency, balances in self.currency_balances().items():
			creditors = [[friend, balance] for friend, balance in balances.items() if balance > 0.005]
			debtors = [[friend, -balance] for friend, balance in balances.items() if balance < -0.005]
			while creditors and debtors:
				amount = min(creditors[0][1], debtors[0][1])
				transfers.append((debtors[0][0], creditors[0][0], round(amount, 2), currency))
				creditors[0][1] -= amount
				debtors[0][1] -= amount
				if creditors[0][1] < 0.005:
					creditors.pop(0)
				if debtors[0][1] < 0.005:
					debtors.pop(0)
		return transfers

	def category_totals(self) -> dict[str, float]:
		totals = {category: 0.0 for category in EXPENSE_CATEGORIES}
		for expense in self.expenses:
			totals[expense.category] += expense.amount
		return totals

	def currency_totals(self) -> dict[str, float]:
		totals = {"USD": 0.0, "PKR": 0.0}
		for expense in self.expenses:
			totals[expense.currency] += expense.amount
		return {currency: amount for currency, amount in totals.items() if amount}

	def category_currency_totals(self) -> dict[str, dict[str, float]]:
		totals = {category: {} for category in EXPENSE_CATEGORIES}
		for expense in self.expenses:
			totals[expense.category][expense.currency] = totals[expense.category].get(expense.currency, 0.0) + expense.amount
		return totals

	def balances(self) -> dict[str, float]:
		shares = self.shares()
		paid = self.paid_totals()
		return {friend: paid[friend] - shares[friend] for friend in self.friends}

	def settlements(self) -> list[tuple[str, str, float]]:
		creditors = [[friend, balance] for friend, balance in self.balances().items() if balance > 0.005]
		debtors = [[friend, -balance] for friend, balance in self.balances().items() if balance < -0.005]
		transfers: list[tuple[str, str, float]] = []
		creditor_index = 0
		debtor_index = 0

		while creditor_index < len(creditors) and debtor_index < len(debtors):
			creditor, credit = creditors[creditor_index]
			debtor, debt = debtors[debtor_index]
			amount = min(credit, debt)
			transfers.append((debtor, creditor, round(amount, 2)))
			creditors[creditor_index][1] -= amount
			debtors[debtor_index][1] -= amount
			if creditors[creditor_index][1] < 0.005:
				creditor_index += 1
			if debtors[debtor_index][1] < 0.005:
				debtor_index += 1
		return transfers


def read_category() -> str:
	while True:
		print("Category: " + ", ".join(EXPENSE_CATEGORIES))
		category = input("Expense category: ").strip().lower()
		if category in EXPENSE_CATEGORIES:
			return category
		print("Choose one of the listed expense categories.")


def read_amount() -> float:
	while True:
		try:
			amount = float(input("Amount: "))
			if amount > 0:
				return amount
		except ValueError:
			pass
		print("Enter a number greater than zero.")


def show_summary(trip: TripExpenses) -> None:
	print(f"\nTotal spent: ${trip.total_spent():.2f}")
	if not trip.expenses:
		print("No expenses recorded yet.")
		return

	share = trip.total_spent() / len(trip.friends)
	paid = trip.paid_totals()
	balances = trip.balances()
	print(f"Each friend owes: ${share:.2f}")
	print("\nExpenses by category:")
	for category, amount in trip.category_totals().items():
		if amount:
			print(f"- {category.title()}: ${amount:.2f}")
	print("\nFriend summary:")
	for friend in trip.friends:
		status = "gets back" if balances[friend] >= 0 else "owes"
		print(f"- {friend}: paid ${paid[friend]:.2f}, {status} ${abs(balances[friend]):.2f}")

	print("\nSuggested settlements:")
	transfers = trip.settlements()
	if transfers:
		for debtor, creditor, amount in transfers:
			print(f"- {debtor} pays {creditor} ${amount:.2f}")
	else:
		print("Everyone is settled up.")


def main() -> None:
	print("Trip Expense Manager")
	trip = TripExpenses()
	try:
		if trip.friends:
			print("Loaded saved trip data from trip_expenses.db.")
		else:
			while True:
				raw_friends = input("Enter friend names separated by commas: ").strip()
				friends = [name.strip() for name in raw_friends.split(",") if name.strip()]
				if friends and len(set(friends)) == len(friends):
					trip.close()
					trip = TripExpenses(friends)
					break
				print("Enter at least one unique friend name.")

		while True:
			print("\n1. Add expense\n2. Show summary\n3. Exit")
			choice = input("Choose an option: ").strip()
			if choice == "1":
				description = input("Description: ").strip() or "Expense"
				category = read_category()
				amount = read_amount()
				print("Payer: " + ", ".join(trip.friends))
				payer = input("Who paid? ").strip()
				try:
					trip.add_expense(description, amount, payer, category)
					print("Expense added and saved.")
				except ValueError as error:
					print(error)
			elif choice == "2":
				show_summary(trip)
			elif choice == "3":
				print("Goodbye!")
				break
			else:
				print("Choose 1, 2, or 3.")
	finally:
		trip.close()


if __name__ == "__main__":
	main()
