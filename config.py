import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    # We'll add Amadeus keys later when they work
    AMADEUS_CLIENT_ID=os.getenv('AMADEUS_CLIENT_ID')
    AMADEUS_CLIENT_SECRET=os.getenv('AMADEUS_CLIENT_SECRET')