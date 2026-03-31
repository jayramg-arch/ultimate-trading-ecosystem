import json
import os
import time
import hashlib

CACHE_FILE = "ai_cache.json"

def _get_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=4)

def get_cached_response(key_data):
    """
    Retrieves a cached response if it exists and is less than 24 hours old.
    key_data: A string or dict used to generate a unique cache key.
    """
    key = str(key_data)
    if isinstance(key_data, dict):
        key = json.dumps(key_data, sort_keys=True)
    
    cache_key = hashlib.md5(key.encode()).hexdigest()
    cache = _get_cache()
    
    if cache_key in cache:
        entry = cache[cache_key]
        timestamp = entry.get("timestamp", 0)
        # 24 hour TTL (86400 seconds)
        if time.time() - timestamp < 86400:
            return entry.get("response")
            
    return None

def set_cached_response(key_data, response):
    """
    Saves a response to the local cache with a timestamp.
    """
    key = str(key_data)
    if isinstance(key_data, dict):
        key = json.dumps(key_data, sort_keys=True)
        
    cache_key = hashlib.md5(key.encode()).hexdigest()
    cache = _get_cache()
    
    cache[cache_key] = {
        "timestamp": time.time(),
        "response": response,
        "original_key": key # For debugging
    }
    
    _save_cache(cache)
