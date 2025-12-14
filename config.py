import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    AMADEUS_CLIENT_ID=os.getenv('AMADEUS_CLIENT_ID')
    AMADEUS_CLIENT_SECRET=os.getenv('AMADEUS_CLIENT_SECRET')
    
    # Railway provides DATABASE_URL for PostgreSQL
    # For local development, use SQLite
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        # Railway uses postgres:// but SQLAlchemy needs postgresql://
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # If no DATABASE_URL, use SQLite for local development
    if not DATABASE_URL:
        DATABASE_URL = 'sqlite:///travel_bot.db'