"""
Database initialization script for R Sanju Invoice application.
Run this script to create all database tables.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask
from models import db, User, StoreSettings, Product, Supplier, Invoice, InvoiceItem, Expense, StockTransaction
from config import config

def init_database(app_config='default'):
    """
    Initialize the database by creating all tables.
    
    Args:
        app_config: Configuration to use ('development', 'production', or 'default')
    """
    app = Flask(__name__)
    app.config.from_object(config[app_config])
    
    # Initialize database with app
    db.init_app(app)
    
    with app.app_context():
        print(f"Creating database tables...")
        print(f"Database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        # Create all tables
        db.create_all()
        
        print("✓ All tables created successfully!")
        
        # Display created tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"\nCreated {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")
        
    return True


if __name__ == '__main__':
    # Determine environment
    env = os.environ.get('FLASK_ENV', 'development')
    
    print("=" * 60)
    print("R Sanju Invoice - Database Initialization")
    print("=" * 60)
    print(f"Environment: {env}")
    print()
    
    try:
        init_database(env)
        print("\n✅ Database initialization complete!")
        print("\nNext steps:")
        print("  1. Run 'python app.py' to start the application")
        print("  2. (Optional) Run 'python migrate_json_to_db.py' to import existing data")
    except Exception as e:
        print(f"\n❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
