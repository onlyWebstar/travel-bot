"""
handlers/preferences_handler.py - Complete User Preferences Management
FIXED: Removed Markdown parsing issues
"""

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from database.models import SessionLocal, User, Preferences
from datetime import datetime

# Conversation states
CITY, BUDGET, AIRLINE_PREF = range(3)

class PreferencesHandler:
    def __init__(self):
        self.db = SessionLocal()
    
    async def check_and_prompt_preferences(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check if user needs to set preferences"""
        user_id = update.effective_user.id
        
        try:
            user = self.db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                await self.start_preference_collection(update, context)
                return True
            
            prefs = self.db.query(Preferences).filter(Preferences.user_id == user_id).first()
            if not prefs:
                await self.start_preference_collection(update, context)
                return True
                
            return False
            
        except Exception as e:
            print(f"❌ Error checking preferences: {e}")
            return False
        finally:
            self.db.close()
    
    async def start_preference_collection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start collecting user preferences"""
        user_name = update.effective_user.first_name
        
        await update.message.reply_text(
            f"👋 Welcome, {user_name}! Let me help you set up your travel preferences.\n\n"
            "📍 What city are you usually traveling from?\n"
            "(e.g., Lagos, London, New York)"
        )
        return CITY
    
    async def collect_city(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Collect user's default city"""
        user_city = update.message.text.strip().title()
        context.user_data['home_city'] = user_city
        
        budget_keyboard = [
            ['💰 Budget (< $500)', '💵 Mid-range ($500-$1500)'],
            ['💎 Premium (> $1500)', '⏭️ Skip']
        ]
        reply_markup = ReplyKeyboardMarkup(budget_keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"✅ Got it! You're traveling from {user_city}\n\n"
            "💰 What's your typical travel budget?",
            reply_markup=reply_markup
        )
        return BUDGET
    
    async def collect_budget(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Collect user's budget preference"""
        budget_text = update.message.text
        
        budget_mapping = {
            '💰 Budget (< $500)': {'min': 0, 'max': 500},
            '💵 Mid-range ($500-$1500)': {'min': 500, 'max': 1500},
            '💎 Premium (> $1500)': {'min': 1500, 'max': 10000},
            '⏭️ Skip': None
        }
        
        context.user_data['budget'] = budget_mapping.get(budget_text, None)
        
        airline_keyboard = [
            ['Emirates', 'British Airways', 'Lufthansa'],
            ['Air France', 'Turkish Airlines', 'KLM'],
            ['⏭️ No preference']
        ]
        reply_markup = ReplyKeyboardMarkup(airline_keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "✈️ Do you have any preferred airlines?\n(Select one or skip)",
            reply_markup=reply_markup
        )
        return AIRLINE_PREF
    
    async def collect_airline(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Collect airline preference and save all preferences"""
        airline_text = update.message.text
        
        if airline_text != '⏭️ No preference':
            context.user_data['preferred_airline'] = airline_text
        else:
            context.user_data['preferred_airline'] = None
        
        await self.save_preferences(update, context)
        
        await update.message.reply_text(
            "✅ All set! Your preferences have been saved.\n\n"
            "🤖 I'll learn more about your preferences as you search.\n"
            "You can update them anytime with /preferences\n\n"
            "Now, how can I help you today?",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    async def save_preferences(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Save collected preferences to database"""
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name
        username = update.effective_user.username
        
        try:
            user = self.db.query(User).filter(User.user_id == user_id).first()
            if not user:
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name
                )
                self.db.add(user)
                self.db.commit()
            
            prefs = self.db.query(Preferences).filter(Preferences.user_id == user_id).first()
            
            home_city = context.user_data.get('home_city', 'Lagos')
            budget = context.user_data.get('budget')
            airline = context.user_data.get('preferred_airline')
            
            if prefs:
                prefs.preferred_airlines = airline if airline else ''
                if budget:
                    prefs.set_budget_ranges(budget)
                prefs.updated_at = datetime.now()
            else:
                prefs = Preferences(
                    user_id=user_id,
                    preferred_airlines=airline if airline else ''
                )
                if budget:
                    prefs.set_budget_ranges(budget)
                self.db.add(prefs)
            
            budget_data = prefs.get_budget_ranges() if budget else {}
            budget_data['home_city'] = home_city
            prefs.set_budget_ranges(budget_data)
            
            self.db.commit()
            print(f"✅ Saved preferences for user {user_id}")
            
        except Exception as e:
            print(f"❌ Error saving preferences: {e}")
            self.db.rollback()
        finally:
            self.db.close()
    
    async def show_preferences(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Display current user preferences - FIXED VERSION"""
        user_id = update.effective_user.id
        
        try:
            prefs = self.db.query(Preferences).filter(Preferences.user_id == user_id).first()
            
            if not prefs:
                await update.message.reply_text(
                    "❌ No preferences found. Let's set them up!\n\n"
                    "Use /update_preferences to get started."
                )
                return
            
            budget_data = prefs.get_budget_ranges()
            home_city = budget_data.get('home_city', 'Not set')
            
            if 'min' in budget_data and 'max' in budget_data:
                budget_range = f"${budget_data['min']} - ${budget_data['max']}"
            else:
                budget_range = 'Not set'
            
            airline = prefs.preferred_airlines or 'No preference'
            
            # Plain text - no Markdown to avoid parsing errors
            pref_text = (
                "⚙️ YOUR TRAVEL PREFERENCES\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📍 Home City: {home_city}\n"
                f"💰 Budget Range: {budget_range}\n"
                f"✈️ Preferred Airline: {airline}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "To update: /update_preferences\n"
                "To clear: /clear_preferences"
            )
            
            await update.message.reply_text(pref_text)
            
        except Exception as e:
            print(f"❌ Error showing preferences: {e}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text(
                "❌ Error loading preferences.\n\n"
                "Try /update_preferences to set them again."
            )
        finally:
            self.db.close()
    
    async def cancel_preferences(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel preference collection"""
        await update.message.reply_text(
            "❌ Preference setup cancelled. You can start again with /preferences",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END


# Helper functions
def get_user_home_city(user_id):
    """Get user's home city from preferences"""
    db = SessionLocal()
    try:
        prefs = db.query(Preferences).filter(Preferences.user_id == user_id).first()
        if prefs:
            budget_data = prefs.get_budget_ranges()
            return budget_data.get('home_city', 'Lagos')
        return 'Lagos'
    except Exception as e:
        print(f"❌ Error getting home city: {e}")
        return 'Lagos'
    finally:
        db.close()


def get_user_budget(user_id):
    """Get user's budget preference"""
    db = SessionLocal()
    try:
        prefs = db.query(Preferences).filter(Preferences.user_id == user_id).first()
        if prefs:
            budget_data = prefs.get_budget_ranges()
            if 'min' in budget_data and 'max' in budget_data:
                return budget_data
        return None
    except Exception as e:
        print(f"❌ Error getting budget: {e}")
        return None
    finally:
        db.close()


# Additional Commands
async def clear_preferences_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete all user preferences"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    db = SessionLocal()
    
    try:
        prefs = db.query(Preferences).filter(Preferences.user_id == user_id).first()
        
        if not prefs:
            await update.message.reply_text(
                "ℹ️ You don't have any preferences set yet.\n\n"
                "Use /start to set up your preferences!"
            )
            return
        
        db.delete(prefs)
        db.commit()
        
        await update.message.reply_text(
            f"✅ Preferences Cleared!\n\n"
            f"Hi {user_name}, your travel preferences have been deleted.\n\n"
            f"You can:\n"
            f"• Set new preferences with /update_preferences\n"
            f"• Start fresh with /start\n"
            f"• Continue searching (I'll use defaults)",
            reply_markup=ReplyKeyboardRemove()
        )
        
        print(f"✅ Cleared preferences for user {user_id}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error clearing preferences: {e}")
        await update.message.reply_text(
            "❌ An error occurred while clearing your preferences.\n"
            "Please try again later."
        )
    finally:
        db.close()


async def reset_preferences_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset preferences to defaults"""
    user_id = update.effective_user.id
    
    db = SessionLocal()
    
    try:
        prefs = db.query(Preferences).filter(Preferences.user_id == user_id).first()
        
        if prefs:
            prefs.preferred_airlines = ''
            prefs.set_budget_ranges({
                'home_city': 'Lagos',
                'min': 0,
                'max': 10000
            })
            db.commit()
            
            await update.message.reply_text(
                "🔄 Preferences Reset!\n\n"
                "Your preferences have been reset to defaults:\n\n"
                "📍 Home City: Lagos\n"
                "💰 Budget: Any\n"
                "✈️ Airlines: No preference\n\n"
                "Use /update_preferences to customize again."
            )
        else:
            await update.message.reply_text(
                "ℹ️ You don't have any preferences yet.\n\n"
                "Use /start to set up!"
            )
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error resetting preferences: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")
    finally:
        db.close()


async def view_learning_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show what the bot has learned"""
    user_id = update.effective_user.id
    
    try:
        from handlers.preference_learning import get_user_learning_summary
        summary = get_user_learning_summary(user_id)
        await update.message.reply_text(summary)
        
    except Exception as e:
        print(f"❌ Error showing learning: {e}")
        await update.message.reply_text(
            "❌ Unable to retrieve learning data.\n\n"
            "You need at least 3 searches before I can learn your patterns!"
        )