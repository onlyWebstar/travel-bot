"""
cache_scheduler.py - Automatic Cache Cleanup & Management
Place this file in: utils/cache_scheduler.py

Provides automated cache maintenance and monitoring
"""

import asyncio
from datetime import datetime, timedelta
from api.cache import get_cache_manager, cleanup_cache, cache_stats
from telegram import Update
from telegram.ext import ContextTypes
import threading
import time

class CacheScheduler:
    """Automated cache maintenance scheduler"""
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.running = False
        self.cleanup_thread = None
    
    def start_cleanup_scheduler(self, interval_hours: int = 6):
        """
        Start automatic cache cleanup every N hours
        
        Args:
            interval_hours: Hours between cleanups (default: 6)
        """
        if self.running:
            print("⚠️ Cache scheduler already running")
            return
        
        self.running = True
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            args=(interval_hours,),
            daemon=True
        )
        self.cleanup_thread.start()
        print(f"✅ Cache cleanup scheduler started (every {interval_hours} hours)")
    
    def _cleanup_loop(self, interval_hours: int):
        """Background loop for cache cleanup"""
        while self.running:
            try:
                # Wait for the specified interval
                time.sleep(interval_hours * 3600)
                
                # Perform cleanup
                deleted = cleanup_cache()
                
                # Get stats after cleanup
                stats = cache_stats()
                
                print(f"""
🧹 Automatic Cache Cleanup Complete
   - Deleted: {deleted} expired entries
   - Active entries: {stats.get('active_entries', 0)}
   - Memory cache: {stats.get('memory_cache_size', 0)} items
   - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""")
                
            except Exception as e:
                print(f"❌ Cache cleanup error: {e}")
    
    def stop_scheduler(self):
        """Stop the cleanup scheduler"""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        print("✅ Cache scheduler stopped")


# Global scheduler instance
_scheduler = None

def get_scheduler() -> CacheScheduler:
    """Get or create global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = CacheScheduler()
    return _scheduler

def start_cache_scheduler(interval_hours: int = 6):
    """Start the global cache scheduler"""
    scheduler = get_scheduler()
    scheduler.start_cleanup_scheduler(interval_hours)

def stop_cache_scheduler():
    """Stop the global cache scheduler"""
    scheduler = get_scheduler()
    scheduler.stop_scheduler()


# Telegram Bot Commands for Cache Management

async def cache_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cache_stats - Show cache statistics
    Admin command to view cache performance
    """
    try:
        stats = cache_stats()
        
        message = f"""
📊 *Cache Statistics*

*Database Cache:*
• Total Entries: {stats.get('total_entries', 0)}
• Active Entries: {stats.get('active_entries', 0)}
• Expired Entries: {stats.get('expired_entries', 0)}

*Memory Cache:*
• In-Memory Items: {stats.get('memory_cache_size', 0)}

*By Provider:*
"""
        
        by_provider = stats.get('by_provider', {})
        if by_provider:
            for provider, count in by_provider.items():
                message += f"• {provider}: {count}\n"
        else:
            message += "• No entries yet\n"
        
        message += f"\n_Last checked: {datetime.now().strftime('%H:%M:%S')}_"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting cache stats: {e}")

async def cache_clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cache_clear - Clear all cache (Admin only)
    """
    user_id = update.effective_user.id
    
    # Add your admin user IDs here
    ADMIN_IDS = []  # e.g., [123456789, 987654321]
    
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ This command is only available to administrators.")
        return
    
    try:
        # Parse arguments
        args = context.args
        provider = args[0] if args else None
        
        if provider:
            deleted = get_cache_manager().invalidate_cache(provider=provider)
            await update.message.reply_text(
                f"✅ Cleared {deleted} cache entries for provider: {provider}",
                parse_mode='Markdown'
            )
        else:
            deleted = get_cache_manager().invalidate_cache()
            await update.message.reply_text(
                f"✅ Cleared all {deleted} cache entries",
                parse_mode='Markdown'
            )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error clearing cache: {e}")

async def cache_cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cache_cleanup - Manually trigger cache cleanup
    """
    try:
        deleted = cleanup_cache()
        stats = cache_stats()
        
        message = f"""
🧹 *Cache Cleanup Complete*

• Removed: {deleted} expired entries
• Active entries: {stats.get('active_entries', 0)}
• Memory cache: {stats.get('memory_cache_size', 0)} items

_Time: {datetime.now().strftime('%H:%M:%S')}_
"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error during cleanup: {e}")


# Cache Performance Monitoring

class CacheMonitor:
    """Monitor cache hit/miss rates"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.start_time = datetime.now()
    
    def record_hit(self):
        """Record a cache hit"""
        self.hits += 1
    
    def record_miss(self):
        """Record a cache miss"""
        self.misses += 1
    
    def get_hit_rate(self) -> float:
        """Calculate cache hit rate percentage"""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100
    
    def get_stats(self) -> dict:
        """Get monitoring statistics"""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.get_hit_rate(),
            'uptime': (datetime.now() - self.start_time).total_seconds() / 3600
        }
    
    def reset(self):
        """Reset statistics"""
        self.hits = 0
        self.misses = 0
        self.start_time = datetime.now()


# Global monitor instance
_monitor = CacheMonitor()

def get_cache_monitor() -> CacheMonitor:
    """Get global cache monitor"""
    return _monitor

async def cache_monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cache_monitor - Show cache performance metrics
    """
    try:
        monitor = get_cache_monitor()
        stats = monitor.get_stats()
        
        message = f"""
📈 *Cache Performance Metrics*

*Hit/Miss Statistics:*
• Cache Hits: {stats['hits']}
• Cache Misses: {stats['misses']}
• Hit Rate: {stats['hit_rate']:.1f}%

*Performance:*
• Uptime: {stats['uptime']:.1f} hours
• Avg Requests: {(stats['hits'] + stats['misses']) / max(stats['uptime'], 0.1):.1f}/hour

_Real-time monitoring since bot start_
"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting monitor stats: {e}")