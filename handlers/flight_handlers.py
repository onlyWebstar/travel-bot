"""
Updated flight_handlers.py - Smarter origin handling
Now asks for origin instead of assuming Lagos
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from utils.nlp_processor import extract_travel_info, validate_destination
from api.amadeus_client import search_flights, get_airport_code
from database.session_manager import SessionManager
from handlers.booking_links import BookingLinkGenerator
from handlers.preferences_handler import get_user_home_city, get_user_budget

async def handle_flight_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    # Handle /flights command without arguments
    if update.message.text == '/flights':
        await update.message.reply_text(
            "🛫 Flight Search\n\n"
            "Where would you like to fly?\n\n"
            "Examples:\n"
            "• \"Flights from London to Paris\"\n"
            "• \"Fly to Dubai\"\n"
            "• \"New York to Tokyo\""
        )
        return
    
    # Extract information using enhanced NLP
    travel_info = extract_travel_info(user_message)
    
    # Handle errors from NLP processor
    if travel_info.get('error'):
        error_msg = travel_info['error']
        if travel_info.get('suggestion'):
            error_msg += f"\n\n{travel_info['suggestion']}"
        await update.message.reply_text(error_msg)
        return
    
    # Check if suggestion was made (fuzzy match)
    if travel_info.get('suggestion') and travel_info['confidence'] < 90:
        destination = travel_info.get('destination', 'Unknown')
        await update.message.reply_text(
            f"🤔 {travel_info['suggestion']}\n\n"
            f"I'll search for flights to {destination.title()}."
        )
    
    # Validate intent
    if travel_info['intent'] != 'flight':
        if '/flights' in user_message:
            travel_info['intent'] = 'flight'
        else:
            return
    
    destination = travel_info.get('destination')
    origin = travel_info.get('origin')
    
    # Check if we have destination
    if not destination:
        await update.message.reply_text(
            "❓ Where would you like to fly?\n\n"
            "Examples:\n"
            "• \"Flights from London to Paris\"\n"
            "• \"Fly to Dubai\"\n"
            "• \"Lagos to New York\""
        )
        return
    
    # Validate destination
    destination_code = travel_info.get('destination_code')
    if not destination_code or len(destination_code) != 3:
        await update.message.reply_text(
            f"❌ I don't recognize '{destination}' as a valid destination.\n\n"
            "Try popular cities like:\n"
            "• London • Paris • Dubai\n"
            "• New York • Los Angeles • Tokyo\n"
            "• Singapore • Sydney • Bangkok"
        )
        return
    
    # Smart origin handling - UPDATED LOGIC
    if not origin:
        # Check if user has home city in preferences
        user_home_city = get_user_home_city(user_id)
        
        # Only use preference if it's actually set (not the default 'Lagos')
        if user_home_city and user_home_city != 'Lagos':
            origin = user_home_city
            origin_code = get_airport_code(origin)
            
            # Inform user we're using their preference
            await update.message.reply_text(
                f"✈️ Searching flights from {origin.title()} to {destination.title()}\n"
                f"(Using your home city from preferences)\n\n"
                f"🔍 Searching..."
            )
        else:
            # No origin specified and no preference - ask for it
            # Store destination in context for next message
            context.user_data['pending_destination'] = destination
            context.user_data['pending_destination_code'] = destination_code
            context.user_data['pending_date'] = travel_info.get('date')
            
            await update.message.reply_text(
                f"✈️ Flying to {destination.title()}\n\n"
                f"📍 Where are you flying FROM?\n\n"
                f"Examples:\n"
                f"• London\n"
                f"• Lagos\n"
                f"• New York\n\n"
                f"💡 Tip: Set your home city with /preferences to skip this step!"
            )
            return
    else:
        origin_code = travel_info.get('origin_code') or get_airport_code(origin)
    
    # Validate origin code
    if not origin_code or len(origin_code) != 3:
        await update.message.reply_text(
            f"❌ I don't recognize '{origin}' as a valid city.\n\n"
            "Please specify where you're flying FROM:\n"
            "• \"Flights from London to Paris\"\n"
            "• Set your home city with /preferences"
        )
        return
    
    searching_msg = await update.message.reply_text(
        f"🔍 Searching flights: {origin.title()} → {destination.title()}..."
    )
    
    try:
        departure_date = travel_info.get('date')
        if not departure_date:
            departure_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Search for flights
        flights_data = await search_flights(origin_code, destination_code, departure_date)
        
        await searching_msg.delete()
        
        # Handle no flights found
        if not flights_data or (isinstance(flights_data, dict) and 'error' in flights_data):
            await update.message.reply_text(
                f"❌ No flights found\n\n"
                f"Route: {origin.title()} ({origin_code}) → {destination.title()} ({destination_code})\n"
                f"Date: {departure_date}\n\n"
                f"Try:\n"
                f"• Different dates\n"
                f"• Nearby airports\n"
                f"• Major hub cities"
            )
            return
        
        # Get user budget preference for filtering
        user_budget = get_user_budget(user_id)
        
        # Filter by budget if preference exists
        if user_budget:
            filtered_flights = []
            for flight in flights_data:
                try:
                    price_str = flight['price'].split()[-1]
                    price = float(price_str.replace(',', ''))
                    price_usd = price * 1.1  # EUR to USD approx
                    
                    if user_budget['min'] <= price_usd <= user_budget['max']:
                        filtered_flights.append(flight)
                except:
                    filtered_flights.append(flight)
            
            if filtered_flights:
                flights_data = filtered_flights
        
        # Save to database
        db = SessionManager()
        save_data = {
            'flights': flights_data,
            'search_info': {
                'origin': origin,
                'origin_code': origin_code,
                'destination': destination,
                'destination_code': destination_code,
                'date': departure_date
            }
        }
        db.save_search_context(user_id, first_name, 'flight', save_data)
        
        # Build response
        response = f"✈️ Flights: {origin.title()} → {destination.title()}\n"
        response += f"📅 Date: {departure_date}\n"
        response += f"🎫 Found {len(flights_data)} flights\n\n"
        
        # Create keyboard with booking links
        keyboard_rows = []

        for i, flight in enumerate(flights_data[:5], 1):
            response += f"{i}. {flight['airline']} - {flight['price']}\n"
            response += f"   {flight['departure']} → {flight['arrival']} ({flight['duration']})\n"
            
            if flight.get('stops', 0) == 0:
                response += "   ✈️ Direct flight\n"
            else:
                response += f"   🔄 {flight['stops']} stop(s)\n"

            # Generate real booking link
            booking_url = BookingLinkGenerator.get_primary_flight_link(
                origin_code, 
                destination_code, 
                departure_date,
                adults=1
            )
            
            button = InlineKeyboardButton(
                text=f"💳 Book {flight['price']}", 
                url=booking_url
            )
            keyboard_rows.append([button])
        
        # Add "More Options" button
        more_options_button = InlineKeyboardButton(
            text="🔗 More Booking Sites",
            callback_data=f"more_options_flight_{user_id}"
        )
        keyboard_rows.append([more_options_button])
            
        reply_markup = InlineKeyboardMarkup(keyboard_rows)

        await update.message.reply_text(
            response, 
            reply_markup=reply_markup
        )
        
        # Send all booking platform links
        all_links = BookingLinkGenerator.generate_flight_link(
            origin_code, 
            destination_code, 
            departure_date
        )
        
        links_message = BookingLinkGenerator.format_flight_booking_message(all_links)
        await update.message.reply_text(
            links_message,
            disable_web_page_preview=True
        )
        
        # Clear pending context
        context.user_data.pop('pending_destination', None)
        context.user_data.pop('pending_destination_code', None)
        context.user_data.pop('pending_date', None)
        
    except Exception as e:
        await searching_msg.delete()
        error_details = str(e)
        
        # Check for specific API errors
        if "INVALID_FORMAT" in error_details or "destinationLocationCode" in error_details:
            await update.message.reply_text(
                f"❌ Invalid destination code\n\n"
                f"'{destination}' ({destination_code}) is not recognized by the booking system.\n\n"
                f"Try popular destinations like:\n"
                f"• London (LHR) • Paris (CDG)\n"
                f"• Dubai (DXB) • New York (JFK)\n"
                f"• Los Angeles (LAX) • Tokyo (NRT)"
            )
        else:
            await update.message.reply_text(
                "❌ Search Error\n\n"
                "Something went wrong with the flight search.\n\n"
                "Please try:\n"
                "• Different destination\n"
                "• Different date\n"
                "• Type '/help' for examples"
            )
        
        print(f"Flight search error: {e}")


async def handle_origin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle when user provides origin after being asked
    This is called from the main message handler
    """
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Check if we have pending destination
    if 'pending_destination' not in context.user_data:
        return False  # Not handling origin response
    
    # Extract origin from message
    travel_info = extract_travel_info(user_message)
    
    # Try to get city from the message
    origin = None
    if travel_info.get('destination'):
        origin = travel_info['destination']  # User just typed city name
    elif travel_info.get('origin'):
        origin = travel_info['origin']
    
    if not origin:
        await update.message.reply_text(
            "❓ I didn't catch that. Please tell me which city you're flying FROM:\n\n"
            "Examples: London, Lagos, New York"
        )
        return True
    
    # Validate origin
    is_valid, origin_code, suggestion = validate_destination(origin)
    
    if not is_valid and not suggestion:
        await update.message.reply_text(
            f"❌ I don't recognize '{origin}' as a city.\n\n"
            "Please try: London, Lagos, New York, Dubai, Paris..."
        )
        return True
    
    if suggestion:
        origin = suggestion
        origin_code = get_airport_code(origin)
    
    # Get pending destination from context
    destination = context.user_data.get('pending_destination')
    destination_code = context.user_data.get('pending_destination_code')
    departure_date = context.user_data.get('pending_date')
    
    # Now search with complete information
    searching_msg = await update.message.reply_text(
        f"🔍 Searching flights: {origin.title()} → {destination.title()}..."
    )
    
    try:
        if not departure_date:
            departure_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        flights_data = await search_flights(origin_code, destination_code, departure_date)
        
        await searching_msg.delete()
        
        if not flights_data:
            await update.message.reply_text(f"❌ No flights found for this route.")
            return True
        
        # Save and display results (same as above)
        db = SessionManager()
        save_data = {
            'flights': flights_data,
            'search_info': {
                'origin': origin,
                'origin_code': origin_code,
                'destination': destination,
                'destination_code': destination_code,
                'date': departure_date
            }
        }
        db.save_search_context(user_id, update.effective_user.first_name, 'flight', save_data)
        
        # Build and send response (reuse code from above)
        response = f"✈️ Flights: {origin.title()} → {destination.title()}\n"
        response += f"📅 Date: {departure_date}\n"
        response += f"🎫 Found {len(flights_data)} flights\n\n"
        
        keyboard_rows = []
        for i, flight in enumerate(flights_data[:5], 1):
            response += f"{i}. {flight['airline']} - {flight['price']}\n"
            response += f"   {flight['departure']} → {flight['arrival']} ({flight['duration']})\n"
            
            booking_url = BookingLinkGenerator.get_primary_flight_link(
                origin_code, destination_code, departure_date
            )
            button = InlineKeyboardButton(text=f"💳 Book {flight['price']}", url=booking_url)
            keyboard_rows.append([button])
        
        reply_markup = InlineKeyboardMarkup(keyboard_rows)
        await update.message.reply_text(response, reply_markup=reply_markup)
        
        # Clear context
        context.user_data.pop('pending_destination', None)
        context.user_data.pop('pending_destination_code', None)
        context.user_data.pop('pending_date', None)
        
        return True
        
    except Exception as e:
        await searching_msg.delete()
        await update.message.reply_text("❌ Search error. Please try again.")
        print(f"Error: {e}")
        return True


async def handle_flight_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle flight selection by number"""
    user_id = update.effective_user.id
    user_input = update.message.text.strip()

    db = SessionManager()
    session_data = db.get_active_session(user_id)

    if not session_data or session_data.get('type') != 'flight':
        await update.message.reply_text(
            "❌ No active flight search found.\n\n"
            "Please search for flights first using:\n"
            "• \"Flights from London to Paris\"\n"
            "• /flights"
        )
        return

    try:
        flight_number = int(user_input)
        flights = session_data['data']['flights']
        search_info = session_data['data']['search_info']
        
        if flight_number < 1 or flight_number > len(flights):
            await update.message.reply_text(
                f"❌ Invalid selection\n\n"
                f"Please choose a number between 1 and {len(flights)}."
            )
            return

        selected_flight = flights[flight_number - 1]
        
        # Generate all booking links
        all_links = BookingLinkGenerator.generate_flight_link(
            search_info['origin_code'],
            search_info['destination_code'],
            search_info['date']
        )
        
        # Create inline keyboard
        keyboard = []
        button_config = [
            ('✈️ Skyscanner', 'skyscanner'),
            ('🔍 Google Flights', 'google_flights'),
            ('🛫 Kayak', 'kayak'),
            ('🌐 Expedia', 'expedia')
        ]
        
        for label, platform in button_config:
            if platform in all_links:
                keyboard.append([InlineKeyboardButton(text=label, url=all_links[platform])])
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ Flight Selected!\n\n"
            f"Flight Details:\n"
            f"✈️ Airline: {selected_flight['airline']}\n"
            f"💰 Price: {selected_flight['price']}\n"
            f"🕐 Departure: {selected_flight['departure']}\n"
            f"🕐 Arrival: {selected_flight['arrival']}\n"
            f"⏱️ Duration: {selected_flight['duration']}\n"
            f"🔄 Stops: {selected_flight.get('stops', 0)}\n\n"
            f"Route:\n"
            f"📍 {search_info['origin'].title()} ({search_info['origin_code']}) → "
            f"{search_info['destination'].title()} ({search_info['destination_code']})\n"
            f"📅 Date: {search_info['date']}\n\n"
            f"👇 Click below to complete your booking:",
            reply_markup=reply_markup
        )

        db.clear_session(user_id)

    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input\n\n"
            "Please send the number of the flight you want to select.\n"
            "Example: Send \"1\" to select the first flight."
        )