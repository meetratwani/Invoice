"""
Database models for R Sanju Invoice application.
All models support multi-tenant architecture with user_id isolation.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """User model - linked to Firebase authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.String(128), primary_key=True)  # Firebase UID
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    store_settings = db.relationship('StoreSettings', backref='user', uselist=False, cascade='all, delete-orphan')
    invoices = db.relationship('Invoice', backref='user', cascade='all, delete-orphan')
    products = db.relationship('Product', backref='user', cascade='all, delete-orphan')
    expenses = db.relationship('Expense', backref='user', cascade='all, delete-orphan')
    suppliers = db.relationship('Supplier', backref='user', cascade='all, delete-orphan')
    stock_transactions = db.relationship('StockTransaction', backref='user', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email}>'


class StoreSettings(db.Model):
    """Store configuration settings per user."""
    __tablename__ = 'store_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False, unique=True)
    
    store_name = db.Column(db.String(255), nullable=False, default='Managekarlo')
    address = db.Column(db.Text)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(255))
    logo_data = db.Column(db.LargeBinary)  # Store logo as binary
    logo_filename = db.Column(db.String(255))
    logo_mimetype = db.Column(db.String(100))
    
    invoice_counter = db.Column(db.Integer, nullable=False, default=0)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<StoreSettings {self.store_name}>'


class Product(db.Model):
    """Product/inventory item."""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False, index=True)
    
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    sku = db.Column(db.String(100), nullable=False, index=True)
    barcode = db.Column(db.String(100), index=True)
    category = db.Column(db.String(100), index=True)
    brand = db.Column(db.String(100))
    
    unit_price = db.Column(db.Float, nullable=False, default=0.0)
    cost_price = db.Column(db.Float, nullable=False, default=0.0)
    stock_quantity = db.Column(db.Float, nullable=False, default=0.0)
    min_stock_level = db.Column(db.Float, nullable=False, default=0.0)
    
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    invoice_items = db.relationship('InvoiceItem', backref='product', cascade='all, delete-orphan')
    stock_transactions = db.relationship('StockTransaction', backref='product', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Product {self.name} ({self.sku})>'


class Supplier(db.Model):
    """Supplier information."""
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False, index=True)
    
    name = db.Column(db.String(255), nullable=False)
    contact_person = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(255))
    address = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', backref='supplier')
    
    def __repr__(self):
        return f'<Supplier {self.name}>'


class Invoice(db.Model):
    """Sales invoice."""
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False, index=True)
    
    invoice_number = db.Column(db.String(50), nullable=False, unique=True, index=True)
    invoice_date = db.Column(db.Date, nullable=False, index=True)
    
    # Customer details
    customer_name = db.Column(db.String(255))
    customer_phone = db.Column(db.String(50), index=True)
    customer_address = db.Column(db.Text)
    customer_gstin = db.Column(db.String(50))
    
    # Amounts
    subtotal = db.Column(db.Float, nullable=False, default=0.0)
    discount = db.Column(db.Float, nullable=False, default=0.0)
    tax = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)
    
    # Payment
    payment_mode = db.Column(db.String(50))  # CASH, CREDIT, UPI, etc.
    payment_reference = db.Column(db.String(255))
    
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan', lazy='joined')
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'


class InvoiceItem(db.Model):
    """Line item in an invoice."""
    __tablename__ = 'invoice_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    
    description = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    line_total = db.Column(db.Float, nullable=False)
    
    def __repr__(self):
        return f'<InvoiceItem {self.description} x{self.quantity}>'


class Expense(db.Model):
    """Business expense tracking."""
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False, index=True)
    
    date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(100), index=True)
    amount = db.Column(db.Float, nullable=False)
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Expense {self.description} - Rs.{self.amount}>'


class StockTransaction(db.Model):
    """Stock movement history."""
    __tablename__ = 'stock_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    
    transaction_type = db.Column(db.String(50), nullable=False)  # sale, purchase, adjustment, return
    quantity = db.Column(db.Float, nullable=False)
    reference_id = db.Column(db.String(100))  # Invoice ID, PO ID, etc.
    notes = db.Column(db.Text)
    
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<StockTransaction {self.transaction_type} {self.quantity}>'
