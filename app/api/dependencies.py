"""
API Dependencies
Rate limiting and common dependencies
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import get_settings

# Initialize rate limiter
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


def get_limiter() -> Limiter:
    """Get the rate limiter instance"""
    return limiter
