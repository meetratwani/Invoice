"""
Migration script to convert data from data.json to database.
Run this script AFTER initializing the database to import existing data.
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask
from models import db, User, StoreSettings, Product, Supplier, Invoice, InvoiceItem, Expense, StockTransaction
from config import config


def migrate_data(json_file='data.json', app_config='default'):
    """
    Migrate data from JSON file to database.
    
    Args:
        json_file: Path to the data.json file
        app_config: Configuration to use
    """
    json_path = Path(json_file)
    
    if not json_path.exists():
        print(f"❌ JSON file not found: {json_file}")
        print("   If you don't have existing data to migrate, you can skip this step.")
        return False
    
    print(f"Reading data from {json_file}...")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Failed to read JSON file: {e}")
        return False
    
    # Initialize Flask app
    app = Flask(__name__)
    app.config.from_object(config[app_config])
    db.init_app(app)
    
    with app.app_context():
        print("\n" + "=" * 60)
        print("Starting migration...")
        print("=" * 60)
        
        # Check if data has new structure (with users key) or old structure
        if "users" in data:
            users_data = data["users"]
        else:
            # Old structure - wrap in default user
            users_data = {
                "default_user": data
            }
        
        total_migrated = {
            "users": 0,
            "store_settings": 0,
            "products": 0,
            "invoices": 0,
            "invoice_items": 0,
            "expenses": 0,
            "stock_transactions": 0,
        }
        
        for user_id, user_data in users_data.items():
            print(f"\n📦 Migrating data for user: {user_id}")
            
            # Create user if doesn't exist
            user = User.query.get(user_id)
            if not user:
                user = User(id=user_id, email=f"{user_id}@imported.local")
                db.session.add(user)
                total_migrated["users"] += 1
                print(f"  ✓ Created user: {user_id}")
            
            # Migrate store settings
            if user_data.get("store_settings"):
                settings_data = user_data["store_settings"]
                settings = StoreSettings.query.filter_by(user_id=user_id).first()
                
                if not settings:
                    settings = StoreSettings(
                        user_id=user_id,
                        store_name=settings_data.get("store_name", "Managekarlo"),
                        address=settings_data.get("address", ""),
                        phone=settings_data.get("phone", ""),
                        email=settings_data.get("email", ""),
                        invoice_counter=user_data.get("invoice_counter", 0),
                    )
                    db.session.add(settings)
                    total_migrated["store_settings"] += 1
                    print(f"  ✓ Migrated store settings")
            
            # Migrate products
            products_map = {}  # Map old string IDs to new integer IDs
            for old_product in user_data.get("products", []):
                old_id = old_product.get("id")
                
                product = Product(
                    user_id=user_id,
                    name=old_product.get("name", ""),
                    description=old_product.get("description", ""),
                    sku=old_product.get("sku", ""),
                    barcode=old_product.get("barcode", ""),
                    category=old_product.get("category", ""),
                    brand=old_product.get("brand", ""),
                    unit_price=float(old_product.get("unit_price", 0)),
                    cost_price=float(old_product.get("cost_price", 0)),
                    stock_quantity=float(old_product.get("stock_quantity", 0)),
                    min_stock_level=float(old_product.get("min_stock_level", 0)),
                )
                
                db.session.add(product)
                db.session.flush()  # Get product.id
                products_map[old_id] = product.id
                total_migrated["products"] += 1
            
            if products_map:
                print(f"  ✓ Migrated {len(products_map)} products")
            
            # Migrate invoices
            invoices_map = {}  # Map old string IDs to new integer IDs
            for old_invoice in user_data.get("invoices", []):
                old_id = old_invoice.get("id")
                
                # Parse invoice date
                invoice_date_str = old_invoice.get("invoice_date") or old_invoice.get("created_at", "").split(" ")[0]
                try:
                    invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d").date()
                except:
                    invoice_date = datetime.now().date()
                
                # Parse created_at
                created_at_str = old_invoice.get("created_at", "")
                try:
                    created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
                except:
                    created_at = datetime.now()
                
                invoice = Invoice(
                    user_id=user_id,
                    invoice_number=old_invoice.get("invoice_number", ""),
                    invoice_date=invoice_date,
                    customer_name=old_invoice.get("customer_name", ""),
                    customer_phone=old_invoice.get("customer_phone", ""),
                    customer_address=old_invoice.get("customer_address", ""),
                    customer_gstin=old_invoice.get("customer_gstin", ""),
                    subtotal=float(old_invoice.get("subtotal", 0)),
                    discount=float(old_invoice.get("discount", 0)),
                    tax=float(old_invoice.get("tax", 0)),
                    total=float(old_invoice.get("total", 0)),
                    payment_mode=old_invoice.get("payment_mode", ""),
                    payment_reference=old_invoice.get("payment_reference", ""),
                    notes=old_invoice.get("notes", ""),
                    created_at=created_at,
                )
                
                db.session.add(invoice)
                db.session.flush()  # Get invoice.id
                invoices_map[old_id] = invoice.id
                
                # Migrate invoice items
                for old_item in old_invoice.get("items", []):
                    old_product_id = old_item.get("product_id")
                    new_product_id = products_map.get(old_product_id) if old_product_id else None
                    
                    item = InvoiceItem(
                        invoice_id=invoice.id,
                        product_id=new_product_id,
                        description=old_item.get("description", ""),
                        quantity=float(old_item.get("quantity", 0)),
                        unit_price=float(old_item.get("unit_price", 0)),
                        line_total=float(old_item.get("line_total", 0)),
                    )
                    
                    db.session.add(item)
                    total_migrated["invoice_items"] += 1
                
                total_migrated["invoices"] += 1
            
            if invoices_map:
                print(f"  ✓ Migrated {len(invoices_map)} invoices with {total_migrated['invoice_items']} items")
            
            # Migrate expenses
            for old_expense in user_data.get("expenses", []):
                expense_date_str = old_expense.get("date", "")
                try:
                    expense_date = datetime.strptime(expense_date_str, "%Y-%m-%d").date()
                except:
                    expense_date = datetime.now().date()
                
                expense = Expense(
                    user_id=user_id,
                    date=expense_date,
                    description=old_expense.get("description", ""),
                    category=old_expense.get("category", ""),
                    amount=float(old_expense.get("amount", 0)),
                )
                
                db.session.add(expense)
                total_migrated["expenses"] += 1
            
            if total_migrated["expenses"] > 0:
                print(f"  ✓ Migrated {total_migrated['expenses']} expenses")
            
            # Migrate stock transactions
            for old_tx in user_data.get("stock_transactions", []):
                old_product_id = old_tx.get("product_id")
                new_product_id = products_map.get(old_product_id) if old_product_id else None
                
                if not new_product_id:
                    continue  # Skip if product not found
                
                tx_date_str = old_tx.get("date", "")
                try:
                    tx_date = datetime.strptime(tx_date_str, "%Y-%m-%d %H:%M:%S")
                except:
                    tx_date = datetime.now()
                
                transaction = StockTransaction(
                    user_id=user_id,
                    product_id=new_product_id,
                    transaction_type=old_tx.get("transaction_type", ""),
                    quantity=float(old_tx.get("quantity", 0)),
                    reference_id=old_tx.get("reference_id", ""),
                    notes=old_tx.get("notes", ""),
                    date=tx_date,
                )
                
                db.session.add(transaction)
                total_migrated["stock_transactions"] += 1
            
            if total_migrated["stock_transactions"] > 0:
                print(f"  ✓ Migrated {total_migrated['stock_transactions']} stock transactions")
        
        # Commit all changes
        try:
            db.session.commit()
            print("\n" + "=" * 60)
            print("✅ Migration completed successfully!")
            print("=" * 60)
            print(f"Migrated:")
            print(f"  - {total_migrated['users']} users")
            print(f"  - {total_migrated['store_settings']} store settings")
            print(f"  - {total_migrated['products']} products")
            print(f"  - {total_migrated['invoices']} invoices")
            print(f"  - {total_migrated['invoice_items']} invoice items")
            print(f"  - {total_migrated['expenses']} expenses")
            print(f"  - {total_migrated['stock_transactions']} stock transactions")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error committing changes: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    env = os.environ.get('FLASK_ENV', 'development')
    
    print("=" * 60)
    print("R Sanju Invoice - Data Migration from JSON to Database")
    print("=" * 60)
    print(f"Environment: {env}")
    print()
    
    # Check if database is initialized
    print("⚠️  Make sure you've run 'python init_db.py' first!\n")
    
    try:
        success = migrate_data('data.json', env)
        
        if success:
            print("\n✅ Migration complete!")
            print("\nNext steps:")
            print("  1. Run 'python app.py' to start the application")
            print("  2. (Optional) Backup your data.json file")
        else:
            print("\n❌ Migration failed. Please check errors above.")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
