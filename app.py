import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash

import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key")

# --- Firebase setup ---
if not firebase_admin._apps:
    # You can either set GOOGLE_APPLICATION_CREDENTIALS to point to your service account JSON,
    # or put the file as "firebase_credentials.json" in the project root.
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "firebase_credentials.json")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

STORE_SETTINGS_DOC_ID = "default"


def get_store_settings():
    doc_ref = db.collection("store_settings").document(STORE_SETTINGS_DOC_ID)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    # Default values if nothing stored yet
    return {
        "store_name": "R Sanju Store",
        "address": "",
        "phone": "",
        "email": "",
        "logo_url": "",
    }


def save_store_settings(data: dict) -> None:
    doc_ref = db.collection("store_settings").document(STORE_SETTINGS_DOC_ID)
    doc_ref.set(data)


def generate_invoice_number() -> str:
    """Simple incremental invoice number: RS-<year>-0001 style."""
    counter_ref = db.collection("metadata").document("invoice_counter")
    counter_doc = counter_ref.get()
    if counter_doc.exists:
        current = counter_doc.to_dict().get("value", 0)
    else:
        current = 0
    new_value = current + 1
    counter_ref.set({"value": new_value})

    year = datetime.now().year
    return f"RS-{year}-{new_value:04d}"


@app.route("/")
def invoice_list():
    store = get_store_settings()
    invoices_query = db.collection("invoices").order_by(
        "created_at", direction=firestore.Query.DESCENDING
    )
    invoices = []
    for doc in invoices_query.stream():
        data = doc.to_dict()
        data["id"] = doc.id
        invoices.append(data)

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

        doc_ref, _ = db.collection("invoices").add(invoice_data)
        flash("Invoice created successfully.", "success")
        return redirect(url_for("invoice_view", invoice_id=doc_ref.id))

    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("new_invoice.html", store=store, today=today)


@app.route("/invoice/<invoice_id>")
def invoice_view(invoice_id: str):
    store = get_store_settings()
    doc_ref = db.collection("invoices").document(invoice_id)
    doc = doc_ref.get()
    if not doc.exists:
        flash("Invoice not found.", "error")
        return redirect(url_for("invoice_list"))

    invoice = doc.to_dict()
    invoice["id"] = doc.id
    return render_template("invoice_view.html", store=store, invoice=invoice)


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
