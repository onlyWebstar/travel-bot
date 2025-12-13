from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from utils.nlp_processor import extract_travel_info
from api.booking_client import search_hotels
from database.session_manager import SessionManager
# Store hotel results temporarily
user_hotel_data = {}

async def handle_hotel_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id

    # Extract information using NLP
    travel_info = extract_travel_info(user_message)

    # If command is /hotels but no destination specified
    if update.message.text == '/hotels':
        await update.message.reply_text(
            "🏨 *Hotel Search*\n\n"
            "Tell me where you want to stay!\n\n"
            "**Examples:**\n"
            "• \"Hotels in London\"\n"
            "• \"Stay in Paris for 3 nights\"\n"
            "• \"Book hotel in Dubai for 2 guests\"",
            parse_mode='Markdown'
        )
        return

    if travel_info['intent'] != 'hotel':
        if '/hotels' in user_message:
            travel_info['intent'] = 'hotel'
        else:
            return

    # Get destination
    destination = travel_info.get('destination')
    if not destination:
        await update.message.reply_text(
            "❓ *Where would you like to stay?*\n\n"
            "Please specify a destination:\n"
            "• \"Hotels in London\"\n"
            "• \"Stay in Paris\"\n"
            "• \"Book hotel in Dubai\"",
            parse_mode='Markdown'
        )
        return

    # Show searching message
    searching_msg = await update.message.reply_text(
        f"🔍 *Searching hotels...*\n"
        f"📍 **Location:** {destination}\n"
        f"👥 **Guests:** {travel_info.get('guests', 1)}\n"
        f"🛏️ **Rooms:** {travel_info.get('rooms', 1)}\n"
        f"Please wait ⏳",
        parse_mode='Markdown'
    )

    try:
        # Get hotels from Amadeus API
        check_in = travel_info.get('check_in', (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'))
        check_out = travel_info.get('check_out', (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'))
        guests = travel_info.get('guests', 1)
        rooms = travel_info.get('rooms', 1)

        hotels_data = await search_hotels(destination, check_in, check_out, guests, rooms)
        
        # Delete searching message
        await searching_msg.delete()

        # Handle API errors
        if isinstance(hotels_data, dict) and 'error' in hotels_data:
            await update.message.reply_text(
                "❌ *Service Temporarily Unavailable*\n\n"
                "The hotel search service is experiencing high demand. Please try again in a few minutes.",
                parse_mode='Markdown'
            )
            return

        # Handle no hotels found
        if not hotels_data:
            await update.message.reply_text(
                f"❌ *No Hotels Found*\n\n"
                f"No hotels available in {destination} for your dates.\n"
                f"Try different dates or location.",
                parse_mode='Markdown'
            )
            return

        # Store hotel data for this user
        user_hotel_data[user_id] = {
            'hotels': hotels_data,
            'search_info': {
                'destination': destination,
                'check_in': check_in,
                'check_out': check_out,
                'guests': guests,
                'rooms': rooms
            }
        }

        # Format hotel results with numbers
        message = f"🏨 **Hotels in {destination}**\n"
        message += f"📅 **Check-in:** {check_in} | **Check-out:** {check_out}\n"
        message += f"👥 **Guests:** {guests} | **Rooms:** {rooms}\n\n"

        for i, hotel in enumerate(hotels_data[:5], 1):
            message += (
                f"{i}. **{hotel['name']}** ⭐ {hotel.get('rating', 'N/A')}\n"
                f"   📍 {hotel.get('address', 'Address not available')}\n"
                f"   💰 **Price:** {hotel['price']} per night\n"
                f"   📞 **Contact:** {hotel.get('phone', 'N/A')}\n\n"
            )

        message += "**To book a hotel, reply with the number (1-5)**"

        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(
            "❌ *Search Failed*\n\n"
            "An unexpected error occurred. Please try again in a few moments.",
            parse_mode='Markdown'
        )
        print(f"Hotel search error: {e}")

async def handle_hotel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle when user selects a hotel number"""
    user_id = update.effective_user.id
    user_input = update.message.text.strip()

    db = SessionManager()
    session_data = db.get_active_session(user_id)

    # Check if valid session exists and is for flights
    if not session_data or session_data.get('type') != 'hotel':
        await update.message.reply_text(
            "❌ *No active hotel search*\n\n"
            "Please search for hotelss first.",
            parse_mode='Markdown'
        )
        return

    try:
        # Parse hotel number (1-5)
        hotel_number = int(user_input)
        if hotel_number < 1 or hotel_number > 5:
            raise ValueError("Number out of range")

        hotels = user_hotel_data[user_id]['hotels']
        search_info = user_hotel_data[user_id]['search_info']

        if hotel_number > len(hotels):
            await update.message.reply_text(
                f"❌ *Invalid selection*\n\n"
                f"Please choose a number between 1 and {len(hotels)}",
                parse_mode='Markdown'
            )
            return

        # Get selected hotel
        selected_hotel = hotels[hotel_number - 1]

        # Send booking confirmation
        await update.message.reply_text(
            f"✅ **Hotel Selected!**\n\n"
            f"🏨 **Hotel:** {selected_hotel['name']}\n"
            f"⭐ **Rating:** {selected_hotel.get('rating', 'N/A')}\n"
            f"📍 **Address:** {selected_hotel.get('address', 'N/A')}\n"
            f"📞 **Contact:** {selected_hotel.get('phone', 'N/A')}\n"
            f"💰 **Price:** {selected_hotel['price']} per night\n\n"
            f"**Check-in:** {search_info['check_in']}\n"
            f"**Check-out:** {search_info['check_out']}\n"
            f"**Guests:** {search_info['guests']}\n"
            f"**Rooms:** {search_info['rooms']}\n\n"
            f"To proceed with booking, please contact the hotel directly or visit our website.",
            parse_mode='Markdown'
        )

        # Clear the stored data
        del user_hotel_data[user_id]

    except ValueError:
        await update.message.reply_text(
            "❌ *Invalid input*\n\n"
            "Please reply with a number between 1 and 5 to select a hotel.",
            parse_mode='Markdown'
        )