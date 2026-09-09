import time
import logging
from functools import wraps
from typing import Callable, Any
from dhan_auth import get_dhan_client

logger = logging.getLogger(__name__)

class DhanRateLimitExceeded(Exception):
    pass

class BrokerGateway:
    """
    A resilient wrapper around DhanHQ client with automatic retries,
    exponential backoff, and basic rate-limit throttling.
    """
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._client = get_dhan_client()

    def _execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        retries = 0
        while retries <= self.max_retries:
            try:
                response = func(*args, **kwargs)
                
                # Check for Dhan API specific failure responses
                if isinstance(response, dict):
                    status = response.get('status', '').lower()
                    if status == 'failure':
                        error_code = response.get('errorCode', '')
                        error_msg = str(response.get('remarks', ''))
                        
                        # Handle rate limits (429) or internal errors (500)
                        if 'rate limit' in error_msg.lower() or error_code in ['429', '500', '502', '503', '504']:
                            raise DhanRateLimitExceeded(f"API Error {error_code}: {error_msg}")
                            
                return response
                
            except (ConnectionError, TimeoutError, DhanRateLimitExceeded) as e:
                if retries == self.max_retries:
                    logger.error(f"[BrokerGateway] Max retries reached for {func.__name__}. Error: {e}")
                    raise
                
                # Exponential backoff
                delay = self.base_delay * (2 ** retries)
                logger.warning(f"[BrokerGateway] {e}. Retrying in {delay} seconds... ({retries+1}/{self.max_retries})")
                time.sleep(delay)
                retries += 1
                
            except Exception as e:
                # For non-transient errors (like invalid parameters), fail immediately
                logger.error(f"[BrokerGateway] Unhandled exception in {func.__name__}: {e}")
                raise

    def get_holdings(self):
        return self._execute_with_retry(self._client.get_holdings)

    def get_positions(self):
        return self._execute_with_retry(self._client.get_positions)

    def place_order(self, *args, **kwargs):
        return self._execute_with_retry(self._client.place_order, *args, **kwargs)

    def get_order_list(self):
        return self._execute_with_retry(self._client.get_order_list)

    def get_fund_limits(self):
        return self._execute_with_retry(self._client.get_fund_limits)

    def get_trade_history(self, from_date, to_date):
        return self._execute_with_retry(self._client.get_trade_history, from_date, to_date)
    
    # Expose the underlying client constants for convenience
    @property
    def NSE(self): return self._client.NSE
    @property
    def BSE(self): return self._client.BSE
    @property
    def BUY(self): return self._client.BUY
    @property
    def SELL(self): return self._client.SELL
    @property
    def LIMIT(self): return self._client.LIMIT
    @property
    def MARKET(self): return self._client.MARKET
    @property
    def CNC(self): return self._client.CNC
    @property
    def INTRADAY(self): return self._client.INTRADAY

# Singleton instance
_gateway_instance = None

def get_broker_gateway() -> BrokerGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = BrokerGateway()
    return _gateway_instance
