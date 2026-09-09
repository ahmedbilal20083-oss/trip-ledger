"""Browser interface for the trip expense manager."""

import json
import re
import shutil
import tempfile
import uuid
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from main import CATEGORY_LABELS, EXPENSE_CATEGORIES, TripExpenses

HOST = "127.0.0.1"
PORT = 8000
ROOT = Path(__file__).parent
ARCHIVE_DIR = ROOT / "trips"
DATABASE_PATH = ROOT / "trip_expenses.db"
trip = TripExpenses(database_path=str(DATABASE_PATH))
trip_metadata = trip.metadata()
trip_name = trip_metadata["trip_name"] if trip_metadata else ""
trip_id = trip_metadata["trip_id"] if trip_metadata else ""

TRIP_SUMMARY_FILE = "trip-summary.json"
CANONICAL_FILES = {TRIP_SUMMARY_FILE}


def archived_trips() -> list[dict[str, Any]]:
    ARCHIVE_DIR.mkdir(exist_ok=True)
    archives = []
    for archive_folder in sorted(ARCHIVE_DIR.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True):
        archive_file = archive_folder / TRIP_SUMMARY_FILE
        try:
            if not archive_folder.is_dir() or not archive_file.is_file():
                continue
            archive = json.loads(archive_file.read_text(encoding="utf-8"))
            if archive.get("status") != "completed":
                continue
            currency_totals = {}
            for expense in archive.get("expenses", []):
                currency = expense.get("currency", "PKR")
                currency_totals[currency] = currency_totals.get(currency, 0) + float(expense.get("amount", 0))
            archives.append({
                "folder": archive_folder.name,
                "name": archive.get("trip_name", "Untitled trip"),
                "ended_at": archive.get("updated_at", ""),
                "total": sum(currency_totals.values()),
                "currency_totals": currency_totals,
                "friends": len(archive.get("friends", archive.get("participants", []))),
                "expenses": len(archive.get("expenses", [])) or archive.get("financial_summary", {}).get("expense_count", 0),
            })
        except (OSError, json.JSONDecodeError, KeyError):
            continue
    return archives


def archive_folder(folder_name: str) -> Path:
    folder_name = unquote(folder_name)
    if not re.fullmatch(r"[A-Za-z0-9 _-]+", folder_name):
        raise ValueError("Invalid archived trip.")
    for folder in ARCHIVE_DIR.iterdir() if ARCHIVE_DIR.exists() else []:
        summary_file = folder / TRIP_SUMMARY_FILE
        if folder.is_dir() and summary_file.is_file() and folder.name == folder_name:
            return folder
    raise FileNotFoundError("Saved trip was not found.")


def archived_trip_payload(folder: Path) -> dict[str, Any]:
    summary = json.loads((folder / TRIP_SUMMARY_FILE).read_text(encoding="utf-8"))
    expenses = summary.get("expenses", [])
    currency_totals: dict[str, float] = {}
    for expense in expenses:
        currency = expense.get("currency", "PKR")
        currency_totals[currency] = currency_totals.get(currency, 0.0) + float(expense.get("amount", 0))
    friends = summary.get("friends", [participant.get("name", "") for participant in summary.get("participants", [])])
    return {
        "name": summary["trip_name"],
        "ended_at": summary.get("updated_at", ""),
        "friends": friends,
        "expenses": expenses,
        "total": sum(currency_totals.values()),
        "share": sum(currency_totals.values()) / len(friends) if friends else 0,
        "currency_totals": currency_totals,
        "category_currency_totals": summary.get("category_currency_totals", {}),
        "categories": summary.get("categories", {}),
        "people": [
            {"name": name, **values}
            for name, values in summary.get("people", summary.get("participants", {})).items()
        ],
        "settlements": summary.get("settlements", []),
    }


def state_payload() -> dict[str, Any]:
    if not trip.friends:
        return {
            "trip_name": "",
            "friends": [],
            "expenses": [],
            "total": 0.0,
            "share": 0.0,
            "categories": {category: 0.0 for category in EXPENSE_CATEGORIES},
            "currency_totals": {},
            "category_currency_totals": {category: {} for category in EXPENSE_CATEGORIES},
            "people": [],
            "settlements": [],
            "archives": archived_trips(),
        }

    currency_balances = trip.currency_balances()
    currency_paid = trip.currency_paid_totals()
    return {
        "trip_name": trip_name,
        "friends": trip.friends,
        "expenses": [
            {
                "description": expense.description,
                "amount": expense.amount,
                "paid_by": expense.paid_by,
                "category": expense.category,
                "currency": expense.currency,
                "currency_description": expense.currency_description,
                "split_method": expense.split_method,
            }
            for expense in reversed(trip.expenses)
        ],
        "total": trip.total_spent(),
        "share": trip.total_spent() / len(trip.friends),
        "categories": trip.category_totals(),
        "currency_totals": trip.currency_totals(),
        "category_currency_totals": trip.category_currency_totals(),
        "people": [
            {"name": friend, "currencies": {
                currency: {"paid": currency_paid[currency][friend], "balance": currency_balances[currency][friend]}
                for currency in ("USD", "PKR") if currency_paid[currency][friend] or currency_balances[currency][friend]
            }}
            for friend in trip.friends
        ],
        "settlements": [
            {"from": debtor, "to": creditor, "amount": amount, "currency": currency}
            for debtor, creditor, amount, currency in trip.currency_settlements()
        ],
        "archives": archived_trips(),

    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def safe_trip_folder_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", name).strip(" .")
    return re.sub(r"\s+", " ", cleaned) or "Untitled Trip"


def current_trip_document(status: str) -> dict[str, Any]:
    metadata = trip.metadata() or {}
    now = datetime.now().isoformat(timespec="seconds")
    current_trip_name = metadata.get("trip_name", trip_name) or "Untitled trip"
    created_at = metadata.get("created_at", now)
    currency_paid = trip.currency_paid_totals()
    currency_balances = trip.currency_balances()
    currency_totals = trip.currency_totals()
    return {
        "trip_name": current_trip_name,
        "status": status,
        "friends": trip.friends,
        "expenses": [
            {
                "description": expense.description,
                "category": expense.category,
                "paid_by": expense.paid_by,
                "amount": expense.amount,
                "currency": expense.currency,
                "currency_description": expense.currency_description,
                "split_method": expense.split_method,
            }
            for expense in trip.expenses
        ],
        "financial_summary": {
            "expense_count": len(trip.expenses),
            "currency_totals": currency_totals,
        },
        "categories": trip.category_currency_totals(),
        "currency_totals": currency_totals,
        "category_currency_totals": trip.category_currency_totals(),
        "people": {
            friend: {
                "currencies": {
                    currency: {
                        "paid": currency_paid[currency][friend],
                        "share": currency_totals.get(currency, 0) / len(trip.friends),
                        "balance": currency_balances[currency][friend],
                        "status": "Receives" if currency_balances[currency][friend] > 0.005 else "Owes" if currency_balances[currency][friend] < -0.005 else "Settled",
                    }
                    for currency in ("USD", "PKR") if currency_paid[currency][friend] or currency_balances[currency][friend]
                },
            }
            for friend in trip.friends
        },
        "settlements": [
            {
                "from": debtor,
                "to": creditor,
                "amount": amount,
                "currency": currency,
            }
            for debtor, creditor, amount, currency in trip.currency_settlements()
        ],
        "created_at": created_at,
        "updated_at": now,
    }


def trip_folder_for_current_trip() -> Path:
    current_name = (trip.metadata() or {}).get("trip_name", trip_name)
    ARCHIVE_DIR.mkdir(exist_ok=True)
    for folder in ARCHIVE_DIR.iterdir():
        summary_file = folder / TRIP_SUMMARY_FILE
        if folder.is_dir() and summary_file.is_file():
            try:
                if json.loads(summary_file.read_text(encoding="utf-8")).get("trip_name") == current_name:
                    return folder
            except json.JSONDecodeError:
                continue
    folder = ARCHIVE_DIR / safe_trip_folder_name(current_name)
    return folder


def save_current_trip(status: str = "active") -> Path:
    if not trip.friends:
        raise ValueError("There is no active trip to save.")
    folder = trip_folder_for_current_trip()
    folder.mkdir(exist_ok=True)
    summary = current_trip_document(status)
    with tempfile.TemporaryDirectory(dir=folder.parent) as temporary_dir:
        temporary_folder = Path(temporary_dir)
        write_json_atomic(temporary_folder / TRIP_SUMMARY_FILE, summary)
        for filename in CANONICAL_FILES:
            (temporary_folder / filename).replace(folder / filename)
    for path in folder.iterdir():
        if path.name not in CANONICAL_FILES:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    return folder


def archive_current_trip() -> Path:
    folder = save_current_trip("completed")
    return folder / TRIP_SUMMARY_FILE


def excel_cell(value: Any, row: int, column: int) -> str:
    column_name = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        column_name = chr(65 + remainder) + column_name
    cell = f"{column_name}{row}"
    if isinstance(value, (int, float)):
        return f'<c r="{cell}"><v>{value}</v></c>'
    escaped = (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))
    return f'<c r="{cell}" t="inlineStr"><is><t>{escaped}</t></is></c>'


def excel_sheet(rows: list[list[Any]], auto_filter_columns: int = 0) -> str:
    sheet_rows = "".join(
        f'<row r="{row_number}">' + "".join(
            excel_cell(value, row_number, column_number)
            for column_number, value in enumerate(values, 1)
        ) + "</row>"
        for row_number, values in enumerate(rows, 1)
    )
    dimension = max((len(values) for values in rows), default=1)
    last_column = ""
    column_number = dimension
    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        last_column = chr(65 + remainder) + last_column
    auto_filter = ""
    if auto_filter_columns and rows:
        last_filter_column = ""
        column_number = auto_filter_columns
        while column_number:
            column_number, remainder = divmod(column_number - 1, 26)
            last_filter_column = chr(65 + remainder) + last_filter_column
        auto_filter = f'<autoFilter ref="A1:{last_filter_column}{len(rows)}"/>'
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="A1:{last_column}{len(rows)}"/>'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'{auto_filter}<sheetData>{sheet_rows}</sheetData></worksheet>'
    )


def write_excel_workbook(workbook_path: Path) -> None:
    paid = trip.paid_totals()
    balances = trip.balances()
    total = trip.total_spent()
    share = total / len(trip.friends)
    summary_rows = [
        ["Trip summary", trip_name or "Untitled trip"],
        ["Total expenses", total],
        ["Each person's share", share],
        ["Number of friends", len(trip.friends)],
        ["Number of expenses", len(trip.expenses)],
        ["Currency", (trip.metadata() or {}).get("currency", "PKR")],
        [],
        ["Category", "Total", "Number of expenses", "Percentage of total"],
        *[
            [CATEGORY_LABELS[category], amount, sum(expense.category == category for expense in trip.expenses), amount / total if total else 0]
            for category, amount in trip.category_totals().items()
        ],
    ]
    expense_rows = [["Description", "Category", "Paid By", "Amount", "Split Method"]]
    expense_rows.extend([
        [expense.description, CATEGORY_LABELS[expense.category], expense.paid_by, expense.amount, expense.split_method]
        for expense in trip.expenses
    ])
    balance_rows = [["Participant", "Total Paid", "Total Share", "Balance", "Status"]]
    balance_rows.extend([
        [
            friend,
            paid[friend],
            share,
            balances[friend],
            "Receives" if balances[friend] > 0.005 else "Owes" if balances[friend] < -0.005 else "Settled",
        ]
        for friend in trip.friends
    ])
    settlement_rows = [["Settlement ID", "From", "To", "Amount", "Status", "Date", "Notes"]]
    settlement_rows.extend(
        [f"SET-{index:03d}", debtor, creditor, amount, "Pending", date.today().isoformat(), ""]
        for index, (debtor, creditor, amount) in enumerate(trip.settlements(), 1)
    )
    sheets = [
        ("Expenses", expense_rows, 10),
        ("Participant Balances", balance_rows, 5),
        ("Expense Summary", summary_rows, 0),
        ("Settlements", settlement_rows, 7),
    ]
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + "".join(
            f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>'
            for index, (name, _, _) in enumerate(sheets, 1)
        )
        + "</sheets></workbook>"
    )
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
            for index in range(1, len(sheets) + 1)
        )
        + "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for index in range(1, len(sheets) + 1)
        )
        + "</Types>"
    )
    with ZipFile(workbook_path, "w", ZIP_DEFLATED) as workbook_zip:
        workbook_zip.writestr("[Content_Types].xml", content_types)
        workbook_zip.writestr("_rels/.rels", rels)
        workbook_zip.writestr("xl/workbook.xml", workbook)
        workbook_zip.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for index, (_, rows, filter_columns) in enumerate(sheets, 1):
            workbook_zip.writestr(
                f"xl/worksheets/sheet{index}.xml",
                excel_sheet(rows, filter_columns),
            )


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0"))
    return json.loads(handler.rfile.read(content_length))


class AppHandler(BaseHTTPRequestHandler):
    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self) -> None:
        try:
            if self.path == "/api/state":
                self.send_json(state_payload())
                return
            if self.path.startswith("/api/trips/"):
                folder_name = unquote(self.path.removeprefix("/api/trips/"))
                self.send_json(archived_trip_payload(archive_folder(folder_name)))
                return

            filename = "index.html" if self.path == "/" else self.path.lstrip("/")
            allowed_files = {"index.html": "text/html", "index.js": "text/javascript", "style.css": "text/css"}
            if filename not in allowed_files:
                self.send_json({"error": "Not found"}, 404)
                return

            file_path = ROOT / filename
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", allowed_files[filename])
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as error:
            self.send_json({"error": str(error)}, 500)

    def do_POST(self) -> None:
        global trip, trip_name, trip_id
        try:
            payload = read_json(self)
            if self.path == "/api/setup":
                name = str(payload.get("name", "")).strip()
                friends = [str(friend).strip() for friend in payload.get("friends", [])]
                if not name:
                    raise ValueError("Enter a name for the trip.")
                if not friends or len(set(friends)) != len(friends):
                    raise ValueError("Enter at least one unique friend name.")
                if trip.friends:
                    raise ValueError("This trip has already been set up.")
                trip.close()
                trip = TripExpenses(friends, database_path=str(DATABASE_PATH))
                trip_name = name
                trip_id = uuid.uuid4().hex
                now = datetime.now().isoformat(timespec="seconds")
                trip.set_metadata({
                    "trip_id": trip_id,
                    "trip_name": trip_name,
                    "currency": "PKR",
                    "created_at": now,
                    "updated_at": now,
                    "status": "active",
                })
                save_current_trip()
                self.send_json(state_payload(), 201)
                return

            if self.path == "/api/end-trip":
                archive_current_trip()
                trip.reset()
                trip_name = ""
                trip_id = ""
                self.send_json(state_payload(), 201)
                return

            if self.path == "/api/delete-trip":
                shutil.rmtree(archive_folder(str(payload.get("folder", ""))))
                self.send_json(state_payload(), 200)
                return

            if self.path == "/api/expenses":
                trip.add_expense(
                    str(payload.get("description", "Expense")).strip() or "Expense",
                    float(payload["amount"]),
                    str(payload["paid_by"]),
                    str(payload["category"]),
                    currency=str(payload.get("currency", "PKR")),
                    split_method=str(payload.get("split_method", "Equal")),
                )
                save_current_trip()
                self.send_json(state_payload(), 201)
                return

            if self.path == "/api/edit-expense":
                trip.update_expense(
                    str(payload["expense_id"]),
                    str(payload.get("description", "Expense")).strip() or "Expense",
                    float(payload["amount"]),
                    str(payload["paid_by"]),
                    str(payload["category"]),
                    currency=str(payload.get("currency", "PKR")),
                    split_method=str(payload.get("split_method", "Equal")),
                )
                save_current_trip()
                self.send_json(state_payload(), 200)
                return

            if self.path == "/api/delete-expense":
                trip.delete_expense(str(payload["expense_id"]))
                save_current_trip()
                self.send_json(state_payload(), 200)
                return

            self.send_json({"error": "Not found"}, 404)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)
        except Exception as error:
            self.send_json({"error": str(error)}, 500)

    def log_message(self, format: str, *args: Any) -> None:
        return


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), AppHandler)
    print(f"Trip Expense Manager running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        trip.close()
        server.server_close()