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
    
    if not DATABASE_URL:
        # Railway provides this automatically
        DATABASE_URL = os.getenv("DATABASE_URL_RAILWAY") or os.getenv("RAILWAY_DATABASE_URL")
    # If no DATABASE_URL, use SQLite for local development
    if not DATABASE_URL:
        DATABASE_URL = 'sqlite:///travel_bot.db'
    
    # Other configs...
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # Validate critical configs
    @classmethod
    def validate(cls):
        missing = []
        if not cls.DATABASE_URL:
            missing.append("DATABASE_URL")
        if not cls.AMADEUS_CLIENT_ID:
            missing.append("AMADEUS_CLIENT_ID")
        if not cls.AMADEUS_CLIENT_SECRET:
            missing.append("AMADEUS_CLIENT_SECRET")
        
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")

# Validate on import
Config.validate()