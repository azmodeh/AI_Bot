import logging
from typing import Dict
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


class SpamFilter:
    """
    Lightweight anti-spam filter to prevent rapid message flooding.
    
    Rules:
    - Tracks last 5 message timestamps per user
    - If 5 messages arrive within 2 seconds, reject as spam
    - Does NOT enforce time-based cooldown
    - Does NOT block normal usage
    - Only prevents abusive rapid flooding
    """
    
    def __init__(self, max_messages: int = 5, time_window: float = 2.0):
        self.max_messages = max_messages
        self.time_window = time_window
        self.user_timestamps: Dict[int, deque] = {}
        
        logger.info(f"[SPAM_FILTER] Initialized: max_messages={max_messages}, time_window={time_window}s")
    
    def check_spam(self, user_id: int) -> bool:
        """
        Check if a user is spamming.
        
        Args:
            user_id: User ID
            
        Returns:
            True if spam detected, False otherwise
        """
        now = datetime.utcnow()
        
        if user_id not in self.user_timestamps:
            self.user_timestamps[user_id] = deque(maxlen=self.max_messages)
        
        timestamps = self.user_timestamps[user_id]
        timestamps.append(now)
        
        if len(timestamps) < self.max_messages:
            return False
        
        oldest = timestamps[0]
        newest = timestamps[-1]
        time_diff = (newest - oldest).total_seconds()
        
        if time_diff <= self.time_window:
            logger.warning(f"[SPAM_FILTER] Spam detected: user={user_id}, {self.max_messages} messages in {time_diff:.2f}s")
            return True
        
        return False
    
    def reset_user(self, user_id: int):
        """Reset spam tracking for a user"""
        if user_id in self.user_timestamps:
            del self.user_timestamps[user_id]
            logger.debug(f"[SPAM_FILTER] Reset user: {user_id}")


global_spam_filter = None


def initialize_spam_filter(max_messages: int = 5, time_window: float = 2.0):
    """Initialize the global spam filter"""
    global global_spam_filter
    global_spam_filter = SpamFilter(max_messages, time_window)
    logger.info("[SPAM_FILTER] Global spam filter initialized")
    return global_spam_filter


def get_spam_filter():
    """Get the global spam filter instance"""
    if global_spam_filter is None:
        raise RuntimeError("Spam filter not initialized")
    return global_spam_filter
