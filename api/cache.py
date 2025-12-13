"""
cache.py - Intelligent API Response Caching System
Place this file in: api/cache.py

Implements a multi-layer caching strategy:
1. In-memory cache (fastest, short-lived)
2. Database cache (persistent, medium-duration)
3. Smart cache invalidation based on time and search patterns
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from database.models import SessionLocal, APICache

class CacheManager:
    """
    Manages API response caching to reduce external API calls
    and improve response times
    """
    
    def __init__(self):
        self.db = SessionLocal()
        # In-memory cache for ultra-fast lookups
        self._memory_cache = {}
        # Cache TTL configurations (in minutes)
        self.cache_ttl = {
            'flight': 60,      # Flights: 1 hour
            'hotel': 120,      # Hotels: 2 hours
            'airport': 10080,  # Airport codes: 7 days
            'token': 25        # API tokens: 25 minutes
        }
    
    def _generate_cache_key(self, provider: str, params: Dict[str, Any]) -> str:
        """
        Generate unique cache key from provider and parameters
        
        Args:
            provider: API provider name (e.g., 'amadeus_flights')
            params: Search parameters dictionary
            
        Returns:
            Unique cache key string
        """
        # Sort params to ensure consistent keys
        sorted_params = json.dumps(params, sort_keys=True)
        # Create hash for shorter keys
        param_hash = hashlib.md5(sorted_params.encode()).hexdigest()
        return f"{provider}:{param_hash}"
    
    def get_cached_response(self, provider: str, params: Dict[str, Any]) -> Optional[Dict]:
        """
        Retrieve cached API response if valid
        
        Args:
            provider: API provider name
            params: Search parameters
            
        Returns:
            Cached response data or None if not found/expired
        """
        cache_key = self._generate_cache_key(provider, params)
        
        # 1. Check in-memory cache first (fastest)
        if cache_key in self._memory_cache:
            cached_item = self._memory_cache[cache_key]
            if cached_item['expires_at'] > datetime.now():
                print(f"✅ Cache HIT (Memory): {provider}")
                return cached_item['data']
            else:
                # Remove expired item from memory
                del self._memory_cache[cache_key]
        
        # 2. Check database cache (persistent)
        try:
            cache_entry = self.db.query(APICache).filter(
                APICache.cache_key == cache_key
            ).first()
            
            if cache_entry and cache_entry.expires_at > datetime.now():
                # Parse response data
                response_data = cache_entry.get_response_data()
                
                # Store in memory for faster future access
                self._memory_cache[cache_key] = {
                    'data': response_data,
                    'expires_at': cache_entry.expires_at
                }
                
                print(f"✅ Cache HIT (Database): {provider}")
                return response_data
            
            # If expired, delete from database
            if cache_entry:
                self.db.delete(cache_entry)
                self.db.commit()
                
        except Exception as e:
            print(f"⚠️ Cache retrieval error: {e}")
            self.db.rollback()
        
        print(f"❌ Cache MISS: {provider}")
        return None
    
    def save_to_cache(self, provider: str, params: Dict[str, Any], 
                     response_data: Dict, cache_type: str = 'flight') -> bool:
        """
        Save API response to cache
        
        Args:
            provider: API provider name
            params: Search parameters
            response_data: API response to cache
            cache_type: Type of cache (flight, hotel, airport, token)
            
        Returns:
            True if saved successfully, False otherwise
        """
        cache_key = self._generate_cache_key(provider, params)
        
        # Calculate expiration time
        ttl_minutes = self.cache_ttl.get(cache_type, 60)
        expires_at = datetime.now() + timedelta(minutes=ttl_minutes)
        
        try:
            # 1. Save to memory cache
            self._memory_cache[cache_key] = {
                'data': response_data,
                'expires_at': expires_at
            }
            
            # 2. Save to database cache
            cache_entry = self.db.query(APICache).filter(
                APICache.cache_key == cache_key
            ).first()
            
            if cache_entry:
                # Update existing entry
                cache_entry.set_response_data(response_data)
                cache_entry.expires_at = expires_at
            else:
                # Create new entry
                cache_entry = APICache(
                    cache_key=cache_key,
                    provider=provider,
                    expires_at=expires_at
                )
                cache_entry.set_response_data(response_data)
                self.db.add(cache_entry)
            
            self.db.commit()
            print(f"✅ Cached response for {provider} (TTL: {ttl_minutes}m)")
            return True
            
        except Exception as e:
            print(f"❌ Cache save error: {e}")
            self.db.rollback()
            return False
        finally:
            self.db.close()
    
    def invalidate_cache(self, provider: Optional[str] = None, 
                        cache_key: Optional[str] = None) -> int:
        """
        Manually invalidate cache entries
        
        Args:
            provider: Provider to invalidate (None = all)
            cache_key: Specific key to invalidate
            
        Returns:
            Number of entries invalidated
        """
        try:
            if cache_key:
                # Delete specific cache entry
                deleted = self.db.query(APICache).filter(
                    APICache.cache_key == cache_key
                ).delete()
                
                # Remove from memory cache
                if cache_key in self._memory_cache:
                    del self._memory_cache[cache_key]
                    
            elif provider:
                # Delete all entries for provider
                deleted = self.db.query(APICache).filter(
                    APICache.provider == provider
                ).delete()
                
                # Clear relevant memory cache entries
                self._memory_cache = {
                    k: v for k, v in self._memory_cache.items()
                    if not k.startswith(provider)
                }
            else:
                # Delete all cache entries
                deleted = self.db.query(APICache).delete()
                self._memory_cache.clear()
            
            self.db.commit()
            print(f"✅ Invalidated {deleted} cache entries")
            return deleted
            
        except Exception as e:
            print(f"❌ Cache invalidation error: {e}")
            self.db.rollback()
            return 0
        finally:
            self.db.close()
    
    def cleanup_expired_cache(self) -> int:
        """
        Remove all expired cache entries from database
        
        Returns:
            Number of entries cleaned up
        """
        try:
            deleted = self.db.query(APICache).filter(
                APICache.expires_at < datetime.now()
            ).delete()
            
            self.db.commit()
            
            if deleted > 0:
                print(f"🧹 Cleaned up {deleted} expired cache entries")
            
            # Also clean memory cache
            current_time = datetime.now()
            self._memory_cache = {
                k: v for k, v in self._memory_cache.items()
                if v['expires_at'] > current_time
            }
            
            return deleted
            
        except Exception as e:
            print(f"❌ Cache cleanup error: {e}")
            self.db.rollback()
            return 0
        finally:
            self.db.close()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about cache usage
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            total_entries = self.db.query(APICache).count()
            
            # Count by provider
            providers = self.db.query(
                APICache.provider
            ).distinct().all()
            
            provider_counts = {}
            for (provider,) in providers:
                count = self.db.query(APICache).filter(
                    APICache.provider == provider
                ).count()
                provider_counts[provider] = count
            
            # Count expired entries
            expired_count = self.db.query(APICache).filter(
                APICache.expires_at < datetime.now()
            ).count()
            
            return {
                'total_entries': total_entries,
                'memory_cache_size': len(self._memory_cache),
                'expired_entries': expired_count,
                'active_entries': total_entries - expired_count,
                'by_provider': provider_counts
            }
            
        except Exception as e:
            print(f"❌ Error getting cache stats: {e}")
            return {}
        finally:
            self.db.close()
    
    def get_or_fetch(self, provider: str, params: Dict[str, Any], 
                    fetch_function, cache_type: str = 'flight') -> Optional[Dict]:
        """
        Get from cache or fetch from API if not cached
        
        Args:
            provider: API provider name
            params: Search parameters
            fetch_function: Async function to call if cache miss
            cache_type: Type of cache for TTL
            
        Returns:
            Response data from cache or API
        """
        # Try to get from cache
        cached_response = self.get_cached_response(provider, params)
        
        if cached_response is not None:
            return cached_response
        
        # Cache miss - we'll need to fetch
        # Note: This method returns None if cache miss
        # The actual fetch should be handled by the caller
        return None


# Singleton instance
_cache_manager = None

def get_cache_manager() -> CacheManager:
    """Get or create singleton cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


# Convenience functions
def get_cached(provider: str, params: Dict[str, Any]) -> Optional[Dict]:
    """Quick access to get cached response"""
    return get_cache_manager().get_cached_response(provider, params)

def save_cache(provider: str, params: Dict[str, Any], 
               response_data: Dict, cache_type: str = 'flight') -> bool:
    """Quick access to save to cache"""
    return get_cache_manager().save_to_cache(provider, params, response_data, cache_type)

def clear_cache(provider: Optional[str] = None) -> int:
    """Quick access to clear cache"""
    return get_cache_manager().invalidate_cache(provider)

def cleanup_cache() -> int:
    """Quick access to cleanup expired cache"""
    return get_cache_manager().cleanup_expired_cache()

def cache_stats() -> Dict[str, Any]:
    """Quick access to cache statistics"""
    return get_cache_manager().get_cache_stats()