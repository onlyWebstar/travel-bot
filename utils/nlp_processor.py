"""
nlp_processor.py - Enhanced NLP with Smart Error Recovery
Handles unclear inputs, suggests corrections, and validates destinations
"""

import re
import spacy
from datetime import datetime, timedelta
from api.amadeus_client import get_airport_code
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

try:
    from dateutil.parser import parse
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False
    print("⚠️ dateutil not available, using basic date parsing")

# Try to load spaCy, but fall back to regex if not available
try:
    nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except OSError:
    SPACY_AVAILABLE = False
    print("⚠️ spaCy model not available, using regex-based NLP")

# Comprehensive city/airport database
KNOWN_DESTINATIONS = {
    # Major cities
    'lagos': 'LOS', 'los': 'LOS', 'lagos nigeria': 'LOS',
    'london': 'LHR', 'lon': 'LHR', 'london uk': 'LHR',
    'paris': 'CDG', 'paris france': 'CDG',
    'new york': 'JFK', 'nyc': 'JFK', 'newyork': 'JFK', 'new york city': 'JFK',
    'los angeles': 'LAX', 'la': 'LAX', 'losangeles': 'LAX',
    'tokyo': 'NRT', 'tokyo japan': 'NRT',
    'dubai': 'DXB', 'dubai uae': 'DXB',
    'abuja': 'ABV', 'abuja nigeria': 'ABV',
    'port harcourt': 'PHC', 'ph': 'PHC', 'portharcourt': 'PHC',
    'accra': 'ACC', 'accra ghana': 'ACC',
    'johannesburg': 'JNB', 'joburg': 'JNB', 'jnb': 'JNB',
    'amsterdam': 'AMS', 'amsterdam netherlands': 'AMS',
    'berlin': 'BER', 'berlin germany': 'BER',
    'madrid': 'MAD', 'madrid spain': 'MAD',
    'rome': 'FCO', 'rome italy': 'FCO',
    'istanbul': 'IST', 'istanbul turkey': 'IST',
    'singapore': 'SIN', 'singapore city': 'SIN',
    'hong kong': 'HKG', 'hongkong': 'HKG',
    'bangkok': 'BKK', 'bangkok thailand': 'BKK',
    'sydney': 'SYD', 'sydney australia': 'SYD',
    'melbourne': 'MEL', 'melbourne australia': 'MEL',
    'toronto': 'YYZ', 'toronto canada': 'YYZ',
    'vancouver': 'YVR', 'vancouver canada': 'YVR',
    'chicago': 'ORD', 'chicago usa': 'ORD',
    'miami': 'MIA', 'miami usa': 'MIA',
    'atlanta': 'ATL', 'atlanta usa': 'ATL',
    'boston': 'BOS', 'boston usa': 'BOS',
    'san francisco': 'SFO', 'sf': 'SFO', 'sanfrancisco': 'SFO',
    'washington': 'IAD', 'dc': 'IAD', 'washington dc': 'IAD',
    'lisbon': 'LIS', 'lisbon portugal': 'LIS',
    'barcelona': 'BCN', 'barcelona spain': 'BCN',
    'munich': 'MUC', 'munich germany': 'MUC',
    'zurich': 'ZRH', 'zurich switzerland': 'ZRH',
    'vienna': 'VIE', 'vienna austria': 'VIE',
    'prague': 'PRG', 'prague czech': 'PRG',
    'athens': 'ATH', 'athens greece': 'ATH',
    'cairo': 'CAI', 'cairo egypt': 'CAI',
    'nairobi': 'NBO', 'nairobi kenya': 'NBO',
    'cape town': 'CPT', 'capetown': 'CPT',
    'casablanca': 'CMN', 'casablanca morocco': 'CMN',
    'addis ababa': 'ADD', 'addisababa': 'ADD',
    'kigali': 'KGL', 'kigali rwanda': 'KGL',
    'dar es salaam': 'DAR', 'daressalaam': 'DAR',
    'manchester': 'MAN', 'manchester uk': 'MAN',
    'edinburgh': 'EDI', 'edinburgh uk': 'EDI',
    'glasgow': 'GLA', 'glasgow uk': 'GLA',
    'frankfurt': 'FRA', 'frankfurt germany': 'FRA',
    'milan': 'MXP', 'milan italy': 'MXP',
    'venice': 'VCE', 'venice italy': 'VCE',
    'dublin': 'DUB', 'dublin ireland': 'DUB',
    'brussels': 'BRU', 'brussels belgium': 'BRU',
    'copenhagen': 'CPH', 'copenhagen denmark': 'CPH',
    'stockholm': 'ARN', 'stockholm sweden': 'ARN',
    'oslo': 'OSL', 'oslo norway': 'OSL',
    'helsinki': 'HEL', 'helsinki finland': 'HEL',
    'moscow': 'SVO', 'moscow russia': 'SVO',
    'warsaw': 'WAW', 'warsaw poland': 'WAW',
    'budapest': 'BUD', 'budapest hungary': 'BUD',
    'bucharest': 'OTP', 'bucharest romania': 'OTP',
    'kuala lumpur': 'KUL', 'kl': 'KUL', 'kualalumpur': 'KUL',
    'jakarta': 'CGK', 'jakarta indonesia': 'CGK',
    'manila': 'MNL', 'manila philippines': 'MNL',
    'delhi': 'DEL', 'new delhi': 'DEL', 'delhi india': 'DEL',
    'mumbai': 'BOM', 'bombay': 'BOM', 'mumbai india': 'BOM',
    'bangalore': 'BLR', 'bengaluru': 'BLR',
    'chennai': 'MAA', 'madras': 'MAA',
    'kolkata': 'CCU', 'calcutta': 'CCU',
    'hyderabad': 'HYD', 'hyderabad india': 'HYD',
    'karachi': 'KHI', 'karachi pakistan': 'KHI',
    'lahore': 'LHE', 'lahore pakistan': 'LHE',
    'dhaka': 'DAC', 'dhaka bangladesh': 'DAC',
    'colombo': 'CMB', 'colombo sri lanka': 'CMB',
    'kathmandu': 'KTM', 'kathmandu nepal': 'KTM',
    'shanghai': 'PVG', 'shanghai china': 'PVG',
    'beijing': 'PEK', 'beijing china': 'PEK',
    'guangzhou': 'CAN', 'guangzhou china': 'CAN',
    'seoul': 'ICN', 'seoul korea': 'ICN',
    'taipei': 'TPE', 'taipei taiwan': 'TPE',
    'hanoi': 'HAN', 'hanoi vietnam': 'HAN',
    'ho chi minh': 'SGN', 'saigon': 'SGN', 'hochiminh': 'SGN',
    'phnom penh': 'PNH', 'phnompenh': 'PNH',
    'yangon': 'RGN', 'rangoon': 'RGN',
    'tehran': 'IKA', 'tehran iran': 'IKA',
    'riyadh': 'RUH', 'riyadh saudi': 'RUH',
    'jeddah': 'JED', 'jeddah saudi': 'JED',
    'doha': 'DOH', 'doha qatar': 'DOH',
    'abu dhabi': 'AUH', 'abudhabi': 'AUH',
    'muscat': 'MCT', 'muscat oman': 'MCT',
    'kuwait': 'KWI', 'kuwait city': 'KWI',
    'beirut': 'BEY', 'beirut lebanon': 'BEY',
    'amman': 'AMM', 'amman jordan': 'AMM',
    'tel aviv': 'TLV', 'telaviv': 'TLV',
}

def find_closest_destination(query):
    """
    Find the closest matching destination using fuzzy matching
    Returns: (matched_city, confidence_score, airport_code)
    """
    if not query:
        return None, 0, None
    
    query = query.lower().strip()
    
    # Direct match
    if query in KNOWN_DESTINATIONS:
        return query, 100, KNOWN_DESTINATIONS[query]
    
    # Fuzzy match
    matches = process.extract(query, KNOWN_DESTINATIONS.keys(), limit=3, scorer=fuzz.ratio)
    
    if matches and matches[0][1] >= 70:  # 70% confidence threshold
        matched_city = matches[0][0]
        confidence = matches[0][1]
        airport_code = KNOWN_DESTINATIONS[matched_city]
        return matched_city, confidence, airport_code
    
    return None, 0, None

def validate_destination(destination):
    """
    Validate if a destination is recognized
    Returns: (is_valid, airport_code, suggestion)
    """
    if not destination:
        return False, None, None
    
    matched_city, confidence, airport_code = find_closest_destination(destination)
    
    if confidence >= 90:
        # High confidence - use it
        return True, airport_code, None
    elif confidence >= 70:
        # Medium confidence - suggest correction
        return False, airport_code, matched_city
    else:
        # Low confidence - destination unknown
        return False, None, None

def extract_travel_info(text):
    """
    Enhanced travel information extraction with smart error recovery
    """
    text = text.lower().strip()
    
    # Default response
    result = {
        'intent': 'unknown',
        'destination': None,
        'origin': None,
        'date': None,
        'check_in': None,
        'check_out': None,
        'budget': None,
        'destination_code': None,
        'origin_code': None,
        'guests': 1,
        'rooms': 1,
        'error': None,
        'suggestion': None,
        'confidence': 100
    }
    
    # Check for intent using keywords
    flight_keywords = ['flight', 'fly', 'airline', 'airport', 'ticket', 'book flight', 'flights']
    hotel_keywords = ['hotel', 'stay', 'accommodation', 'lodging', 'room', 'book hotel', 'hostel']
    
    if any(keyword in text for keyword in flight_keywords):
        result['intent'] = 'flight'
    elif any(keyword in text for keyword in hotel_keywords):
        result['intent'] = 'hotel'
    elif any(word in text for word in ['to ', 'from ']):
        result['intent'] = 'flight'
    
    # Extract locations using enhanced regex
    locations = extract_locations_enhanced(text)
    
    # Process locations based on intent
    if locations:
        if result['intent'] == 'flight':
            if len(locations) >= 2:
                # Validate origin
                is_valid_origin, origin_code, origin_suggestion = validate_destination(locations[0])
                if is_valid_origin:
                    result['origin'] = locations[0]
                    result['origin_code'] = origin_code
                elif origin_suggestion:
                    result['origin'] = origin_suggestion
                    result['origin_code'] = origin_code
                    result['suggestion'] = f"Did you mean {origin_suggestion.title()}?"
                    result['confidence'] = 80
                
                # Validate destination
                is_valid_dest, dest_code, dest_suggestion = validate_destination(locations[1])
                if is_valid_dest:
                    result['destination'] = locations[1]
                    result['destination_code'] = dest_code
                elif dest_suggestion:
                    result['destination'] = dest_suggestion
                    result['destination_code'] = dest_code
                    result['suggestion'] = f"Did you mean {dest_suggestion.title()}?"
                    result['confidence'] = 80
                else:
                    result['error'] = f"I don't recognize '{locations[1]}'. Try a major city like London, Paris, or Dubai."
                    result['intent'] = 'unknown'
                    
            elif len(locations) == 1:
                # Only destination provided
                is_valid_dest, dest_code, dest_suggestion = validate_destination(locations[0])
                if is_valid_dest:
                    result['origin'] = 'Lagos'
                    result['origin_code'] = 'LOS'
                    result['destination'] = locations[0]
                    result['destination_code'] = dest_code
                elif dest_suggestion:
                    result['origin'] = 'Lagos'
                    result['origin_code'] = 'LOS'
                    result['destination'] = dest_suggestion
                    result['destination_code'] = dest_code
                    result['suggestion'] = f"Did you mean {dest_suggestion.title()}?"
                    result['confidence'] = 80
                else:
                    result['error'] = f"I don't recognize '{locations[0]}'. Try cities like:\n• London\n• Paris\n• Dubai\n• New York"
                    result['intent'] = 'unknown'
        else:  # hotel intent
            if len(locations) >= 1:
                is_valid_dest, dest_code, dest_suggestion = validate_destination(locations[0])
                if is_valid_dest or dest_suggestion:
                    result['destination'] = dest_suggestion if dest_suggestion else locations[0]
                    if dest_suggestion:
                        result['suggestion'] = f"Did you mean {dest_suggestion.title()}?"
                        result['confidence'] = 80
                else:
                    result['error'] = f"I don't recognize '{locations[0]}' as a city."
                    result['intent'] = 'unknown'
    else:
        # No location found
        if result['intent'] == 'flight':
            result['error'] = "Where would you like to fly to? Example: 'Flights to London'"
        elif result['intent'] == 'hotel':
            result['error'] = "Which city do you need a hotel in? Example: 'Hotels in Paris'"
    
    # Extract dates
    date_info = extract_dates(text)
    result.update(date_info)
    
    # Extract guest and room count
    guests_rooms = extract_guests_rooms(text)
    result.update(guests_rooms)
    
    return result

def extract_locations_enhanced(text):
    """Enhanced location extraction with better pattern matching"""
    locations = []
    
    # Remove common noise words
    noise_words = ['cheap', 'expensive', 'direct', 'nonstop', 'return', 'round trip', 
                   'one way', 'business class', 'economy', 'first class']
    for word in noise_words:
        text = text.replace(word, '')
    
    patterns = [
        r'from\s+([a-zA-Z\s]+?)\s+to\s+([a-zA-Z\s]+?)(?:\s+on|\s+for|\s+in|\s+at|$)',
        r'flights?\s+to\s+([a-zA-Z\s]+?)(?:\s+from|\s+on|\s+for|\s+tomorrow|\s+today|$)',
        r'fly\s+to\s+([a-zA-Z\s]+?)(?:\s+from|\s+on|\s+for|\s+tomorrow|\s+today|$)',
        r'hotels?\s+in\s+([a-zA-Z\s]+?)(?:\s+for|\s+on|\s+from|$)',
        r'stay\s+in\s+([a-zA-Z\s]+?)(?:\s+for|\s+on|$)',
        r'accommodation\s+in\s+([a-zA-Z\s]+?)(?:\s+for|\s+on|$)',
        r'to\s+([a-zA-Z\s]+?)(?:\s+from|\s+on|\s+for|\s+tomorrow|\s+today|$)',
        r'in\s+([a-zA-Z\s]+?)(?:\s+for|\s+on|$)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            if isinstance(matches[0], tuple):
                # Multiple locations (from X to Y)
                for location in matches[0]:
                    clean_loc = location.strip()
                    if len(clean_loc) > 2 and clean_loc not in ['a', 'the', 'and', 'or', 'be']:
                        locations.append(clean_loc.lower())
            else:
                # Single location
                clean_loc = matches[0].strip()
                if len(clean_loc) > 2 and clean_loc not in ['a', 'the', 'and', 'or', 'be']:
                    locations.append(clean_loc.lower())
            break
    
    # Remove duplicates while preserving order
    seen = set()
    unique_locations = []
    for loc in locations:
        if loc not in seen:
            seen.add(loc)
            unique_locations.append(loc)
    
    return unique_locations

def extract_dates(text):
    """Extract check-in and check-out dates"""
    today = datetime.now()
    result = {
        'date': None,
        'check_in': None,
        'check_out': None
    }
    
    result['date'] = extract_date_simple(text)
    
    if 'hotel' in text.lower() or 'stay' in text.lower():
        result['check_in'] = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        result['check_out'] = (today + timedelta(days=3)).strftime('%Y-%m-%d')
        
        duration_patterns = [
            r'for\s+(\d+)\s+night',
            r'for\s+(\d+)\s+days',
            r'(\d+)\s+night',
            r'(\d+)\s+day'
        ]
        
        for pattern in duration_patterns:
            matches = re.findall(pattern, text)
            if matches:
                nights = int(matches[0])
                result['check_out'] = (today + timedelta(days=1 + nights)).strftime('%Y-%m-%d')
                break
    
    return result

def extract_guests_rooms(text):
    """Extract number of guests and rooms"""
    result = {
        'guests': 1,
        'rooms': 1
    }
    
    guest_patterns = [
        r'for\s+(\d+)\s+guest',
        r'for\s+(\d+)\s+people',
        r'for\s+(\d+)\s+person',
        r'(\d+)\s+guest',
        r'(\d+)\s+people',
        r'(\d+)\s+person'
    ]
    
    for pattern in guest_patterns:
        matches = re.findall(pattern, text)
        if matches:
            result['guests'] = int(matches[0])
            break
    
    room_patterns = [
        r'(\d+)\s+room',
        r'for\s+(\d+)\s+room'
    ]
    
    for pattern in room_patterns:
        matches = re.findall(pattern, text)
        if matches:
            result['rooms'] = int(matches[0])
            break
    
    return result

def extract_date_simple(text):
    """Extract and format date reliably"""
    today = datetime.now()
    current_year = today.year
    
    if 'tomorrow' in text:
        return (today + timedelta(days=1)).strftime('%Y-%m-%d')
    elif 'next week' in text:
        return (today + timedelta(days=7)).strftime('%Y-%m-%d')
    elif 'today' in text:
        return today.strftime('%Y-%m-%d')
    
    day_mapping = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }
    
    for day_name, day_num in day_mapping.items():
        if day_name in text:
            days_ahead = (day_num - today.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
    
    month_mapping = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    date_patterns = [
        r'(\d{1,2})(?:st|nd|rd|th)?\s+of\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
        r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?',
        r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})'
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            if len(matches[0]) == 2:
                if matches[0][0].isdigit() and matches[0][1].isalpha():
                    day = int(matches[0][0])
                    month_name = matches[0][1].lower()
                else:
                    month_name = matches[0][0].lower()
                    day = int(matches[0][1])
                
                if month_name in month_mapping:
                    month = month_mapping[month_name]
                    target_date = datetime(current_year, month, day)
                    if target_date < today:
                        target_date = datetime(current_year + 1, month, day)
                    return target_date.strftime('%Y-%m-%d')
            
            elif len(matches[0]) == 3 and matches[0][0].isdigit() and len(matches[0][0]) == 4:
                year, month, day = int(matches[0][0]), int(matches[0][1]), int(matches[0][2])
                return f"{year:04d}-{month:02d}-{day:02d}"
    
    return (today + timedelta(days=1)).strftime('%Y-%m-%d')