import mysql.connector
import os

# MySQL database connection parameters
db_config = {
    "host": "localhost",  # or your MySQL server address
    "user": "root",       # your MySQL username
    "password": "",       # your MySQL password
    "database": "tunnel"  # your database name
}

def migrate_database():
    """Add the verification fields to the Users table if they don't exist."""
    try:
        # Connect to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Check if the columns already exist
        cursor.execute("DESCRIBE Users")
        columns = [column[0] for column in cursor.fetchall()]
        
        # Add the columns if they don't exist
        if "is_verified" not in columns:
            cursor.execute("ALTER TABLE Users ADD COLUMN is_verified BOOLEAN DEFAULT 0")
            print("Added is_verified column")
            
        if "verification_code" not in columns:
            cursor.execute("ALTER TABLE Users ADD COLUMN verification_code VARCHAR(255)")
            print("Added verification_code column")
            
        if "code_expiry" not in columns:
            cursor.execute("ALTER TABLE Users ADD COLUMN code_expiry DATETIME")
            print("Added code_expiry column")
            
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
    migrate_database()