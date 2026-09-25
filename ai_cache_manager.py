import json
import os
import time
import hashlib
import sqlite3

import journal_path as _jp  # AUD-INT-14: one owner of the journal location
DB_FILE = _jp.JOURNAL_DB

def _get_cache_from_db(cache_key):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT value FROM AICache WHERE key = ?", (cache_key,))
        row = c.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return None

def _save_cache_to_db(cache_key, entry):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO AICache (key, value) VALUES (?, ?)", (cache_key, json.dumps(entry)))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_cached_response(key_data):
    """
    Retrieves a cached response if it exists and is less than 24 hours old.
    key_data: A string or dict used to generate a unique cache key.
    """
    key = str(key_data)
    if isinstance(key_data, dict):
        key = json.dumps(key_data, sort_keys=True)
    
    cache_key = hashlib.md5(key.encode()).hexdigest()
    entry = _get_cache_from_db(cache_key)
    
    if entry:
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
    
    entry = {
        "timestamp": time.time(),
        "response": response,
        "original_key": key # For debugging
    }
    
    _save_cache_to_db(cache_key, entry)
