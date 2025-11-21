import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def init_db(sqlite_path: str):
    """Initialize database"""
    db_path = Path(sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_ref TEXT NOT NULL UNIQUE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            ts TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_user_id 
        ON chat_memory(user_id, ts)
    """)
    
    conn.commit()
    conn.close()
    
    logger.info(f"Database initialized at {sqlite_path}")


def get_channels(sqlite_path: str):
    """Get all channels"""
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_ref FROM channels")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def add_chat_message(sqlite_path: str, user_id: int, role: str, content: str):
    """Add chat message to memory"""
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_memory (user_id, role, content, ts) VALUES (?, ?, ?, ?)",
        (user_id, role, content, now)
    )
    conn.commit()
    conn.close()


def get_chat_history(sqlite_path: str, user_id: int, limit: int = 10):
    """Get chat history for user"""
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content, ts FROM chat_memory WHERE user_id = ? ORDER BY ts DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in reversed(rows)]


def get_all_users(sqlite_path: str):
    """Get all users with their stats"""
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Create users table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_seen TEXT NOT NULL,
            last_activity TEXT NOT NULL,
            total_requests INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        SELECT user_id, first_seen, last_activity, total_requests 
        FROM users 
        ORDER BY last_activity DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_user_stats(sqlite_path: str, user_id: int):
    """Get stats for specific user"""
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_activity(sqlite_path: str, user_id: int):
    """Update user activity timestamp"""
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    # Create users table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_seen TEXT NOT NULL,
            last_activity TEXT NOT NULL,
            total_requests INTEGER DEFAULT 0
        )
    """)
    
    # Check if user exists
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    
    if exists:
        cursor.execute(
            "UPDATE users SET last_activity = ?, total_requests = total_requests + 1 WHERE user_id = ?",
            (now, user_id)
        )
    else:
        cursor.execute(
            "INSERT INTO users (user_id, first_seen, last_activity, total_requests) VALUES (?, ?, ?, 1)",
            (user_id, now, now)
        )
    
    conn.commit()
    conn.close()


def get_user_count(sqlite_path: str) -> int:
    """Get total user count"""
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    # Create users table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_seen TEXT NOT NULL,
            last_activity TEXT NOT NULL,
            total_requests INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_channel_id(sqlite_path: str) -> str:
    """Get configured channel ID"""
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    # Create config table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    
    cursor.execute("SELECT value FROM config WHERE key = 'required_channel'")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def set_channel_id(sqlite_path: str, channel_id: str):
    """Set required channel ID"""
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    # Create config table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    
    cursor.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES ('required_channel', ?)",
        (channel_id,)
    )
    conn.commit()
    conn.close()


def get_ai_stats(sqlite_path: str) -> dict:
    """Get AI usage statistics"""
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    # Create ai_stats table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL,
            success INTEGER DEFAULT 1,
            ts TEXT NOT NULL
        )
    """)
    
    stats = {
        'primary': 0,
        'fallback1': 0,
        'fallback2': 0,
        'failures': 0,
        'total': 0
    }
    
    cursor.execute("SELECT endpoint, COUNT(*) as count FROM ai_stats WHERE success = 1 GROUP BY endpoint")
    for row in cursor.fetchall():
        endpoint, count = row
        if endpoint == 'primary':
            stats['primary'] = count
        elif endpoint == 'fallback1':
            stats['fallback1'] = count
        elif endpoint == 'fallback2':
            stats['fallback2'] = count
    
    cursor.execute("SELECT COUNT(*) FROM ai_stats WHERE success = 0")
    stats['failures'] = cursor.fetchone()[0]
    
    stats['total'] = stats['primary'] + stats['fallback1'] + stats['fallback2']
    
    conn.close()
    return stats


def log_ai_request(sqlite_path: str, endpoint: str, success: bool):
    """Log AI request for statistics"""
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    # Create ai_stats table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint TEXT NOT NULL,
            success INTEGER DEFAULT 1,
            ts TEXT NOT NULL
        )
    """)
    
    cursor.execute(
        "INSERT INTO ai_stats (endpoint, success, ts) VALUES (?, ?, ?)",
        (endpoint, 1 if success else 0, now)
    )
    conn.commit()
    conn.close()


def clear_old_cache(sqlite_path: str, days: int = 7) -> int:
    """Clear old cache entries"""
    from datetime import timedelta
    
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    # Clear old chat memory
    cursor.execute("DELETE FROM chat_memory WHERE ts < ?", (cutoff,))
    deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    return deleted
