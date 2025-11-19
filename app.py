import os
from datetime import datetime, date
import json
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, make_response

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key")

# --- Simple file-based storage (no external database) ---
DATA_FILE = Path("data.json")


def _load_data():
    if DATA_FILE.exists():
        try:
            with DATA_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # If the file is corrupted, fall back to empty structure
            pass
    return {"store_settings": None, "invoices": [], "invoice_counter": 0, "expenses": []}


_data = _load_data()
# Ensure expenses key exists for older data files
if "expenses" not in _data:
    _data["expenses"] = []


def _save_data() -> None:
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(_data, f, ensure_ascii=False, indent=2)


STORE_SETTINGS_DOC_ID = "default"


def get_store_settings():
    settings = _data.get("store_settings")
    if settings:
        return settings
    # Default values if nothing stored yet
    return {
        "store_name": "R Sanju Store",
        "address": "",
        "phone": "",
        "email": "",
        "logo_url": "",
    }


def save_store_settings(data: dict) -> None:
    _data["store_settings"] = data
    _save_data()


def generate_invoice_number() -> str:
    """Simple incremental invoice number: RS-<year>-0001 style."""
    current = _data.get("invoice_counter", 0)
    new_value = current + 1
    _data["invoice_counter"] = new_value
    _save_data()

    year = datetime.now().year
    return f"RS-{year}-{new_value:04d}"


@app.route("/")
def invoice_list():
    store = get_store_settings()
    invoices = list(_data.get("invoices", []))
    invoices.sort(key=lambda inv: inv.get("created_at", ""), reverse=True)
    return render_template("invoice_list.html", store=store, invoices=invoices)


@app.route("/invoice/new", methods=["GET", "POST"])
def new_invoice():
    store = get_store_settings()

    if request.method == "POST":
        form = request.form
        now = datetime.now()
        created_at = now.strftime("%Y-%m-%d %H:%M:%S")
        invoice_date = form.get("invoice_date") or now.strftime("%Y-%m-%d")
        invoice_number = generate_invoice_number()

        # Line items (arrays)
        descriptions = form.getlist("item_description[]")
        quantities = form.getlist("item_quantity[]")
        unit_prices = form.getlist("item_unit_price[]")

        items = []
        subtotal = 0.0

        for desc, qty_str, price_str in zip(descriptions, quantities, unit_prices):
            if not desc.strip():
                continue
            try:
                qty = float(qty_str or 0)
                price = float(price_str or 0)
            except ValueError:
                qty = 0.0
                price = 0.0
            line_total = qty * price
            subtotal += line_total
            items.append(
                {
                    "description": desc.strip(),
                    "quantity": qty,
                    "unit_price": price,
                    "line_total": line_total,
                }
            )

        try:
            discount = float(form.get("discount") or 0)
        except ValueError:
            discount = 0.0
        try:
            tax = float(form.get("tax") or 0)
        except ValueError:
            tax = 0.0

        total = subtotal - discount + tax

        payment_mode = form.get("payment_mode")
        payment_reference = form.get("payment_reference", "").strip()
        notes = form.get("notes", "").strip()

        customer_name = form.get("customer_name", "").strip()
        customer_phone = form.get("customer_phone", "").strip()
        customer_address = form.get("customer_address", "").strip()
        customer_gstin = form.get("customer_gstin", "").strip()

        invoice_data = {
            "invoice_number": invoice_number,
            "created_at": created_at,
            "invoice_date": invoice_date,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_address": customer_address,
            "customer_gstin": customer_gstin,
            "items": items,
            "subtotal": subtotal,
            "discount": discount,
            "tax": tax,
            "total": total,
            "payment_mode": payment_mode,
            "payment_reference": payment_reference,
            "notes": notes,
        }

        # Generate a simple string id for the invoice
        invoices = _data.setdefault("invoices", [])
        new_id = str(len(invoices) + 1)
        invoice_data["id"] = new_id
        invoices.append(invoice_data)
        _save_data()

        flash("Invoice created successfully.", "success")
        return redirect(url_for("invoice_view", invoice_id=new_id))

    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("new_invoice.html", store=store, today=today)


@app.route("/invoice/<invoice_id>")
def invoice_view(invoice_id: str):
    store = get_store_settings()
    invoices = _data.get("invoices", [])
    invoice = next((inv for inv in invoices if inv.get("id") == invoice_id), None)
    if not invoice:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoice_list"))

    return render_template("invoice_view.html", store=store, invoice=invoice)


@app.route("/invoice/<invoice_id>/download")
def download_invoice(invoice_id: str):
    store = get_store_settings()
    invoices = _data.get("invoices", [])
    invoice = next((inv for inv in invoices if inv.get("id") == invoice_id), None)
    if not invoice:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoice_list"))

    # Render the same invoice view HTML and send it as a downloadable file
    html = render_template("invoice_view.html", store=store, invoice=invoice)
    response = make_response(html)
    filename = f"invoice-{invoice.get('invoice_number', invoice_id)}.html"
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@app.route("/expenses", methods=["GET", "POST"])
def expenses():
    store = get_store_settings()
    if request.method == "POST":
        form = request.form
        d = form.get("date") or datetime.now().strftime("%Y-%m-%d")
        desc = form.get("description", "").strip()
        category = form.get("category", "").strip()
        try:
            amount = float(form.get("amount") or 0)
        except ValueError:
            amount = 0.0

        exp_list = _data.setdefault("expenses", [])
        new_id = str(len(exp_list) + 1)
        exp_list.append(
            {
                "id": new_id,
                "date": d,
                "description": desc,
                "category": category,
                "amount": amount,
            }
        )
        _save_data()
        flash("Expense recorded.", "success")
        return redirect(url_for("expenses"))

    all_expenses = list(_data.get("expenses", []))
    all_expenses.sort(key=lambda e: e.get("date", ""), reverse=True)
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("expenses.html", store=store, expenses=all_expenses, today=today)


@app.route("/reports")
def reports():
    store = get_store_settings()
    invoices = _data.get("invoices", [])
    expenses_data = _data.get("expenses", [])

    today_str = datetime.now().strftime("%Y-%m-%d")
    current_month_str = datetime.now().strftime("%Y-%m")

    period = request.args.get("period") or "daily"
    selected_date = request.args.get("date") or today_str
    selected_month = request.args.get("month") or current_month_str

    if period == "monthly":
        # Use year-month from selected_month
        try:
            year, month = map(int, selected_month.split("-"))
        except ValueError:
            year, month = datetime.now().year, datetime.now().month

        inv_filtered = []
        for inv in invoices:
            inv_date_str = inv.get("invoice_date") or inv.get("created_at", "").split(" ")[0]
            try:
                inv_d = datetime.strptime(inv_date_str, "%Y-%m-%d").date()
            except Exception:
                continue
            if inv_d.year == year and inv_d.month == month:
                inv_filtered.append(inv)

        exp_filtered = []
        for exp in expenses_data:
            exp_date_str = exp.get("date")
            if not exp_date_str:
                continue
            try:
                exp_d = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
            except Exception:
                continue
            if exp_d.year == year and exp_d.month == month:
                exp_filtered.append(exp)

        label = f"{year}-{month:02d} (Monthly)"
    else:
        # Daily report
        try:
            d = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            d = date.today()
            selected_date = d.strftime("%Y-%m-%d")

        inv_filtered = []
        for inv in invoices:
            inv_date_str = inv.get("invoice_date") or inv.get("created_at", "").split(" ")[0]
            try:
                inv_d = datetime.strptime(inv_date_str, "%Y-%m-%d").date()
            except Exception:
                continue
            if inv_d == d:
                inv_filtered.append(inv)

        exp_filtered = [exp for exp in expenses_data if exp.get("date") == selected_date]
        label = f"{selected_date} (Daily)"

    sales_total = sum(float(inv.get("total") or 0) for inv in inv_filtered)
    expenses_total = sum(float(exp.get("amount") or 0) for exp in exp_filtered)
    net_total = sales_total - expenses_total

    invoice_count = len(inv_filtered)
    expense_count = len(exp_filtered)

    # Simple AI-style narrative summary generated automatically in Python
    if invoice_count == 0 and expense_count == 0:
        ai_summary = "No financial activity recorded for this period."
    else:
        trend = "balanced"
        if net_total > 0:
            trend = "profitable"
        elif net_total < 0:
            trend = "loss-making"

        ai_summary = (
            f"AI summary: For {label}, total sales are Rs. {sales_total:.2f} "
            f"across {invoice_count} invoice(s), with expenses of Rs. {expenses_total:.2f}. "
            f"The period is {trend} with a net of Rs. {net_total:.2f}. "
        )
        if expenses_total > 0:
            ai_summary += "Consider reviewing infrastructure and operational costs to optimize profit."
        else:
            ai_summary += "No expenses recorded, so all sales are currently counted as profit."

    report = {
        "label": label,
        "sales_total": sales_total,
        "expenses_total": expenses_total,
        "net_total": net_total,
        "invoice_count": invoice_count,
        "expense_count": expense_count,
        "invoices": inv_filtered,
        "expenses": exp_filtered,
        "ai_summary": ai_summary,
    }

    return render_template(
        "reports.html",
        store=store,
        report=report,
        period=period,
        selected_date=selected_date,
        selected_month=selected_month,
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        data = {
            "store_name": request.form.get("store_name", "").strip(),
            "address": request.form.get("address", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "email": request.form.get("email", "").strip(),
            "logo_url": request.form.get("logo_url", "").strip(),
        }
        save_store_settings(data)
        flash("Store settings saved.", "success")
        return redirect(url_for("settings"))

    store = get_store_settings()
    return render_template("settings.html", store=store)


if __name__ == "__main__":
    # Runs on http://127.0.0.1:5000/ by default
    app.run(debug=True)
