# test_db.py
from Database.models import init_db, SessionLocal, User

try:
    print("⏳ Attempting to create database...")
    init_db() # This should create travel_bot.db file
    
    print("⏳ Testing connection...")
    db = SessionLocal()
    
    # Try adding a dummy user to see if it works
    test_user = User(user_id=12345, first_name="TestUser")
    db.add(test_user)
    db.commit()
    
    print("✅ SUCCESS! Database created and write test passed.")
    print("Check your folder for 'travel_bot.db'")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
finally:
    # Clean up (optional)
    if 'db' in locals():
        db.close()