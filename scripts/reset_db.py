"""
Reset SQL Server tables — drop all and recreate with NVARCHAR (Unicode).
Run: c:\python314\python.exe scripts/reset_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from core.orm import engine, Base

confirm = input("Drop and recreate ALL tables? This deletes all data. (yes/no): ").strip()
if confirm != "yes":
    print("Cancelled.")
    sys.exit(0)

print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)
print("Recreating tables with NVARCHAR...")
Base.metadata.create_all(bind=engine)
print("Done — restart the app now.")
