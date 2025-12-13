import aiohttp
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

class BookingClient:
    def __init__(self):
        self.rapidapi_key = os.getenv('RAPIDAPI_KEY')
        self.session = None
    
    async def ensure_session(self):
        """Ensure we have an HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def search_hotels(self, city_name, check_in, check_out, adults=1, rooms=1):
        """Search hotels - using mock data only"""
        print(f"🔍 Searching hotels in {city_name} from {check_in} to {check_out}")
        
        try:
            # Always use mock data - skip API calls that are failing
            print("✅ Using mock hotel data (API disabled)")
            # Mock data returns instantly (or after brief sleep), so timeout rarely needed here
            hotels = await self._get_mock_hotels(city_name)
            print(f"✅ Found {len(hotels)} hotels")
            return hotels
            
        except Exception as e:
            print(f"❌ Hotel search error: {e}")
            return []
    
    async def _get_location_id(self, city_name):
        """Get location ID for city name"""
        url = "https://booking-com.p.rapidapi.com/v1/hotels/locations"
        headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
        }
        params = {
            "name": city_name,
            "locale": "en-us"
        }
        
        try:
            # FIX: Added timeout=15
            async with self.session.get(url, headers=headers, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        return data[0].get('dest_id')
                return None
        except asyncio.TimeoutError:
            print("❌ Location search timed out")
            return None
        except Exception as e:
            print(f"❌ Location search error: {e}")
            return None
    
    async def _search_hotels_by_location(self, location_id, check_in, check_out, adults, rooms):
        """Search hotels by location ID"""
        url = "https://booking-com.p.rapidapi.com/v1/hotels/search"
        headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": "booking-com.p.rapidapi.com"
        }
        params = {
            "checkin_date": check_in,
            "checkout_date": check_out,
            "units": "metric",
            "dest_id": location_id,
            "dest_type": "city",
            "adults_number": adults,
            "room_number": rooms,
            "order_by": "popularity",
            "filter_by_currency": "USD",
            "locale": "en-us",
            "page_number": "0"
        }
        
        try:
            # FIX: Added timeout=15
            async with self.session.get(url, headers=headers, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._format_hotel_data(data)
                else:
                    print(f"❌ Hotel search API returned status: {response.status}")
                    return None
        except asyncio.TimeoutError:
            print("❌ Hotel search timed out")
            return None
        except Exception as e:
            print(f"❌ Hotel search error: {e}")
            return None
    
    def _format_hotel_data(self, api_response):
        """Format Booking.com API response"""
        if 'result' not in api_response or not api_response['result']:
            return []
        
        formatted_hotels = []
        for hotel in api_response['result'][:5]:  # Limit to 5 results
            formatted_hotels.append({
                'name': hotel.get('hotel_name', 'Unknown Hotel'),
                'rating': str(hotel.get('review_score', 'N/A')) if hotel.get('review_score') else 'N/A',
                'address': hotel.get('address', 'Address not available'),
                'price': f"USD {hotel.get('min_total_price', 'N/A')}",
                'phone': hotel.get('phone', 'N/A'),
                'url': hotel.get('url', '#')
            })
        
        return formatted_hotels
    
    async def _get_mock_hotels(self, city_name):
        """Fallback mock hotel data"""
        await asyncio.sleep(1)  # Simulate API delay
        
        hotel_templates = {
            'paris': [
                {'name': 'Hotel Eiffel Tower', 'rating': '4.5', 'price': 'EUR 120', 'address': '15 Avenue de Tourville, Paris', 'phone': '+33 1 45 55 55 55'},
                {'name': 'Le Marais Boutique', 'rating': '4.2', 'price': 'EUR 95', 'address': 'Rue de Turenne, Paris', 'phone': '+33 1 42 78 78 78'},
                {'name': 'Champs-Élysées Plaza', 'rating': '4.7', 'price': 'EUR 180', 'address': 'Avenue des Champs-Élysées, Paris', 'phone': '+33 1 53 53 53 53'}
            ],
            # ... (rest of your mock data remains the same)
            'london': [
                {'name': 'London Bridge Hotel', 'rating': '4.3', 'price': 'GBP 110', 'address': '8 Holyrood Street, London', 'phone': '+44 20 7403 3333'},
                {'name': 'Kensington Gardens', 'rating': '4.1', 'price': 'GBP 85', 'address': 'Kensington High Street, London', 'phone': '+44 20 7937 1234'},
                {'name': 'The Shard Residence', 'rating': '4.8', 'price': 'GBP 220', 'address': '32 London Bridge St, London', 'phone': '+44 20 7234 8000'}
            ],
            'dubai': [
                {'name': 'Burj Al Arab', 'rating': '5.0', 'price': 'AED 1200', 'address': 'Jumeirah Beach Road, Dubai', 'phone': '+971 4 301 7777'},
                {'name': 'Dubai Marina Hotel', 'rating': '4.4', 'price': 'AED 450', 'address': 'Dubai Marina, Dubai', 'phone': '+971 4 436 1111'},
                {'name': 'City Centre Business', 'rating': '4.2', 'price': 'AED 320', 'address': 'Deira, Dubai', 'phone': '+971 4 295 2222'}
            ],
            'new york': [
                {'name': 'Times Square Suites', 'rating': '4.3', 'price': 'USD 150', 'address': '7th Avenue, New York', 'phone': '+1 212-586-1234'},
                {'name': 'Central Park View', 'rating': '4.6', 'price': 'USD 200', 'address': 'Central Park West, New York', 'phone': '+1 212-541-1234'},
                {'name': 'Manhattan Luxury', 'rating': '4.4', 'price': 'USD 175', 'address': '5th Avenue, New York', 'phone': '+1 212-755-1234'}
            ],
            'lagos': [
                {'name': 'Eko Hotels & Suites', 'rating': '4.5', 'price': 'NGN 45,000', 'address': 'Plot 1415 Adetokunbo Ademola, VI', 'phone': '+234 1 277 2700'},
                {'name': 'Radisson Blu', 'rating': '4.3', 'price': 'NGN 38,000', 'address': '38-40 Ozumba Mbadiwe, VI', 'phone': '+234 1 461 1000'},
                {'name': 'Ibis Lagos Airport', 'rating': '4.0', 'price': 'NGN 25,000', 'address': 'Mobolaji Johnson Airport Rd', 'phone': '+234 1 280 4888'}
            ]
        }
        
        city_key = city_name.lower()
        if city_key in hotel_templates:
            return hotel_templates[city_key]
        else:
            return [
                {'name': f'Grand {city_name.title()} Hotel', 'rating': '4.2', 'price': 'USD 100', 'address': f'City Center, {city_name.title()}', 'phone': '+1 234-567-8900'},
                {'name': f'{city_name.title()} City Suites', 'rating': '4.0', 'price': 'USD 85', 'address': f'Downtown, {city_name.title()}', 'phone': '+1 234-567-8901'},
                {'name': f'Comfort Inn {city_name.title()}', 'rating': '3.8', 'price': 'USD 65', 'address': f'Business District, {city_name.title()}', 'phone': '+1 234-567-8902'}
            ]
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()

# Global instance
booking_client = BookingClient()

# Helper function
async def search_hotels(city_name, check_in, check_out, adults=1, rooms=1):
    """Search hotels using Booking API"""
    return await booking_client.search_hotels(city_name, check_in, check_out, adults, rooms)