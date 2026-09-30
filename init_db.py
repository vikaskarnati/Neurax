"""
Standalone database initialization script for NEURAX.
Run this script to initialize all database tables and seed default doctors.

Usage:
    python init_db.py
"""
import sys
from database import create_tables

def main():
    print("Testing database connection and initializing tables...")
    try:
        create_tables()
        print("Success: All database tables and seed data are ready.")
    except Exception as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
