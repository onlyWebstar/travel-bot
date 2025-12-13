import asyncio
from datetime import datetime, timedelta
from api.amadeus_client import search_flights
from api.booking_client import search_hotels

async def test_flights():
    print("🧪 Testing Flight API...")
    try:
        # Use future dates
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        result = await search_flights("LOS", "LON", future_date)  # Fixed: LON not LOW
        print(f"✅ Flight API Result: {result}")
    except Exception as e:
        print(f"❌ Flight API Error: {e}")

async def test_hotels():
    print("🧪 Testing Hotel API...")
    try:
        # Use future dates
        check_in = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        check_out = (datetime.now() + timedelta(days=33)).strftime('%Y-%m-%d')
        result = await search_hotels("Paris", check_in, check_out)
        print(f"✅ Hotel API Result: {result}")
    except Exception as e:
        print(f"❌ Hotel API Error: {e}")

async def main():
    await test_flights()
    print("\n" + "="*50 + "\n")
    await test_hotels()

if __name__ == "__main__":
    asyncio.run(main())