from sqlalchemy import create_engine, Column, BigInteger, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY
from sqlalchemy.ext.declarative import declarative_base 
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import uuid
import os
import json
from datetime import datetime

# Database URL with proper fallback
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///travel_bot.db')

Base = declarative_base()

class User(Base):
    """Matches schema in Section 4.4.3"""
    __tablename__ = 'users'

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255))
    first_name = Column(String(255), nullable=False)
    language_code = Column(String(10), default='en')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), onupdate=func.now())

    sessions = relationship("UserSessionModel", back_populates="user")
    preferences = relationship("Preferences", back_populates="user", uselist=False)


class UserSessionModel(Base):
    """Handles context retention (Section 4.5.2)"""
    __tablename__ = 'sessions'

    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(BigInteger, ForeignKey('users.user_id'))
    
    # CRITICAL FIX: Use Text for SQLite, JSONB for PostgreSQL
    # Store JSON as TEXT string in SQLite
    context = Column(Text, default='{}')
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="sessions")
    
    def get_context(self):
        """Parse JSON context from TEXT field"""
        if isinstance(self.context, str):
            return json.loads(self.context) if self.context else {}
        return self.context
    
    def set_context(self, context_dict):
        """Store context as JSON string"""
        self.context = json.dumps(context_dict)


class Preferences(Base):
    """Stores personalization data (Section 4.4.3)"""
    __tablename__ = 'preferences'

    user_id = Column(BigInteger, ForeignKey('users.user_id'), primary_key=True)
    
    # Store as comma-separated string for SQLite compatibility
    preferred_airlines = Column(String)
    budget_ranges = Column(Text, default='{}')
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="preferences")
    
    def get_budget_ranges(self):
        """Parse budget ranges from JSON string"""
        return json.loads(self.budget_ranges) if self.budget_ranges else {}
    
    def set_budget_ranges(self, ranges_dict):
        """Store budget ranges as JSON string"""
        self.budget_ranges = json.dumps(ranges_dict)


class APICache(Base):
    """Implements the caching strategy (Section 4.6.1)"""
    __tablename__ = 'api_cache'

    cache_key = Column(String(255), primary_key=True)
    provider = Column(String(50))
    response_data = Column(Text)  # Store as TEXT for SQLite
    expires_at = Column(DateTime(timezone=True))
    
    def get_response_data(self):
        """Parse response data from JSON string"""
        return json.loads(self.response_data) if self.response_data else None
    
    def set_response_data(self, data_dict):
        """Store response data as JSON string"""
        self.response_data = json.dumps(data_dict)


# Database Connection Setup
engine = create_engine(DATABASE_URL, echo=False)  # Set echo=True for debugging
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully matching Report Schema 4.4.3")
        return True
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        db.close()
        raise