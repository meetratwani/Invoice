import os
from datetime import datetime, date
import json
from pathlib import Path
import csv
from io import StringIO
from functools import wraps
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, redirect, url_for, flash, make_response, session, send_from_directory
import firebase_admin
from firebase_admin import credentials, auth

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key")

UPLOAD_FOLDER = Path(__file__).parent / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

from firebase_admin import credentials, auth

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key")

# Initialize Firebase Admin SDK
try:
    cred_path = Path("firebase_credentials.json")
    if cred_path.exists() and cred_path.stat().st_size > 10:  # Check if file has content
        cred = credentials.Certificate(str(cred_path))
        firebase_admin.initialize_app(cred)
        FIREBASE_ENABLED = True
        print("✓ Firebase initialized successfully")
    else:
        FIREBASE_ENABLED = False
        print("⚠ Firebase credentials not found - running in local mode")
except Exception as e:
    FIREBASE_ENABLED = False
    print(f"⚠ Firebase initialization failed: {e} - running in local mode")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user_id():
    """Get the current logged-in user's ID from session."""
    return session.get("user_id", "default_user")

DATA_FILE = Path("data.json")

def _load_data():
    if DATA_FILE.exists():
        try:
            with DATA_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                # Migrate old structure to new multi-user structure
                if "users" not in data:
                    print("📦 Migrating data to multi-user structure...")
                    default_user_id = "default_user"
                    data["users"] = {
                        default_user_id: {
                            "store_settings": data.get("store_settings"),
                            "invoices": data.get("invoices", []),
                            "products": data.get("products", []),
                            "expenses": data.get("expenses", []),
                            "suppliers": data.get("suppliers", []),
                            "stock_transactions": data.get("stock_transactions", []),
                            "purchase_orders": data.get("purchase_orders", []),
                            "invoice_counter": data.get("invoice_counter", 0)
                        }
                    }
                    # Remove old keys
                    for key in ['store_settings', 'invoices', 'products', 'expenses', 
                                'suppliers', 'stock_transactions', 'purchase_orders', 'invoice_counter']:
                        data.pop(key, None)
                    print("✓ Migration complete")
                return data
        except Exception as e:
            print(f"Error loading data: {e}")
            pass
    return {"users": {}}

_data = _load_data()

def _save_data() -> None:
    """Save data to JSON file."""
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(_data, f, ensure_ascii=False, indent=2)

def _get_user_data(user_id: str = None) -> dict:
    """Get or create user data structure for a specific user."""
    if user_id is None:
        user_id = get_current_user_id()
    
    if user_id not in _data["users"]:
        _data["users"][user_id] = {
            "store_settings": None,
            "invoices": [],
            "products": [],
            "expenses": [],
            "suppliers": [],
            "stock_transactions": [],
            "purchase_orders": [],
            "invoice_counter": 0
        }
        _save_data()
    
    return _data["users"][user_id]


# ---------- Inventory / product helpers ----------

def _next_id(prefix: str, seq: list[dict]) -> str:
    """Generate a simple incremental string id like 'p1', 'p2' based on list length.

    This keeps things stable enough for a JSON-file-based app.
    """
    return f"{prefix}{len(seq) + 1}"


def get_products() -> list[dict]:
    user_data = _get_user_data()
    return user_data.setdefault("products", [])


def find_product(product_id: str) -> dict | None:
    for p in get_products():
        if p.get("id") == product_id:
            return p
    return None


def create_product(data: dict) -> dict:
    products = get_products()
    new_id = _next_id("p", products)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sku = data.get("sku", "").strip() or f"SKU-{new_id}"
    barcode = data.get("barcode", "").strip() or sku

    product = {
        "id": new_id,
        "name": data.get("name", "").strip(),
        "description": data.get("description", "").strip(),
        "sku": sku,
        "barcode": barcode,
        "category": data.get("category", "").strip(),
        "brand": data.get("brand", "").strip(),
        "unit_price": float(data.get("unit_price") or 0),
        "cost_price": float(data.get("cost_price") or 0),
        "stock_quantity": float(data.get("stock_quantity") or 0),
        "min_stock_level": float(data.get("min_stock_level") or 0),
        "supplier_id": data.get("supplier_id") or None,
        "created_at": now,
        "updated_at": now,
    }
    products.append(product)
    _save_data()
    return product


def update_product(product: dict, data: dict) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Keep existing codes if user leaves them empty.
    sku = (data.get("sku", "") or "").strip() or (product.get("sku") or "").strip() or f"SKU-{product.get('id')}"
    barcode_in = (data.get("barcode", "") or "").strip()
    barcode = barcode_in or (product.get("barcode") or "").strip() or sku

    product.update(
        {
            "name": data.get("name", "").strip(),
            "description": data.get("description", "").strip(),
            "sku": sku,
            "barcode": barcode,
            "category": data.get("category", "").strip(),
            "brand": data.get("brand", "").strip(),
            "unit_price": float(data.get("unit_price") or 0),
            "cost_price": float(data.get("cost_price") or 0),
            "stock_quantity": float(data.get("stock_quantity") or 0),
            "min_stock_level": float(data.get("min_stock_level") or 0),
            "supplier_id": data.get("supplier_id") or None,
            "updated_at": now,
        }
    )
    _save_data()


def record_stock_transaction(product_id: str, tx_type: str, quantity: float, reference_id: str = "", notes: str = "") -> None:
    user_data = _get_user_data()
    tx_list = user_data.setdefault("stock_transactions", [])
    new_id = _next_id("t", tx_list)
    tx_list.append(
        {
            "id": new_id,
            "product_id": product_id,
            "transaction_type": tx_type,
            "quantity": float(quantity or 0),
            "reference_id": reference_id,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "notes": notes,
        }
    )


def adjust_stock(product_id: str, delta: float, tx_type: str, reference_id: str = "", notes: str = "") -> None:
    product = find_product(product_id)
    if not product:
        return
    current = float(product.get("stock_quantity") or 0)
    product["stock_quantity"] = current + float(delta or 0)
    record_stock_transaction(product_id, tx_type, delta, reference_id, notes)
    _save_data()


STORE_SETTINGS_DOC_ID = "default"


def get_store_settings():
    user_data = _get_user_data()
    settings = user_data.get("store_settings")
    if settings:
        return settings

    return {
        "store_name": "R Sanju Store",
        "address": "",
        "phone": "",
        "email": "",
        "logo_url": "",
    }


def save_store_settings(data: dict) -> None:
    user_data = _get_user_data()
    user_data["store_settings"] = data
    _save_data()


def generate_invoice_number() -> str:
    """Simple incremental invoice number: RS-<year>-0001 style."""
    user_data = _get_user_data()
    current = user_data.get("invoice_counter", 0)
    new_value = current + 1
    user_data["invoice_counter"] = new_value
    _save_data()

    year = datetime.now().year
    return f"RS-{year}-{new_value:04d}"


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Check if Firebase token is provided (from client-side Firebase auth)
        id_token = request.form.get("id_token")
        
        if id_token and FIREBASE_ENABLED:
            try:
                # Verify the Firebase ID token
                decoded_token = auth.verify_id_token(id_token)
                user_id = decoded_token['uid']
                session["logged_in"] = True
                session["user_id"] = user_id
                session["email"] = decoded_token.get('email', '')
                
                next_url = request.args.get("next") or url_for("invoice_list")
                return redirect(next_url)
            except Exception as e:
                print(f"Firebase auth error: {e}")
                flash("Authentication failed. Please try again.", "error")
        else:
            # Fallback only if configured securely (optional), but for now reject
            if not FIREBASE_ENABLED:
                flash("Firebase not configured. Secure login required.", "error")
            else:
                flash("Invalid authentication method.", "error")
            
            # Remove insecure "accept all" logic
            # session["logged_in"] = True ... -> REMOVED
            pass
            
            # Return to login page logic (return redirect(url_for('login')) effectively via fallthrough or explicit)
            # Actually the function continues... allow fallthrough to render template?
            # No, if POST, we should return or redirect.
            
            return redirect(url_for("login"))


    # Get store settings without requiring login
    try:
        # Try to get default user's store settings for branding
        if "users" in _data and _data["users"]:
            first_user = list(_data["users"].values())[0]
            store = first_user.get("store_settings") or {
                "store_name": "R Sanju Store",
                "address": "",
                "phone": "",
                "email": "",
                "logo_url": "",
            }
        else:
            store = {
                "store_name": "R Sanju Store",
                "address": "",
                "phone": "",
                "email": "",
                "logo_url": "",
            }
    except:
        store = {"store_name": "R Sanju Store", "address": "", "phone": "", "email": "", "logo_url": ""}
    
    return render_template("login.html", store=store, firebase_enabled=FIREBASE_ENABLED)


@app.route("/logout")
def logout():
    email = session.get("email", "User")
    session.clear()
    flash(f"You have been logged out.", "info")
    return redirect(url_for("login"))





@app.route("/")
@login_required
def invoice_list():
    store = get_store_settings()

    
    search_phone = (request.args.get("phone") or "").strip()
    search_date = (request.args.get("date") or "").strip()

    invoices = list(_get_user_data().get("invoices", []))
    invoices.sort(key=lambda inv: inv.get("created_at", ""), reverse=True)

   
    phone_filter = search_phone
    if phone_filter:
        invoices = [
            inv
            for inv in invoices
            if phone_filter in (inv.get("customer_phone") or "")
        ]

    
    if search_date:
        def _get_invoice_date(inv):
            inv_date_str = inv.get("invoice_date") or inv.get("created_at", "").split(" ")[0]
            return inv_date_str

        invoices = [inv for inv in invoices if _get_invoice_date(inv) == search_date]

    return render_template(
        "invoice_list.html",
        store=store,
        invoices=invoices,
        search_phone=search_phone,
        search_date=search_date,
    )


@app.route("/invoices/export")
@login_required
def export_invoices():
    """Export all invoices as a CSV file that opens in Excel."""
    invoices = list(_get_user_data().get("invoices", []))
    invoices.sort(key=lambda inv: inv.get("created_at", ""), reverse=True)

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Invoice #", "Date & time", "Invoice date", "Customer", "Phone", "Total", "Payment mode"])
    for inv in invoices:
        writer.writerow([
            inv.get("invoice_number", ""),
            inv.get("created_at", ""),
            inv.get("invoice_date", ""),
            inv.get("customer_name") or "-",
            inv.get("customer_phone") or "-",
            f"{float(inv.get('total') or 0):.2f}",
            inv.get("payment_mode") or "-",
        ])

    csv_data = output.getvalue()
    output.close()

    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=invoices-all.csv"
    return response


@app.route("/invoice/new", methods=["GET", "POST"])
@login_required
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
        product_ids = form.getlist("item_product_id[]")

        items = []
        subtotal = 0.0

        for desc, qty_str, price_str, product_id in zip(descriptions, quantities, unit_prices, product_ids):
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
            item_data = {
                "description": desc.strip(),
                "quantity": qty,
                "unit_price": price,
                "line_total": line_total,
            }
            if product_id:
                item_data["product_id"] = product_id
            items.append(item_data)

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

        invoices = _get_user_data().setdefault("invoices", [])
        new_id = str(len(invoices) + 1)
        invoice_data["id"] = new_id
        invoices.append(invoice_data)

        # Adjust stock for any items linked to products
        for item in items:
            product_id = item.get("product_id")
            if not product_id:
                continue
            qty = float(item.get("quantity") or 0)
            if qty <= 0:
                continue
            adjust_stock(product_id, -qty, "sale", reference_id=new_id, notes=f"Invoice {invoice_number}")

        _save_data()

        flash("Invoice created successfully.", "success")
        return redirect(url_for("invoice_view", invoice_id=new_id))

    today = datetime.now().strftime("%Y-%m-%d")
    products = get_products()
    return render_template("new_invoice.html", store=store, today=today, products=products)


@app.route("/invoice/<invoice_id>")
@login_required
def invoice_view(invoice_id: str):
    store = get_store_settings()
    invoices = _get_user_data().get("invoices", [])
    invoice = next((inv for inv in invoices if inv.get("id") == invoice_id), None)
    if not invoice:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoice_list"))

    return render_template("invoice_view.html", store=store, invoice=invoice)


@app.route("/invoice/<invoice_id>/delete", methods=["POST"])
@login_required
def delete_invoice(invoice_id: str):
    """Delete a single invoice by id."""
    invoices = _get_user_data().get("invoices", [])
    index_to_remove = None
    for idx, inv in enumerate(invoices):
        if inv.get("id") == invoice_id:
            index_to_remove = idx
            break

    if index_to_remove is None:
        flash("Invoice not found.", "error")
    else:
        invoices.pop(index_to_remove)
        _save_data()
        flash("Invoice deleted successfully.", "success")

    return redirect(url_for("invoice_list"))


@app.route("/invoice/<invoice_id>/convert-credit-to-cash", methods=["POST"])
@login_required
def convert_credit_to_cash(invoice_id: str):
    """Convert an invoice payment mode from CREDIT to CASH."""
    invoices = _get_user_data().get("invoices", [])
    invoice = next((inv for inv in invoices if inv.get("id") == invoice_id), None)
    if not invoice:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoice_list"))

    if (invoice.get("payment_mode") or "").upper() != "CREDIT":
        flash("Invoice is not in CREDIT payment mode.", "error")
        return redirect(url_for("invoice_view", invoice_id=invoice_id))

    invoice["payment_mode"] = "CASH"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing_notes = (invoice.get("notes") or "").strip()
    conversion_note = f"[Converted from CREDIT to CASH on {timestamp}]"
    if existing_notes:
        invoice["notes"] = existing_notes + "\n" + conversion_note
    else:
        invoice["notes"] = conversion_note

    _save_data()
    flash("Invoice payment changed from CREDIT to CASH.", "success")

    return redirect(url_for("invoice_view", invoice_id=invoice_id))


@app.route("/invoice/<invoice_id>/download")
@login_required
def download_invoice(invoice_id: str):
    store = get_store_settings()
    invoices = _get_user_data().get("invoices", [])
    invoice = next((inv for inv in invoices if inv.get("id") == invoice_id), None)
    if not invoice:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoice_list"))

   
    html = render_template("invoice_view.html", store=store, invoice=invoice)
    response = make_response(html)
    filename = f"invoice-{invoice.get('invoice_number', invoice_id)}.html"
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@app.route("/expenses", methods=["GET", "POST"])
@login_required
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

        exp_list = _get_user_data().setdefault("expenses", [])
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

    all_expenses = list(_get_user_data().get("expenses", []))
    all_expenses.sort(key=lambda e: e.get("date", ""), reverse=True)
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("expenses.html", store=store, expenses=all_expenses, today=today)


@app.route("/expenses/export")
@login_required
def export_expenses():
    """Export all expenses as a CSV file that opens in Excel."""
    all_expenses = list(_get_user_data().get("expenses", []))
    all_expenses.sort(key=lambda e: e.get("date", ""), reverse=True)

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Date", "Description", "Category", "Amount"])
    for exp in all_expenses:
        writer.writerow([
            exp.get("date", ""),
            exp.get("description", ""),
            exp.get("category") or "-",
            f"{float(exp.get('amount') or 0):.2f}",
        ])

    csv_data = output.getvalue()
    output.close()

    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=expenses-all.csv"
    return response


@app.route("/reports")
@login_required
def reports():
    store = get_store_settings()
    invoices = _get_user_data().get("invoices", [])
    expenses_data = _get_user_data().get("expenses", [])

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


@app.route("/reports/export")
@login_required
def export_report():
    """Export the current report (same filters) as a CSV file that opens in Excel."""
    invoices = _get_user_data().get("invoices", [])
    expenses_data = _get_user_data().get("expenses", [])

    today_str = datetime.now().strftime("%Y-%m-%d")
    current_month_str = datetime.now().strftime("%Y-%m")

    period = request.args.get("period") or "daily"
    selected_date = request.args.get("date") or today_str
    selected_month = request.args.get("month") or current_month_str

    if period == "monthly":
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

    output = StringIO()
    writer = csv.writer(output)

    # Summary section
    writer.writerow(["Report", label])
    writer.writerow(["Total sales", f"{sales_total:.2f}"])
    writer.writerow(["Total expenses", f"{expenses_total:.2f}"])
    writer.writerow(["Net (sales - expenses)", f"{net_total:.2f}"])
    writer.writerow([])

    # Invoices section
    writer.writerow(["Invoices"])
    writer.writerow(["Invoice #", "Date", "Customer", "Total", "Payment mode"])
    for inv in inv_filtered:
        writer.writerow([
            inv.get("invoice_number", ""),
            inv.get("invoice_date") or (inv.get("created_at", "").split(" ")[0] if inv.get("created_at") else ""),
            inv.get("customer_name") or "-",
            f"{float(inv.get('total') or 0):.2f}",
            inv.get("payment_mode") or "-",
        ])

    writer.writerow([])

    # Expenses section
    writer.writerow(["Expenses"])
    writer.writerow(["Date", "Description", "Category", "Amount"])
    for exp in exp_filtered:
        writer.writerow([
            exp.get("date", ""),
            exp.get("description", ""),
            exp.get("category") or "-",
            f"{float(exp.get('amount') or 0):.2f}",
        ])

    csv_data = output.getvalue()
    output.close()

    filename_period = selected_month if period == "monthly" else selected_date
    filename = f"report-{period}-{filename_period}.csv"

    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        data = {
            "store_name": request.form.get("store_name", "").strip(),
            "address": request.form.get("address", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "email": request.form.get("email", "").strip(),
            "logo_url": request.form.get("logo_url", "").strip(),
        }
        
        if "logo_file" in request.files:
            file = request.files["logo_file"]
            if file and file.filename:
                filename = secure_filename(f"logo_{int(datetime.now().timestamp())}_{file.filename}")
                file.save(UPLOAD_FOLDER / filename)
                data["logo_url"] = url_for("uploaded_file", filename=filename)
        
        save_store_settings(data)
        flash("Store settings saved.", "success")
        return redirect(url_for("settings"))

    store = get_store_settings()
    return render_template("settings.html", store=store)


# ---------- Product management ----------

@app.route("/products")
@login_required
def products_list():
    store = get_store_settings()
    products = list(get_products())

    # Simple search/filter by name, sku, or barcode
    q = (request.args.get("q") or "").strip().lower()
    stock_status = (request.args.get("stock_status") or "").strip()

    def _is_low_stock(p: dict) -> bool:
        try:
            qty = float(p.get("stock_quantity") or 0)
            min_lvl = float(p.get("min_stock_level") or 0)
        except Exception:
            return False
        return qty <= min_lvl

    if q:
        filtered = []
        for p in products:
            text = " ".join(
                [
                    str(p.get("name") or ""),
                    str(p.get("sku") or ""),
                    str(p.get("barcode") or ""),
                ]
            ).lower()
            if q in text:
                filtered.append(p)
        products = filtered

    if stock_status == "low":
        products = [p for p in products if _is_low_stock(p)]
    elif stock_status == "in_stock":
        products = [p for p in products if float(p.get("stock_quantity") or 0) > 0]

    # Sort by name
    products.sort(key=lambda p: (p.get("name") or "").lower())

    return render_template("products_list.html", store=store, products=products)


@app.route("/products/new", methods=["GET", "POST"])
@login_required
def product_new():
    store = get_store_settings()
    if request.method == "POST":
        try:
            create_product(request.form)
            flash("Product created.", "success")
            return redirect(url_for("products_list"))
        except Exception as e:
            flash(f"Failed to create product: {e}", "error")

    return render_template("product_form.html", store=store, product=None)


@app.route("/products/<product_id>/edit", methods=["GET", "POST"])
@login_required
def product_edit(product_id: str):
    store = get_store_settings()
    product = find_product(product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("products_list"))

    if request.method == "POST":
        try:
            update_product(product, request.form)
            flash("Product updated.", "success")
            return redirect(url_for("products_list"))
        except Exception as e:
            flash(f"Failed to update product: {e}", "error")

    return render_template("product_form.html", store=store, product=product)


@app.route("/products/<product_id>/barcode")
@login_required
def product_barcode(product_id: str):
    store = get_store_settings()
    product = find_product(product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("products_list"))
    return render_template("product_barcode.html", store=store, product=product)


@app.route("/products/<product_id>/delete", methods=["POST"])
@login_required
def product_delete(product_id: str):
    products = get_products()
    index_to_remove = None
    for idx, p in enumerate(products):
        if p.get("id") == product_id:
            index_to_remove = idx
            break

    if index_to_remove is None:
        flash("Product not found.", "error")
    else:
        products.pop(index_to_remove)
        _save_data()
        flash("Product deleted.", "success")

    return redirect(url_for("products_list"))


# ---------- Inventory dashboard ----------

@app.route("/inventory")
@login_required
def inventory_dashboard():
    store = get_store_settings()
    products = list(get_products())

    total_products = len(products)
    total_stock_qty = 0.0
    total_stock_value_selling = 0.0
    total_stock_value_cost = 0.0
    low_stock_products = []

    for p in products:
        try:
            qty = float(p.get("stock_quantity") or 0)
            unit_price = float(p.get("unit_price") or 0)
            cost_price = float(p.get("cost_price") or 0)
            min_lvl = float(p.get("min_stock_level") or 0)
        except Exception:
            continue

        total_stock_qty += qty
        total_stock_value_selling += qty * unit_price
        total_stock_value_cost += qty * cost_price

        if qty <= min_lvl:
            low_stock_products.append(p)

    recent_txs = list(_get_user_data().get("stock_transactions", []))[-20:]
    recent_txs.reverse()

    summary = {
        "total_products": total_products,
        "total_stock_qty": total_stock_qty,
        "total_stock_value_selling": total_stock_value_selling,
        "total_stock_value_cost": total_stock_value_cost,
        "low_stock_products": low_stock_products,
        "recent_transactions": recent_txs,
    }

    return render_template("inventory_dashboard.html", store=store, summary=summary)


if __name__ == "__main__":
    # Runs on http://127.0.0.1:5000/ by default
    app.run(debug=True, host="0.0.0.0", port=5000)
