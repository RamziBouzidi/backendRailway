import sqlite3
import os
from sqlalchemy import create_engine, inspect
from Tunnel.database import SQLACHEMY_DATABASE_URL
from Tunnel import models

def migrate_sqlite_database():
    """Add missing columns to the Users table if they don't exist."""
    try:
        # Create an SQLAlchemy engine to inspect the database
        engine = create_engine(SQLACHEMY_DATABASE_URL)
        inspector = inspect(engine)
        
        # Connect directly to SQLite for making alterations
        conn = sqlite3.connect("./tunnel.db")
        cursor = conn.cursor()
        
        # Get existing columns in the Users table
        existing_columns = [column['name'] for column in inspector.get_columns("Users")]
        print(f"Existing columns: {existing_columns}")
        
        # Add surname column if it doesn't exist
        if "surname" not in existing_columns:
            cursor.execute("ALTER TABLE Users ADD COLUMN surname TEXT")
            print("Added surname column")
            
        # Add phone_number column if it doesn't exist
        if "phone_number" not in existing_columns:
            cursor.execute("ALTER TABLE Users ADD COLUMN phone_number INTEGER")
            print("Added phone_number column")
        
        # Commit the changes
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        # Close the connection
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_sqlite_database()