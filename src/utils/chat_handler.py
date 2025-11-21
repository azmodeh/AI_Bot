import logging
from typing import Optional
import requests

from .config_loader import BotSettings
from .db import add_chat_message, get_chat_history, log_ai_request
from . import ai_adapter

logger = logging.getLogger(__name__)


def call_chat_ai_with_fallback(messages: list[dict], settings: BotSettings, sqlite_path: str = None) -> Optional[str]:
    """
    Call AI API for chat with 3-layer fallback system.
    TEXT-ONLY mode - no images.
    
    ANY error → fallback immediately.
    PRIMARY/SECONDARY never return None, only TERTIARY can.
    """
    endpoints = [
        ("PRIMARY", "primary", settings.ai_provider, settings.ai_endpoint_url, settings.ai_auth_key, settings.ai_model_id),
        ("SECONDARY", "fallback1", settings.ai_fallback_provider, settings.ai_fallback_url, settings.ai_fallback_key, settings.ai_fallback_model_id),
        ("TERTIARY", "fallback2", settings.ai_fallback2_provider, settings.ai_fallback2_url, settings.ai_fallback2_key, settings.ai_fallback2_model_id),
    ]
    
    # Build internal payload (OpenAI-style, TEXT-ONLY)
    internal_payload = {
        "model": settings.ai_model_id,
        "messages": messages
    }
    
    for layer_name, stat_name, provider, endpoint_url, auth_key, model_id in endpoints:
        if not endpoint_url or not auth_key:
            continue
        
        try:
            request_url = ai_adapter.get_request_url(provider, endpoint_url, model_id, auth_key)
            headers = ai_adapter.get_headers(provider, auth_key)
            converted_payload = ai_adapter.convert_payload(internal_payload, provider)
            
            logger.info(f"[CHAT_AI] Calling {layer_name} ({provider})")
            
            response = requests.post(request_url, json=converted_payload, headers=headers, timeout=8)
            
            if response.status_code != 200:
                if layer_name == "PRIMARY":
                    logger.warning("[CHAT_AI] PRIMARY FAILED — switching to fallback")
                elif layer_name == "SECONDARY":
                    logger.warning("[CHAT_AI] SECONDARY FAILED — switching to fallback")
                if sqlite_path:
                    log_ai_request(sqlite_path, stat_name, False)
                continue
            
            result = response.json()
            unified_result = ai_adapter.convert_response(result, provider)
            
            if "choices" not in unified_result or not unified_result["choices"]:
                if layer_name == "PRIMARY":
                    logger.warning("[CHAT_AI] PRIMARY FAILED — switching to fallback")
                elif layer_name == "SECONDARY":
                    logger.warning("[CHAT_AI] SECONDARY FAILED — switching to fallback")
                if sqlite_path:
                    log_ai_request(sqlite_path, stat_name, False)
                continue
            
            ai_text = unified_result["choices"][0]["message"]["content"]
            
            if not ai_text or not ai_text.strip():
                if layer_name == "PRIMARY":
                    logger.warning("[CHAT_AI] PRIMARY FAILED — switching to fallback")
                elif layer_name == "SECONDARY":
                    logger.warning("[CHAT_AI] SECONDARY FAILED — switching to fallback")
                if sqlite_path:
                    log_ai_request(sqlite_path, stat_name, False)
                continue
            
            logger.info(f"[CHAT_AI] ✓✓✓ {layer_name} SUCCESS")
            if sqlite_path:
                log_ai_request(sqlite_path, stat_name, True)
            return ai_text
            
        except Exception:
            if layer_name == "PRIMARY":
                logger.warning("[CHAT_AI] PRIMARY FAILED — switching to fallback")
            elif layer_name == "SECONDARY":
                logger.warning("[CHAT_AI] SECONDARY FAILED — switching to fallback")
            continue
    
    logger.critical("[CHAT_AI] ALL FAILED")
    if sqlite_path:
        log_ai_request(sqlite_path, "failure", False)
    return None


async def process_chat_message(
    user_id: int,
    user_message: str,
    sqlite_path: str,
    settings: BotSettings
) -> Optional[str]:
    """
    Process chat message with compressed history.
    
    Args:
        user_id: Telegram user ID
        user_message: User's text message
        sqlite_path: Path to SQLite database
        settings: Bot settings
        
    Returns:
        AI response text or None on failure
    """
    try:
        logger.info(f"[CHAT] User {user_id} sent message: {user_message[:50]}...")
        
        # Get last 10 messages from history (before adding new one)
        history = get_chat_history(sqlite_path, user_id, limit=10)
        
        # Compress history into single text block
        compressed_history = ""
        if history:
            compressed_history = "---chat history---\n"
            for msg in history:
                role = msg["role"]
                content = msg["content"]
                compressed_history += f"{role}: {content}\n"
            compressed_history += "---end of history---\n\n"
        
        # Combine compressed history with new user message
        combined_content = compressed_history + f"user: {user_message}"
        
        # Build messages array for AI
        messages = []
        
        # System prompt
        system_prompt = """تو یک متخصص زیبایی و اکستنشن مژه هستی که به هنرجویان کمک می‌کنی.
به سوالات درباره اکستنشن مژه، تکنیک‌ها، مراقبت و مشکلات رایج پاسخ بده.
پاسخ‌هایت باید به زبان فارسی، محاوره‌ای، مختصر (حداکثر 700 کاراکتر)، همراه با ایموجی، واضح و حرفه‌ای باشد.
اگر تاریخچه چت داده شد، از آن برای درک بهتر context استفاده کن."""
        
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Add single user message with compressed history + new message
        messages.append({
            "role": "user",
            "content": combined_content
        })
        
        logger.info(f"[CHAT] Sending {len(messages)} messages to AI (system + compressed history + user message)")
        logger.debug(f"[CHAT] History items: {len(history)}, Combined content length: {len(combined_content)}")
        
        # Call AI with fallback
        ai_response = call_chat_ai_with_fallback(messages, settings, sqlite_path)
        
        if ai_response is None:
            logger.error("[CHAT] All AI endpoints failed")
            return None
        
        # Save conversation to memory AFTER getting response
        add_chat_message(sqlite_path, user_id, "user", user_message)
        add_chat_message(sqlite_path, user_id, "assistant", ai_response)
        logger.info(f"[CHAT] AI responded with {len(ai_response)} characters")
        
        return ai_response
        
    except Exception as e:
        logger.exception(f"[CHAT] Error processing chat message: {e}")
        return None
