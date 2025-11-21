"""
Anti-Spam Security System with Rate Limiting
Enforces 3-minute cooldown per user for AI requests
"""

import sqlite3
import time
import logging
from typing import Tuple, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

# In-memory tracking for adaptive cooldown
# Structure: {user_id: [timestamp1, timestamp2, ...]}
spam_attempts: Dict[int, list] = {}

# Adaptive cooldown tracking
# Structure: {user_id: cooldown_seconds}
adaptive_cooldowns: Dict[int, int] = {}

# Default cooldown in seconds
DEFAULT_COOLDOWN = 180  # 3 minutes
ADAPTIVE_COOLDOWN = 360  # 6 minutes
SPAM_WINDOW = 10  # seconds
SPAM_THRESHOLD = 3  # attempts


def init_rate_limiter_table(sqlite_path: str) -> None:
    """
    Initialize rate_limiter table in database.
    
    Args:
        sqlite_path: Path to SQLite database
    """
    try:
        db_path = Path(sqlite_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limiter (
                user_id INTEGER PRIMARY KEY,
                last_call_ts INTEGER NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("Rate limiter table initialized")
        
    except Exception as e:
        logger.exception(f"Failed to initialize rate_limiter table: {e}")
        raise


def check_rate_limit(user_id: int, sqlite_path: str) -> Tuple[bool, int]:
    """
    Check if user is allowed to make an AI request.
    
    Args:
        user_id: Telegram user ID
        sqlite_path: Path to SQLite database
        
    Returns:
        Tuple of (allowed: bool, remaining_seconds: int)
        - (True, 0) if request is allowed
        - (False, remaining_seconds) if user must wait
    """
    try:
        now = int(time.time())
        
        # Check for adaptive cooldown
        cooldown = adaptive_cooldowns.get(user_id, DEFAULT_COOLDOWN)
        
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        # Get last call timestamp
        cursor.execute("""
            SELECT last_call_ts FROM rate_limiter
            WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        
        if row is None:
            # First request from this user - allow it
            cursor.execute("""
                INSERT INTO rate_limiter (user_id, last_call_ts)
                VALUES (?, ?)
            """, (user_id, now))
            
            conn.commit()
            conn.close()
            
            logger.info(f"[SEC] User {user_id} first AI request - allowed")
            return (True, 0)
        
        last_call_ts = row[0]
        elapsed = now - last_call_ts
        
        if elapsed < cooldown:
            # User must wait
            remaining = cooldown - elapsed
            
            # Track spam attempts
            _track_spam_attempt(user_id, now)
            
            conn.close()
            
            logger.warning(f"[SEC] User {user_id} rate-limited. Remaining={remaining}s, Cooldown={cooldown}s")
            return (False, remaining)
        
        # Request is allowed - update timestamp
        cursor.execute("""
            UPDATE rate_limiter
            SET last_call_ts = ?
            WHERE user_id = ?
        """, (now, user_id))
        
        conn.commit()
        conn.close()
        
        # Reset adaptive cooldown on successful request
        if user_id in adaptive_cooldowns:
            del adaptive_cooldowns[user_id]
            logger.info(f"[SEC] User {user_id} adaptive cooldown reset")
        
        logger.info(f"[SEC] User {user_id} AI request allowed")
        return (True, 0)
        
    except Exception as e:
        logger.exception(f"[SEC] Error checking rate limit for user {user_id}: {e}")
        # On error, allow the request (fail-open for better UX)
        return (True, 0)


def _track_spam_attempt(user_id: int, now: int) -> None:
    """
    Track spam attempts and activate adaptive cooldown if needed.
    
    Args:
        user_id: Telegram user ID
        now: Current timestamp
    """
    try:
        # Initialize tracking for this user if needed
        if user_id not in spam_attempts:
            spam_attempts[user_id] = []
        
        # Add current attempt
        spam_attempts[user_id].append(now)
        
        # Clean old attempts (outside spam window)
        spam_attempts[user_id] = [
            ts for ts in spam_attempts[user_id]
            if now - ts <= SPAM_WINDOW
        ]
        
        # Check if spam threshold exceeded
        if len(spam_attempts[user_id]) >= SPAM_THRESHOLD:
            # Activate adaptive cooldown
            if user_id not in adaptive_cooldowns:
                adaptive_cooldowns[user_id] = ADAPTIVE_COOLDOWN
                logger.error(f"[SEC] User {user_id} triggered adaptive cooldown (6 minutes)")
                logger.warning(f"[SEC] User {user_id} hit rate limit {len(spam_attempts[user_id])} times in {SPAM_WINDOW}s")
            
            # Clear spam attempts after triggering
            spam_attempts[user_id] = []
    
    except Exception as e:
        logger.exception(f"[SEC] Error tracking spam attempt for user {user_id}: {e}")


def get_user_cooldown_status(user_id: int, sqlite_path: str) -> dict:
    """
    Get detailed cooldown status for a user (for debugging/monitoring).
    
    Args:
        user_id: Telegram user ID
        sqlite_path: Path to SQLite database
        
    Returns:
        Dict with status information
    """
    try:
        now = int(time.time())
        cooldown = adaptive_cooldowns.get(user_id, DEFAULT_COOLDOWN)
        
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT last_call_ts FROM rate_limiter
            WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return {
                "user_id": user_id,
                "has_record": False,
                "cooldown_seconds": cooldown,
                "is_adaptive": user_id in adaptive_cooldowns,
            }
        
        last_call_ts = row[0]
        elapsed = now - last_call_ts
        remaining = max(0, cooldown - elapsed)
        
        return {
            "user_id": user_id,
            "has_record": True,
            "last_call_ts": last_call_ts,
            "elapsed_seconds": elapsed,
            "remaining_seconds": remaining,
            "cooldown_seconds": cooldown,
            "is_adaptive": user_id in adaptive_cooldowns,
            "can_request": remaining == 0,
        }
        
    except Exception as e:
        logger.exception(f"Error getting cooldown status for user {user_id}: {e}")
        return {"error": str(e)}


def reset_user_rate_limit(user_id: int, sqlite_path: str) -> bool:
    """
    Reset rate limit for a specific user (admin function).
    
    Args:
        user_id: Telegram user ID
        sqlite_path: Path to SQLite database
        
    Returns:
        True if reset successful, False otherwise
    """
    try:
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM rate_limiter
            WHERE user_id = ?
        """, (user_id,))
        
        conn.commit()
        conn.close()
        
        # Clear adaptive cooldown
        if user_id in adaptive_cooldowns:
            del adaptive_cooldowns[user_id]
        
        # Clear spam attempts
        if user_id in spam_attempts:
            del spam_attempts[user_id]
        
        logger.info(f"[SEC] Rate limit reset for user {user_id}")
        return True
        
    except Exception as e:
        logger.exception(f"Error resetting rate limit for user {user_id}: {e}")
        return False


def get_rate_limit_stats(sqlite_path: str) -> dict:
    """
    Get overall rate limiter statistics (for monitoring).
    
    Args:
        sqlite_path: Path to SQLite database
        
    Returns:
        Dict with statistics
    """
    try:
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM rate_limiter")
        total_users = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_tracked_users": total_users,
            "users_with_adaptive_cooldown": len(adaptive_cooldowns),
            "users_with_recent_spam_attempts": len(spam_attempts),
            "default_cooldown_seconds": DEFAULT_COOLDOWN,
            "adaptive_cooldown_seconds": ADAPTIVE_COOLDOWN,
        }
        
    except Exception as e:
        logger.exception(f"Error getting rate limit stats: {e}")
        return {"error": str(e)}
