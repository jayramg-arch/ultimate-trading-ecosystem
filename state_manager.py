import os
import json
import logging
from filelock import FileLock, Timeout

logger = logging.getLogger(__name__)

class StateManager:
    """
    Handles atomic JSON reads/writes with file locking.
    Prevents corruption when multiple agents (e.g. screener, exit engine)
    try to update state files concurrently.
    """
    
    @staticmethod
    def load_json(file_path: str, default_val=None) -> dict:
        if default_val is None:
            default_val = {}
            
        if not os.path.exists(file_path):
            return default_val
            
        lock_path = file_path + ".lock"
        lock = FileLock(lock_path, timeout=5)
        
        try:
            with lock:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Timeout:
            logger.error(f"Timeout acquiring lock for reading {file_path}")
            return default_val
        except json.JSONDecodeError:
            logger.error(f"Corrupt JSON in {file_path}, returning default")
            return default_val
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return default_val

    @staticmethod
    def save_json(file_path: str, data: dict) -> bool:
        lock_path = file_path + ".lock"
        lock = FileLock(lock_path, timeout=5)
        temp_path = file_path + ".tmp"
        
        try:
            with lock:
                # Write to temp file first
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)
                    f.flush()
                    os.fsync(f.fileno())
                
                # Atomic replace
                os.replace(temp_path, file_path)
            return True
        except Timeout:
            logger.error(f"Timeout acquiring lock for writing {file_path}")
            return False
        except Exception as e:
            logger.error(f"Error writing {file_path}: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return False
