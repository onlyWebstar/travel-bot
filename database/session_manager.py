from database.models import SessionLocal, UserSessionModel, User
from datetime import datetime, timedelta
import json

class SessionManager:
    def __init__(self):
        self.db = SessionLocal()

    def save_search_context(self, user_id, first_name, search_type, data):
        """Saves search results to DB (Report Section 4.5.2)"""
        try:
            # 1. Ensure User Exists
            user = self.db.query(User).filter(User.user_id == user_id).first()
            if not user:
                user = User(user_id=user_id, first_name=first_name or "Traveler")
                self.db.add(user)
                self.db.commit()
                print(f"✅ Created new user: {user_id}")

            # 2. Get or Create Session
            user_session = self.db.query(UserSessionModel).filter(
                UserSessionModel.user_id == user_id
            ).first()
            
            # 3. Prepare context data as a dictionary
            # Convert datetime to ISO string for JSON serialization
            new_context = {
                "type": search_type,  # 'flight' or 'hotel'
                "data": data,
                "timestamp": datetime.now().isoformat()  # ISO format: '2025-11-21T10:30:00'
            }

            # 4. Update or Create Session
            if user_session:
                # Update existing session
                user_session.set_context(new_context)  # This converts dict to JSON string
                user_session.expires_at = datetime.now() + timedelta(minutes=30)
                print(f"✅ Updated session for user {user_id}")
            else:
                # Create new session
                user_session = UserSessionModel(
                    user_id=user_id,
                    expires_at=datetime.now() + timedelta(minutes=30)
                )
                user_session.set_context(new_context)  # This converts dict to JSON string
                self.db.add(user_session)
                print(f"✅ Created new session for user {user_id}")
            
            # 5. Commit changes to database
            self.db.commit()
            return True
            
        except Exception as e:
            print(f"❌ Database Error (Save): {e}")
            # Print full error traceback for debugging
            import traceback
            traceback.print_exc()
            self.db.rollback()
            return False
        finally:
            self.db.close()

    def get_active_session(self, user_id):
        """Retrieves active session if not expired"""
        try:
            user_session = self.db.query(UserSessionModel).filter(
                UserSessionModel.user_id == user_id
            ).first()
            
            if not user_session:
                print(f"ℹ️ No session found for user {user_id}")
                return None
            
            # Check expiration (Report Section 4.6.3)
            if user_session.expires_at and user_session.expires_at < datetime.now():
                print(f"⚠️ Session expired for user {user_id}")
                return None

            # Return parsed context dictionary (converts JSON string back to dict)
            context = user_session.get_context()
            print(f"✅ Retrieved session for user {user_id}, type: {context.get('type')}")
            return context
            
        except Exception as e:
            print(f"❌ Database Error (Get): {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            self.db.close()

    def clear_session(self, user_id):
        """Clears session after booking"""
        try:
            deleted_count = self.db.query(UserSessionModel).filter(
                UserSessionModel.user_id == user_id
            ).delete()
            self.db.commit()
            
            if deleted_count > 0:
                print(f"✅ Cleared {deleted_count} session(s) for user {user_id}")
            else:
                print(f"ℹ️ No session to clear for user {user_id}")
                
        except Exception as e:
            print(f"❌ Database Error (Clear): {e}")
            self.db.rollback()
        finally:
            self.db.close()

    def update_session_expiry(self, user_id):
        """Extends session expiration time (useful for active users)"""
        try:
            user_session = self.db.query(UserSessionModel).filter(
                UserSessionModel.user_id == user_id
            ).first()
            
            if user_session:
                user_session.expires_at = datetime.now() + timedelta(minutes=30)
                self.db.commit()
                print(f"✅ Extended session for user {user_id}")
                return True
            return False
            
        except Exception as e:
            print(f"❌ Database Error (Update Expiry): {e}")
            self.db.rollback()
            return False
        finally:
            self.db.close()