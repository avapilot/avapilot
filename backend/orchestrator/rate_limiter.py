"""
Rate Limiter - Hybrid approach
- Short-term limits: In-memory (requests per minute)
- Long-term limits: Firestore (requests per month)
"""

from functools import wraps
from flask import request, jsonify, make_response
import time
from collections import defaultdict
from threading import Lock
from error_tracker import log_warning

# In-memory storage for short-term rate limiting
class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.lock = Lock()
        
        # Define rate limits per tier
        self.RATE_LIMITS = {
            "free": {
                "requests_per_minute": 20,
                "requests_per_day": 500
            },
            "paid": {
                "requests_per_minute": 100,
                "requests_per_day": 10000
            }
        }
        
        # Free tier API key (same for everyone during alpha)
        self.FREE_API_KEY = "avapilot_free_alpha"
        
        print(f"[RATE_LIMITER] Initialized with limits: {self.RATE_LIMITS}")
    
    def get_tier(self, api_key: str) -> str:
        """Determine user tier based on API key"""
        if api_key == self.FREE_API_KEY or not api_key:
            return "free"
        
        # Future: Check paid API keys in database
        return "free"
    
    def is_allowed(self, identifier: str, tier: str, window_seconds: int) -> tuple[bool, int, int]:
        """
        Check if request is allowed
        
        Returns:
            (allowed, retry_after, remaining_requests)
        """
        current_time = time.time()
        limit = self.RATE_LIMITS[tier]
        
        # Choose limit based on window
        if window_seconds == 60:  # Per minute
            max_requests = limit["requests_per_minute"]
        elif window_seconds == 86400:  # Per day
            max_requests = limit["requests_per_day"]
        else:
            max_requests = 20  # Default fallback
        
        with self.lock:
            # Clean old requests
            self.requests[identifier] = [
                t for t in self.requests[identifier]
                if current_time - t < window_seconds
            ]
            
            # Calculate remaining
            current_count = len(self.requests[identifier])
            remaining = max_requests - current_count
            
            # Check limit
            if current_count >= max_requests:
                oldest_request = min(self.requests[identifier])
                retry_after = int(window_seconds - (current_time - oldest_request))
                return False, retry_after, 0
            
            # Record this request
            self.requests[identifier].append(current_time)
            return True, 0, remaining - 1  # -1 because we just added one


limiter = RateLimiter()


def rate_limit(window_seconds=60):
    """
    Rate limit decorator - enforces per-minute limits
    Uses IP + API key combination as identifier
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get API key from request
            req_json = request.get_json(silent=True) or {}
            context = req_json.get('context', {})
            api_key = context.get('api_key', limiter.FREE_API_KEY)
            
            # Determine tier
            tier = limiter.get_tier(api_key)
            
            # Build identifier (IP + API key)
            ip = request.remote_addr
            identifier = f"{ip}:{api_key}"
            
            # Check rate limit
            allowed, retry_after, remaining = limiter.is_allowed(identifier, tier, window_seconds)
            
            if not allowed:
                limit = limiter.RATE_LIMITS[tier]
                
                log_warning(
                    "RATE_LIMIT_EXCEEDED",
                    f"User {identifier} exceeded rate limit",
                    context={
                        "identifier": identifier,
                        "tier": tier,
                        "limit": limit['requests_per_minute']
                    }
                )
                
                response = make_response(jsonify({
                    "error": "Rate limit exceeded",
                    "retry_after_seconds": retry_after,
                    "tier": tier,
                    "limit": f"{limit['requests_per_minute']}/min, {limit['requests_per_day']}/day",
                    "message": "You've reached the free tier limit. Upgrade for higher limits at https://avapilot.com/pricing"
                }), 429)
                
                # Add rate limit headers
                max_count = limiter.RATE_LIMITS[tier]["requests_per_minute"]
                response.headers['X-RateLimit-Limit'] = str(max_count)
                response.headers['X-RateLimit-Remaining'] = '0'
                response.headers['X-RateLimit-Reset'] = str(int(time.time() + retry_after))
                response.headers['X-RateLimit-Tier'] = tier
                
                return response
            
            # Call the actual endpoint
            result = f(*args, **kwargs)
            
            # Add rate limit headers to successful response
            if isinstance(result, tuple):
                response_obj, status_code = result
            else:
                response_obj = result
                status_code = 200
            
            # Convert to Response object if it's just a dict
            if not hasattr(response_obj, 'headers'):
                response_obj = make_response(response_obj, status_code)
            
            # Add headers
            max_count = limiter.RATE_LIMITS[tier]["requests_per_minute"]
            response_obj.headers['X-RateLimit-Limit'] = str(max_count)
            response_obj.headers['X-RateLimit-Remaining'] = str(remaining)
            response_obj.headers['X-RateLimit-Reset'] = str(int(time.time() + window_seconds))
            response_obj.headers['X-RateLimit-Tier'] = tier
            
            return response_obj
        
        return decorated_function
    return decorator