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
            "🛫 *Flight Search*\n\n"
            "Where would you like to fly?\n\n"
            "Examples:\n"
            "• \"Flights to London\"\n"
            "• \"Fly to Paris tomorrow\"\n"
            "• \"Book flight from Lagos to Dubai\"",
            parse_mode='Markdown'
        )
        return
    
    # Extract information using enhanced NLP
    travel_info = extract_travel_info(user_message)
    
    # Handle errors from NLP processor
    if travel_info.get('error'):
        error_msg = travel_info['error']
        if travel_info.get('suggestion'):
            error_msg += f"\n\n{travel_info['suggestion']}"
        
        await update.message.reply_text(f"❌ {error_msg}", parse_mode='Markdown')
        return
    
    # Check if suggestion was made (fuzzy match)
    if travel_info.get('suggestion') and travel_info['confidence'] < 90:
        # Ask for confirmation
        destination = travel_info.get('destination', 'Unknown')
        await update.message.reply_text(
            f"🤔 {travel_info['suggestion']}\n\n"
            f"I'll search for flights to *{destination.title()}*. "
            f"If this is correct, I'll proceed!",
            parse_mode='Markdown'
        )
    
    # Validate intent
    if travel_info['intent'] != 'flight':
        if '/flights' in user_message:
            travel_info['intent'] = 'flight'
        else:
            return
    
    destination = travel_info.get('destination')
    if not destination:
        await update.message.reply_text(
            "❓ *Where would you like to fly?*\n\n"
            "Try: \"Flights to London\" or \"Fly to Paris\"",
            parse_mode='Markdown'
        )
        return
    
    # Validate destination before searching
    destination_code = travel_info.get('destination_code')
    if not destination_code or len(destination_code) != 3:
        await update.message.reply_text(
            f"❌ I don't recognize '{destination}' as a valid destination.\n\n"
            f"*Try popular cities like:*\n"
            f"• London • Paris • Dubai\n"
            f"• New York • Los Angeles • Tokyo\n"
            f"• Singapore • Sydney • Bangkok",
            parse_mode='Markdown'
        )
        return
    
    searching_msg = await update.message.reply_text(
        f"🔍 *Searching flights to {destination.title()}...*", 
        parse_mode='Markdown'
    )
    
    try:
        # Get user's home city from preferences
        user_home_city = get_user_home_city(user_id)
        
        # Use preference if origin not specified
        origin = travel_info.get('origin') or user_home_city
        origin_code = travel_info.get('origin_code') or get_airport_code(origin)
        
        # Validate origin code
        if not origin_code or len(origin_code) != 3:
            origin = 'Lagos'
            origin_code = 'LOS'
        
        departure_date = travel_info.get('date')
        if not departure_date:
            departure_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Search for flights
        flights_data = await search_flights(origin_code, destination_code, departure_date)
        
        await searching_msg.delete()
        
        # Handle no flights found
        if not flights_data or (isinstance(flights_data, dict) and 'error' in flights_data):
            await update.message.reply_text(
                f"❌ *No flights found*\n\n"
                f"Route: {origin.title()} ({origin_code}) → {destination.title()} ({destination_code})\n"
                f"Date: {departure_date}\n\n"
                f"*Try:*\n"
                f"• Different dates\n"
                f"• Nearby airports\n"
                f"• Major hub cities",
                parse_mode='Markdown'
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
        response = f"✈️ *Flights: {origin.title()} → {destination.title()}*\n"
        response += f"📅 *Date:* {departure_date}\n"
        response += f"🎫 *Found {len(flights_data)} flights*\n\n"
        
        # Create keyboard with booking links
        keyboard_rows = []

        for i, flight in enumerate(flights_data[:5], 1):
            response += f"*{i}. {flight['airline']}* - {flight['price']}\n"
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
            reply_markup=reply_markup, 
            parse_mode='Markdown'
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
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        await searching_msg.delete()
        error_details = str(e)
        
        # Check for specific API errors
        if "INVALID_FORMAT" in error_details or "destinationLocationCode" in error_details:
            await update.message.reply_text(
                f"❌ *Invalid destination code*\n\n"
                f"'{destination}' ({destination_code}) is not recognized by the booking system.\n\n"
                f"*Try popular destinations like:*\n"
                f"• London (LHR) • Paris (CDG)\n"
                f"• Dubai (DXB) • New York (JFK)\n"
                f"• Los Angeles (LAX) • Tokyo (NRT)",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ *Search Error*\n\n"
                "Something went wrong with the flight search.\n\n"
                "*Please try:*\n"
                "• Different destination\n"
                "• Different date\n"
                "• Type '/help' for examples",
                parse_mode='Markdown'
            )
        
        print(f"Flight search error: {e}")

async def handle_flight_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_input = update.message.text.strip()

    db = SessionManager()
    session_data = db.get_active_session(user_id)

    if not session_data or session_data.get('type') != 'flight':
        await update.message.reply_text(
            "❌ *No active flight search found.*\n\n"
            "Please search for flights first using:\n"
            "• \"Flights to London\"\n"
            "• /flights",
            parse_mode='Markdown'
        )
        return

    try:
        flight_number = int(user_input)
        flights = session_data['data']['flights']
        search_info = session_data['data']['search_info']
        
        if flight_number < 1 or flight_number > len(flights):
            await update.message.reply_text(
                f"❌ *Invalid selection*\n\n"
                f"Please choose a number between 1 and {len(flights)}.", 
                parse_mode='Markdown'
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
                keyboard.append([
                    InlineKeyboardButton(text=label, url=all_links[platform])
                ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ *Flight Selected!*\n\n"
            f"*Flight Details:*\n"
            f"✈️ Airline: {selected_flight['airline']}\n"
            f"💰 Price: {selected_flight['price']}\n"
            f"🕐 Departure: {selected_flight['departure']}\n"
            f"🕐 Arrival: {selected_flight['arrival']}\n"
            f"⏱️ Duration: {selected_flight['duration']}\n"
            f"🔄 Stops: {selected_flight.get('stops', 0)}\n\n"
            f"*Route:*\n"
            f"📍 {search_info['origin'].title()} ({search_info['origin_code']}) → "
            f"{search_info['destination'].title()} ({search_info['destination_code']})\n"
            f"📅 Date: {search_info['date']}\n\n"
            f"👇 *Click below to complete your booking:*",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

        # Clear session
        db.clear_session(user_id)

    except ValueError:
        await update.message.reply_text(
            "❌ *Invalid input*\n\n"
            "Please send the *number* of the flight you want to select.\n"
            "Example: Send \"1\" to select the first flight.", 
            parse_mode='Markdown'
        )
        