import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class BotSettings:
    api_id: int
    api_hash: str
    bot_token: str
    ai_provider: str
    ai_endpoint_url: str
    ai_auth_key: str
    ai_model_id: str
    ai_fallback_provider: str
    ai_fallback_url: str
    ai_fallback_key: str
    ai_fallback_model_id: str
    ai_fallback2_provider: str
    ai_fallback2_url: str
    ai_fallback2_key: str
    ai_fallback2_model_id: str
    locale: str
    messages_file_path: str
    temp_dir: str
    sqlite_path: str
    teacher_ids: List[int] = None
    admin_ids: List[int] = None


def load_settings() -> BotSettings:
    """Load bot settings from environment"""
    
    # Get project root (parent of src directory)
    project_root = Path(__file__).parent.parent.parent.absolute()
    
    api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    ai_provider = os.getenv("AI_PROVIDER", "openai")
    ai_endpoint_url = os.getenv("AI_ENDPOINT_URL", "")
    ai_auth_key = os.getenv("AI_AUTH_KEY", "")
    ai_model_id = os.getenv("AI_MODEL_ID", "")
    
    ai_fallback_provider = os.getenv("AI_FALLBACK_PROVIDER", "openai")
    ai_fallback_url = os.getenv("AI_FALLBACK_URL", "")
    ai_fallback_key = os.getenv("AI_FALLBACK_KEY", "")
    ai_fallback_model_id = os.getenv("AI_FALLBACK_MODEL_ID", "")
    
    ai_fallback2_provider = os.getenv("AI_FALLBACK2_PROVIDER", "openai")
    ai_fallback2_url = os.getenv("AI_FALLBACK2_URL", "")
    ai_fallback2_key = os.getenv("AI_FALLBACK2_KEY", "")
    ai_fallback2_model_id = os.getenv("AI_FALLBACK2_MODEL_ID", "")
    
    locale = os.getenv("BOT_LOCALE", "fa")
    messages_file_path = os.getenv("MESSAGES_FILE_PATH", str(project_root / "config" / "messages.fa.json"))
    temp_dir = os.getenv("TEMP_DIR", str(project_root / "temp"))
    sqlite_path = os.getenv("SQLITE_PATH", str(project_root / "data" / "db" / "Ai.db"))
    
    teacher_ids_str = os.getenv("TEACHER_IDS", "")
    teacher_ids = [int(x.strip()) for x in teacher_ids_str.split(",") if x.strip()]
    
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
    
    return BotSettings(
        api_id=api_id,
        api_hash=api_hash,
        bot_token=bot_token,
        ai_provider=ai_provider,
        ai_endpoint_url=ai_endpoint_url,
        ai_auth_key=ai_auth_key,
        ai_model_id=ai_model_id,
        ai_fallback_provider=ai_fallback_provider,
        ai_fallback_url=ai_fallback_url,
        ai_fallback_key=ai_fallback_key,
        ai_fallback_model_id=ai_fallback_model_id,
        ai_fallback2_provider=ai_fallback2_provider,
        ai_fallback2_url=ai_fallback2_url,
        ai_fallback2_key=ai_fallback2_key,
        ai_fallback2_model_id=ai_fallback2_model_id,
        locale=locale,
        messages_file_path=messages_file_path,
        temp_dir=temp_dir,
        sqlite_path=sqlite_path,
        teacher_ids=teacher_ids,
        admin_ids=admin_ids
    )


def load_messages(locale: str, messages_file_path: str) -> dict:
    """Load messages from JSON file"""
    try:
        with open(messages_file_path, "r", encoding="utf-8") as f:
            messages = json.load(f)
        logger.info(f"Loaded {len(messages)} messages from {messages_file_path}")
        return messages
    except Exception as e:
        logger.error(f"Failed to load messages: {e}")
        return {}
