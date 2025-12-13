"""
booking_links.py - Generate real booking links for flights and hotels
Place this file in: handlers/booking_links.py
"""

from urllib.parse import urlencode
from datetime import datetime

class BookingLinkGenerator:
    """Generate real booking links for flights and hotels"""
    
    @staticmethod
    def generate_flight_link(origin_code, destination_code, departure_date, adults=1, 
                            airline=None, return_date=None):
        """
        Generate booking links for multiple platforms
        Returns a dict with links to different booking sites
        """
        
        # Format dates for URLs
        dep_date = departure_date if isinstance(departure_date, str) else departure_date.strftime('%Y-%m-%d')
        
        links = {}
        
        # 1. Skyscanner - Most popular aggregator
        skyscanner_params = {
            'adultsv2': adults,
            'cabinclass': 'economy',
            'children': 0,
            'destinationentityid': destination_code,
            'infants': 0,
            'originentityid': origin_code,
            'outbounddate': dep_date,
            'ref': 'home'
        }
        
        if return_date:
            ret_date = return_date if isinstance(return_date, str) else return_date.strftime('%Y-%m-%d')
            skyscanner_params['inbounddate'] = ret_date
        
        links['skyscanner'] = f"https://www.skyscanner.com/transport/flights/{origin_code}/{destination_code}/{dep_date}/"
        
        # 2. Google Flights - Direct Google search
        google_params = {
            'hl': 'en',
            'f': '0',  # One-way
            'tfs': f"f.0.d0.{dep_date}.{origin_code}.{destination_code}.ECONOMY"
        }
        links['google_flights'] = "https://www.google.com/travel/flights?" + urlencode(google_params)
        
        # 3. Kayak
        kayak_url = f"https://www.kayak.com/flights/{origin_code}-{destination_code}/{dep_date}"
        if return_date:
            ret_date = return_date if isinstance(return_date, str) else return_date.strftime('%Y-%m-%d')
            kayak_url += f"/{ret_date}"
        kayak_url += f"?sort=bestflight_a&passengers={adults}"
        links['kayak'] = kayak_url
        
        # 4. Expedia
        expedia_params = {
            'flight-type': 'on',
            'mode': 's',
            'trip': 'oneway',
            'leg1': f'from:{origin_code},to:{destination_code},departure:{dep_date}TANYT',
            'passengers': f'adults:{adults},children:0,seniors:0,infantinlap:Y'
        }
        links['expedia'] = "https://www.expedia.com/Flights-Search?" + urlencode(expedia_params)
        
        # 5. Momondo
        momondo_url = f"https://www.momondo.com/flight-search/{origin_code}-{destination_code}/{dep_date}"
        if return_date:
            ret_date = return_date if isinstance(return_date, str) else return_date.strftime('%Y-%m-%d')
            momondo_url += f"/{ret_date}"
        momondo_url += f"?sort=bestflight_a"
        links['momondo'] = momondo_url
        
        return links
    
    @staticmethod
    def generate_hotel_link(city, check_in, check_out, guests=1, rooms=1):
        """
        Generate hotel booking links for multiple platforms
        """
        
        # Format dates
        checkin_date = check_in if isinstance(check_in, str) else check_in.strftime('%Y-%m-%d')
        checkout_date = check_out if isinstance(check_out, str) else check_out.strftime('%Y-%m-%d')
        
        links = {}
        
        # 1. Booking.com - Most popular
        booking_params = {
            'ss': city,
            'checkin': checkin_date,
            'checkout': checkout_date,
            'group_adults': guests,
            'no_rooms': rooms,
            'group_children': 0
        }
        links['booking'] = "https://www.booking.com/searchresults.html?" + urlencode(booking_params)
        
        # 2. Hotels.com
        hotels_params = {
            'q-destination': city,
            'q-check-in': checkin_date,
            'q-check-out': checkout_date,
            'q-rooms': rooms,
            'q-room-0-adults': guests
        }
        links['hotels'] = "https://www.hotels.com/search.do?" + urlencode(hotels_params)
        
        # 3. Expedia Hotels
        expedia_params = {
            'destination': city,
            'startDate': checkin_date,
            'endDate': checkout_date,
            'rooms': rooms,
            'adults': guests
        }
        links['expedia'] = "https://www.expedia.com/Hotel-Search?" + urlencode(expedia_params)
        
        # 4. Agoda
        agoda_url = f"https://www.agoda.com/search?city={city.replace(' ', '+')}&checkIn={checkin_date}&checkOut={checkout_date}&rooms={rooms}&adults={guests}"
        links['agoda'] = agoda_url
        
        # 5. Trivago
        trivago_params = {
            'search': city,
            'checkin': checkin_date,
            'checkout': checkout_date
        }
        links['trivago'] = "https://www.trivago.com/?" + urlencode(trivago_params)
        
        return links
    
    @staticmethod
    def get_primary_flight_link(origin_code, destination_code, departure_date, adults=1):
        """Get the primary recommended booking link (Skyscanner)"""
        links = BookingLinkGenerator.generate_flight_link(
            origin_code, destination_code, departure_date, adults
        )
        return links.get('skyscanner', links.get('google_flights'))
    
    @staticmethod
    def get_primary_hotel_link(city, check_in, check_out, guests=1, rooms=1):
        """Get the primary recommended hotel link (Booking.com)"""
        links = BookingLinkGenerator.generate_hotel_link(
            city, check_in, check_out, guests, rooms
        )
        return links.get('booking')
    
    @staticmethod
    def format_flight_booking_message(links, flight_data=None):
        """Format a message with multiple booking options"""
        message = "🔗 *Book this flight on:*\n\n"
        
        platform_names = {
            'skyscanner': '✈️ Skyscanner (Recommended)',
            'google_flights': '🔍 Google Flights',
            'kayak': '🛫 Kayak',
            'expedia': '🌐 Expedia',
            'momondo': '🌍 Momondo'
        }
        
        for platform, url in links.items():
            name = platform_names.get(platform, platform.title())
            message += f"{name}\n{url}\n\n"
        
        return message
    
    @staticmethod
    def format_hotel_booking_message(links):
        """Format a message with multiple hotel booking options"""
        message = "🔗 *Book your hotel on:*\n\n"
        
        platform_names = {
            'booking': '🏨 Booking.com (Recommended)',
            'hotels': '🏩 Hotels.com',
            'expedia': '🌐 Expedia',
            'agoda': '🏖️ Agoda',
            'trivago': '🔍 Trivago'
        }
        
        for platform, url in links.items():
            name = platform_names.get(platform, platform.title())
            message += f"{name}\n{url}\n\n"
        
        return message


# Helper function for quick access
def get_flight_booking_link(origin, destination, date, adults=1):
    """Quick helper to get primary flight booking link"""
    return BookingLinkGenerator.get_primary_flight_link(origin, destination, date, adults)

def get_hotel_booking_link(city, check_in, check_out, guests=1, rooms=1):
    """Quick helper to get primary hotel booking link"""
    return BookingLinkGenerator.get_primary_hotel_link(city, check_in, check_out, guests, rooms)