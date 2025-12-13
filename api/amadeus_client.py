"""
amadeus_client.py - Amadeus API Client with Intelligent Caching
Updated to include caching strategy for improved performance
"""

import os
import asyncio
import aiohttp
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
from api.cache import get_cache_manager

load_dotenv()

class AmadeusClient:
    def __init__(self):
        self.client_id = os.getenv('AMADEUS_CLIENT_ID')
        self.client_secret = os.getenv('AMADEUS_CLIENT_SECRET')
        self.base_url = "https://test.api.amadeus.com/v2"
        self.token = None
        self.token_expiry = 0
        self.session = None
        self.cache = get_cache_manager()

    async def ensure_session(self):
        """Ensure we have an HTTP session"""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def _get_access_token(self):
        """Get or refresh access token with caching (async version)"""
        # Check if we have a valid cached token
        if self.token and time.time() < self.token_expiry:
            return self.token
        
        # Try to get token from cache
        token_params = {'client_id': self.client_id}
        cached_token = self.cache.get_cached_response('amadeus_token', token_params)
        
        if cached_token:
            self.token = cached_token['access_token']
            self.token_expiry = cached_token['expiry']
            print("✅ Using cached Amadeus token")
            return self.token

        await self.ensure_session()

        url = "https://test.api.amadeus.com/v1/security/oauth2/token"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

        try:
            print("🔑 Requesting Amadeus API token...")
            async with self.session.post(url, headers=headers, data=data) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.token = token_data['access_token']
                    # Token expires in 30 minutes, refresh after 25 minutes
                    self.token_expiry = time.time() + (25 * 60)
                    
                    # Cache the token
                    cache_data = {
                        'access_token': self.token,
                        'expiry': self.token_expiry
                    }
                    self.cache.save_to_cache('amadeus_token', token_params, cache_data, 'token')
                    
                    print("✅ Successfully obtained Amadeus API token")
                    return self.token
                else:
                    error_text = await response.text()
                    print(f"❌ Token request failed: {response.status} - {error_text}")
                    return None
                    
        except asyncio.TimeoutError:
            print("❌ Token request timed out")
            return None
        except Exception as e:
            print(f"❌ Error getting token: {e}")
            return None

    async def search_flights(self, origin, destination, departure_date, adults=1):
        """
        Search for flights using Amadeus API with intelligent caching
        
        Cache Strategy:
        - Flights are cached for 1 hour
        - Same route + date = cache hit
        - Reduces API calls and improves response time
        """
        
        # Prepare search parameters
        search_params = {
            'origin': origin,
            'destination': destination,
            'departure_date': departure_date,
            'adults': adults
        }
        
        # Try to get from cache first
        cached_flights = self.cache.get_cached_response('amadeus_flights', search_params)
        if cached_flights:
            print(f"✅ Using cached flight data for {origin} → {destination}")
            return cached_flights
        
        # Cache miss - fetch from API
        token = await self._get_access_token()
        if not token:
            print("⚠️ No API token, returning mock data")
            mock_data = self._get_mock_flights(origin, destination)
            # Cache mock data too (shorter TTL)
            self.cache.save_to_cache('amadeus_flights', search_params, mock_data, 'flight')
            return mock_data

        await self.ensure_session()

        url = f"{self.base_url}/shopping/flight-offers"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": adults,
            "max": 5,
            "currencyCode": "EUR"
        }

        try:
            print(f"🔍 Searching flights: {origin} → {destination} on {departure_date}")
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    formatted_data = self._format_flight_data(data)
                    
                    # Cache the successful response
                    self.cache.save_to_cache('amadeus_flights', search_params, formatted_data, 'flight')
                    
                    print(f"✅ Found {len(formatted_data)} flights (cached for 1 hour)")
                    return formatted_data
                else:
                    error_text = await response.text()
                    print(f"❌ API Error ({response.status}): {error_text}")
                    mock_data = self._get_mock_flights(origin, destination)
                    # Cache mock data
                    self.cache.save_to_cache('amadeus_flights', search_params, mock_data, 'flight')
                    return mock_data
                    
        except asyncio.TimeoutError:
            print("❌ Search timed out, using mock data")
            mock_data = self._get_mock_flights(origin, destination)
            self.cache.save_to_cache('amadeus_flights', search_params, mock_data, 'flight')
            return mock_data
        except Exception as e:
            print(f"❌ Network error: {e}, using mock data")
            mock_data = self._get_mock_flights(origin, destination)
            self.cache.save_to_cache('amadeus_flights', search_params, mock_data, 'flight')
            return mock_data

    def _format_flight_data(self, api_response):
        """Format Amadeus API response into simple flight data"""
        if 'data' not in api_response or not api_response['data']:
            return []

        formatted_flights = []
        for offer in api_response['data']:
            try:
                price_info = offer['price']
                currency = price_info['currency']
                price = price_info['total']
                
                itinerary = offer['itineraries'][0]
                segments = itinerary['segments']
                
                airline = segments[0]['carrierCode'] if segments else 'Unknown'
                
                departure = segments[0]['departure']['at']
                arrival = segments[-1]['arrival']['at']
                
                dep_time = datetime.fromisoformat(departure.replace('Z', '+00:00'))
                arr_time = datetime.fromisoformat(arrival.replace('Z', '+00:00'))
                
                formatted_flights.append({
                    'price': f"{currency} {price}",
                    'airline': airline,
                    'departure': dep_time.strftime('%H:%M'),
                    'arrival': arr_time.strftime('%H:%M'),
                    'duration': itinerary['duration'].replace('PT', '').lower(),
                    'stops': len(segments) - 1
                })
            except Exception as e:
                print(f"⚠️ Error parsing flight offer: {e}")
                continue
        
        return formatted_flights
    
    def _get_mock_flights(self, origin, destination):
        """Return mock flight data when API fails"""
        print("📋 Using mock flight data")
        return [
            {
                'price': 'EUR 328.59',
                'airline': 'AT',
                'departure': '06:45',
                'arrival': '15:10',
                'duration': '9h25m',
                'stops': 1
            },
            {
                'price': 'EUR 450.00',
                'airline': 'LH',
                'departure': '10:30',
                'arrival': '18:45',
                'duration': '8h15m',
                'stops': 1
            },
            {
                'price': 'EUR 280.00',
                'airline': 'AF',
                'departure': '14:20',
                'arrival': '22:30',
                'duration': '10h10m',
                'stops': 2
            },
            {
                'price': 'EUR 395.00',
                'airline': 'BA',
                'departure': '11:15',
                'arrival': '19:30',
                'duration': '8h15m',
                'stops': 1
            },
            {
                'price': 'EUR 510.00',
                'airline': 'EK',
                'departure': '16:40',
                'arrival': '01:25',
                'duration': '10h45m',
                'stops': 1
            }
        ]

    async def close(self):
        """Close the HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

# Create global instance
amadeus_client = AmadeusClient()

# Async helper function
async def search_flights(origin, destination, departure_date=None):
    """Search flights with Amadeus API (async version with caching)"""
    if not departure_date:
        departure_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    return await amadeus_client.search_flights(origin, destination, departure_date)

# Airport code mapping with caching support
AIRPORT_CODES = {
    'lagos': 'LOS', 'los': 'LOS', 'nigeria': 'LOS',
    'london': 'LHR', 'lon': 'LHR', 'uk': 'LHR',
    'paris': 'CDG', 'france': 'CDG',
    'new york': 'JFK', 'nyc': 'JFK', 'newyork': 'JFK',
    'tokyo': 'TYO', 'japan': 'TYO',
    'dubai': 'DXB', 'uae': 'DXB',
    'abuja': 'ABV', 'port harcourt': 'PHC',
    'accra': 'ACC', 'ghana': 'ACC',
    'johannesburg': 'JNB', 'south africa': 'JNB',
    'amsterdam': 'AMS', 'netherlands': 'AMS',
    'berlin': 'BER', 'germany': 'BER',
    'madrid': 'MAD', 'spain': 'MAD',
    'rome': 'FCO', 'italy': 'FCO',
    'istanbul': 'IST', 'turkey': 'IST'
}

def get_airport_code(city_name):
    """
    Get airport code for city name with caching
    
    Cache airport codes for 7 days since they rarely change
    """
    cache = get_cache_manager()
    
    # Create cache params
    cache_params = {'city': city_name.lower().strip()}
    
    # Try cache first
    cached_code = cache.get_cached_response('airport_codes', cache_params)
    if cached_code:
        return cached_code['code']
    
    # Get from mapping
    code = AIRPORT_CODES.get(city_name.lower().strip(), city_name.upper()[:3])
    
    # Cache the result
    cache.save_to_cache('airport_codes', cache_params, {'code': code}, 'airport')
    
    return code