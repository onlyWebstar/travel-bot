from database.models import SessionLocal, UserSessionModel, Preferences, User
from datetime import datetime, timedelta
from collections import Counter
import json

class PreferenceLearner:
    """Learn user preferences from search history"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def analyze_search_history(self, user_id, limit=10):
        """Analyze recent searches to learn patterns"""
        try:
            # Get recent sessions
            sessions = self.db.query(UserSessionModel).filter(
                UserSessionModel.user_id == user_id
            ).order_by(
                UserSessionModel.created_at.desc()
            ).limit(limit).all()
            
            if not sessions:
                return None
            
            # Collect data from sessions
            destinations = []
            airlines = []
            price_ranges = []
            cities = []
            
            for session in sessions:
                context = session.get_context()
                search_info = context.get('data', {}).get('search_info', {})
                
                # Extract destinations
                if 'destination' in search_info:
                    destinations.append(search_info['destination'])
                
                # Extract origin cities
                if 'origin' in search_info:
                    cities.append(search_info['origin'])
                
                # Extract flight data for airlines
                if context.get('type') == 'flight':
                    flights = context.get('data', {}).get('flights', [])
                    for flight in flights:
                        if 'airline' in flight:
                            airlines.append(flight['airline'])
                        if 'price' in flight:
                            try:
                                # Extract numeric price
                                price_str = flight['price'].split()[-1]
                                price = float(price_str.replace(',', ''))
                                price_ranges.append(price)
                            except:
                                pass
            
            # Analyze patterns
            analysis = {
                'favorite_destinations': self._get_top_items(destinations, 3),
                'common_airlines': self._get_top_items(airlines, 3),
                'home_city': self._get_most_common(cities),
                'avg_price_range': self._calculate_price_range(price_ranges),
                'total_searches': len(sessions)
            }
            
            return analysis
            
        except Exception as e:
            print(f"❌ Error analyzing search history: {e}")
            return None
        finally:
            self.db.close()
    
    def _get_top_items(self, items, count=3):
        """Get top N most common items"""
        if not items:
            return []
        counter = Counter(items)
        return [item for item, _ in counter.most_common(count)]
    
    def _get_most_common(self, items):
        """Get single most common item"""
        if not items:
            return None
        counter = Counter(items)
        return counter.most_common(1)[0][0] if counter else None
    
    def _calculate_price_range(self, prices):
        """Calculate average price range from search history"""
        if not prices:
            return None
        
        avg_price = sum(prices) / len(prices)
        
        # Convert EUR to USD approximately
        avg_price_usd = avg_price * 1.1
        
        # Categorize
        if avg_price_usd < 500:
            return {'min': 0, 'max': 500, 'category': 'Budget'}
        elif avg_price_usd < 1500:
            return {'min': 500, 'max': 1500, 'category': 'Mid-range'}
        else:
            return {'min': 1500, 'max': 10000, 'category': 'Premium'}
    
    def update_preferences_from_learning(self, user_id):
        """Update user preferences based on learned patterns"""
        try:
            analysis = self.analyze_search_history(user_id)
            
            if not analysis or analysis['total_searches'] < 3:
                print(f"ℹ️ Not enough search history for user {user_id}")
                return False
            
            # Get or create preferences
            prefs = self.db.query(Preferences).filter(
                Preferences.user_id == user_id
            ).first()
            
            if not prefs:
                prefs = Preferences(user_id=user_id)
                self.db.add(prefs)
            
            # Update learned preferences
            updated = False
            
            # Update home city if detected
            if analysis['home_city']:
                budget_data = prefs.get_budget_ranges()
                if not budget_data.get('home_city') or budget_data.get('home_city') == 'Lagos':
                    budget_data['home_city'] = analysis['home_city']
                    budget_data['learned'] = True
                    prefs.set_budget_ranges(budget_data)
                    updated = True
            
            # Update airlines if we found common ones
            if analysis['common_airlines'] and not prefs.preferred_airlines:
                prefs.preferred_airlines = ', '.join(analysis['common_airlines'][:2])
                updated = True
            
            # Update budget range if learned
            if analysis['avg_price_range']:
                budget_data = prefs.get_budget_ranges()
                if not budget_data.get('min'):
                    budget_data.update(analysis['avg_price_range'])
                    budget_data['learned'] = True
                    prefs.set_budget_ranges(budget_data)
                    updated = True
            
            if updated:
                prefs.updated_at = datetime.now()
                self.db.commit()
                print(f"✅ Updated preferences for user {user_id} from learning")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error updating preferences: {e}")
            self.db.rollback()
            return False
        finally:
            self.db.close()
    
    def get_learning_summary(self, user_id):
        """Get a summary of what the bot has learned"""
        try:
            analysis = self.analyze_search_history(user_id)
            
            if not analysis:
                return "I haven't learned much about your preferences yet. Keep searching!"
            
            summary = "🧠 *What I've Learned About You:*\n\n"
            
            if analysis['total_searches']:
                summary += f"📊 *Total Searches:* {analysis['total_searches']}\n\n"
            
            if analysis['home_city']:
                summary += f"📍 *Most Common Origin:* {analysis['home_city']}\n"
            
            if analysis['favorite_destinations']:
                dests = ', '.join(analysis['favorite_destinations'])
                summary += f"✈️ *Favorite Destinations:* {dests}\n"
            
            if analysis['common_airlines']:
                airlines = ', '.join(analysis['common_airlines'])
                summary += f"🛫 *Common Airlines:* {airlines}\n"
            
            if analysis['avg_price_range']:
                category = analysis['avg_price_range']['category']
                summary += f"💰 *Budget Category:* {category}\n"
            
            summary += "\n_I'll use this to personalize your searches!_"
            
            return summary
            
        except Exception as e:
            print(f"❌ Error getting learning summary: {e}")
            return "Unable to retrieve learning data."
        finally:
            self.db.close()


# Helper function to trigger learning after searches
def trigger_learning(user_id):
    """Trigger preference learning after a search"""
    learner = PreferenceLearner()
    learner.update_preferences_from_learning(user_id)


# Helper function to get learning summary
def get_user_learning_summary(user_id):
    """Get what the bot has learned about the user"""
    learner = PreferenceLearner()
    return learner.get_learning_summary(user_id)