from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.request import HTTPXRequest
from config import Config
from handlers.flight_handlers import handle_flight_request, handle_flight_selection
from handlers.hotel_handlers import handle_hotel_request, handle_hotel_selection
from handlers.preferences_handler import (
    PreferencesHandler, 
    CITY, BUDGET, AIRLINE_PREF,
    clear_preferences_command,
    reset_preferences_command,
    view_learning_command
)
from utils.nlp_processor import extract_travel_info
from database.models import init_db
from database.session_manager import SessionManager

# Cache management imports
from utils.cache_scheduler import (
    start_cache_scheduler,
    cache_stats_command,
    cache_clear_command,
    cache_cleanup_command,
    cache_monitor_command
)

# Initialize preferences handler
pref_handler = PreferencesHandler()

# 1. Define the setup function FIRST
async def post_init_setup(application):
    """Sets the bot's command list for the Telegram menu."""
    commands = [
        BotCommand("start", "Welcome message and setup"),
        BotCommand("flights", "Search for flights"),
        BotCommand("hotels", "Search for hotels"),
        BotCommand("preferences", "View your preferences"),
        BotCommand("update_preferences", "Update preferences"),
        BotCommand("clear_preferences", "Delete all preferences"),
        BotCommand("my_learning", "What the bot learned about you"),
        BotCommand("cache_stats", "View cache statistics"),
        BotCommand("help", "Show help guide")
    ]
    await application.bot.set_my_commands(commands)
    print("✅ Bot commands menu set.")

# Initializing bot with timeout fix
t_request = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0)

# 2. Application Initialization
application = (
    Application.builder()
    .token(Config.TELEGRAM_TOKEN)
    .request(t_request)
    .post_init(post_init_setup)
    .build()
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message - check if user needs to set preferences"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # Check if this is a new user
    needs_setup = await pref_handler.check_and_prompt_preferences(update, context)
    
    if needs_setup:
        # Preference setup initiated
        return CITY
    
    # Existing user - show welcome
    welcome_text = f"""
👋 *Welcome back, {user_name}!* 🧳

I am your smart travel assistant!

✈️ **Flight Search** - With typo correction
🏨 **Hotel Search** - Personalized results
⚙️ **Smart Preferences** - Learns from you
🚀 **Lightning-fast** - Intelligent caching

*Try these:*
• "Flights to London"
• "Hotels in Paris for 3 nights"
• "Fly to Dubai tomorrow"

I'll handle typos and suggest corrections! 😊
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 *Travel Bot Help*

*Search Commands:*
/flights - Search for flights
/hotels - Search for hotels

*Preference Commands:*
/preferences - View preferences
/update_preferences - Update preferences
/clear_preferences - Delete all preferences
/my_learning - See what I learned

*Cache Commands:*
/cache_stats - Cache performance
/cache_cleanup - Clean expired cache

*Natural Language Search:*
Just type what you need:
• "Flights to London"
• "Hotels in Dubai for 2 nights"
• "Fly to Paris tomorrow"

*Smart Features:*
✅ Typo correction ("lodnon" → "London")
✅ Abbreviations ("LA" → "Los Angeles")
✅ Learning from your searches
✅ Budget filtering
✅ Instant cached results

*Tips:*
💡 I handle typos automatically
💡 I learn your preferences over time
💡 I suggest corrections if unsure
💡 Repeated searches are instant!
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced message handler with smart NLP error handling"""
    user_message = update.message.text
    user_id = update.effective_user.id
    
    if user_message.startswith('/'): 
        return
    
    # 1. Check Database for Active Session (Context Retention)
    try:
        selection_number = int(user_message.strip())
        db = SessionManager()
        session = db.get_active_session(user_id)
        
        if session:
            if session['type'] == 'flight':
                await handle_flight_selection(update, context)
                return
            elif session['type'] == 'hotel':
                await handle_hotel_selection(update, context)
                return
    except ValueError:
        pass 
        
    # 2. Extract Intent using Smart NLP
    travel_info = extract_travel_info(user_message)
    intent = travel_info['intent']
    
    # 3. Handle NLP Errors (FIXED!)
    if travel_info.get('error'):
        # NLP processor found an error - show it to user
        error_msg = f"❌ {travel_info['error']}"
        
        if travel_info.get('suggestion'):
            error_msg += f"\n\n💡 {travel_info['suggestion']}"
        
        await update.message.reply_text(error_msg, parse_mode='Markdown')
        return
    
    # 4. Handle Recognized Intents
    if intent == 'flight':
        await handle_flight_request(update, context)
    elif intent == 'hotel':
        await handle_hotel_request(update, context)
    else:
        # Only show generic help if NLP truly couldn't understand
        await update.message.reply_text(
            "🤔 *I'm not sure what you're looking for.*\n\n"
            "*Try these examples:*\n"
            "✈️ \"Flights to Paris\"\n"
            "🏨 \"Hotels in London\"\n"
            "📍 \"Fly to Dubai tomorrow\"\n\n"
            "Or use /help for more info",
            parse_mode='Markdown'
        )

# Preferences conversation handler
preferences_conv = ConversationHandler(
    entry_points=[
        CommandHandler("start", start),
        CommandHandler("update_preferences", pref_handler.start_preference_collection)
    ],
    states={
        CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, pref_handler.collect_city)],
        BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, pref_handler.collect_budget)],
        AIRLINE_PREF: [MessageHandler(filters.TEXT & ~filters.COMMAND, pref_handler.collect_airline)]
    },
    fallbacks=[CommandHandler("cancel", pref_handler.cancel_preferences)],
    allow_reentry=True
)

# Add handlers
application.add_handler(preferences_conv)
application.add_handler(CommandHandler("preferences", pref_handler.show_preferences))
application.add_handler(CommandHandler("clear_preferences", clear_preferences_command))
application.add_handler(CommandHandler("reset_preferences", reset_preferences_command))
application.add_handler(CommandHandler("my_learning", view_learning_command))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("flights", handle_flight_request))
application.add_handler(CommandHandler("hotels", handle_hotel_request))

# Cache management commands
application.add_handler(CommandHandler("cache_stats", cache_stats_command))
application.add_handler(CommandHandler("cache_clear", cache_clear_command))
application.add_handler(CommandHandler("cache_cleanup", cache_cleanup_command))
application.add_handler(CommandHandler("cache_monitor", cache_monitor_command))

# Main message handler - MUST BE LAST
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    # Initialize database
    init_db()
    
    # Start automatic cache cleanup (runs every 6 hours)
    start_cache_scheduler(interval_hours=6)
    
    print("🤖 TravelBot is starting...")
    print("✅ Smart NLP with typo correction enabled")
    print("✅ Preference collection enabled")
    print("✅ Intelligent API caching enabled")
    print("✅ Automatic cache cleanup scheduled")
    print("✅ Real booking links integrated")
    print("✅ 100+ cities recognized")
    print("✅ Fuzzy matching for error recovery")
    
    try:
        application.run_polling()
    except Exception as e:
        print(f"❌ Bot crashed: {e}")