import logging
from typing import Optional
import requests

from .config_loader import BotSettings
from .db import log_ai_request
from . import ai_adapter

logger = logging.getLogger(__name__)


def call_ai_with_fallback(payload: dict, settings: BotSettings, sqlite_path: str = None) -> Optional[dict]:
    """
    Call AI API with 3-layer fallback system.
    
    ANY error → fallback immediately.
    PRIMARY/SECONDARY never return None, only TERTIARY can.
    """
    endpoints = [
        ("PRIMARY", "primary", settings.ai_provider, settings.ai_endpoint_url, settings.ai_auth_key, settings.ai_model_id),
        ("SECONDARY", "fallback1", settings.ai_fallback_provider, settings.ai_fallback_url, settings.ai_fallback_key, settings.ai_fallback_model_id),
        ("TERTIARY", "fallback2", settings.ai_fallback2_provider, settings.ai_fallback2_url, settings.ai_fallback2_key, settings.ai_fallback2_model_id),
    ]
    
    for layer_name, stat_name, provider, endpoint_url, auth_key, model_id in endpoints:
        if not endpoint_url or not auth_key:
            continue
        
        try:
            request_url = ai_adapter.get_request_url(provider, endpoint_url, model_id, auth_key)
            headers = ai_adapter.get_headers(provider, auth_key)
            current_payload = ai_adapter.convert_payload(payload, provider)
            
            logger.info(f"[AI] Calling {layer_name} ({provider})")
            
            response = requests.post(request_url, json=current_payload, headers=headers, timeout=8)
            
            if response.status_code != 200:
                if layer_name == "PRIMARY":
                    logger.warning("[AI] PRIMARY FAILED — switching to fallback")
                elif layer_name == "SECONDARY":
                    logger.warning("[AI] SECONDARY FAILED — switching to fallback")
                if sqlite_path:
                    log_ai_request(sqlite_path, stat_name, False)
                continue
            
            result = response.json()
            unified_result = ai_adapter.convert_response(result, provider)
            
            if "choices" not in unified_result or not unified_result["choices"]:
                if layer_name == "PRIMARY":
                    logger.warning("[AI] PRIMARY FAILED — switching to fallback")
                elif layer_name == "SECONDARY":
                    logger.warning("[AI] SECONDARY FAILED — switching to fallback")
                if sqlite_path:
                    log_ai_request(sqlite_path, stat_name, False)
                continue
            
            logger.info(f"[AI] ✓✓✓ {layer_name} SUCCESS")
            if sqlite_path:
                log_ai_request(sqlite_path, stat_name, True)
            return unified_result
            
        except Exception:
            if layer_name == "PRIMARY":
                logger.warning("[AI] PRIMARY FAILED — switching to fallback")
            elif layer_name == "SECONDARY":
                logger.warning("[AI] SECONDARY FAILED — switching to fallback")
            continue
    
    logger.critical("[AI] ALL FAILED")
    if sqlite_path:
        log_ai_request(sqlite_path, "failure", False)
    return None


async def generate_final_explanation(
    image_url: str,
    message,
    settings: BotSettings,
    mode: str,
    previous_analysis=None,
) -> Optional[dict]:
    """Generate explanation using external AI API."""
    try:
        analysis_text = """
        لطفاً این تصویر چشم را برای اکستنشن مژه تحلیل کن و موارد زیر را مشخص کن:
        - شکل چشم
        - نوع پلک
        - استایل پیشنهادی
        - کرل مناسب
        - طول‌های پیشنهادی
        - یک ایده 
        توضیحات را به زبان فارسی و در حداکثر 700 کاراکتر بنویس.
        """
        
        try:
            from io import BytesIO
            import base64
            
            buffer = BytesIO()
            await message.download_media(file=buffer)
            image_bytes = buffer.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Unified internal payload (OpenAI-style)
            # Adapter will convert to provider-specific format
            payload = {
                "model": settings.ai_model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": analysis_text
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to process image: {e}")
            # Text-only fallback
            payload = {
                "model": settings.ai_model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": analysis_text
                    }
                ]
            }
        
        # Get sqlite_path from settings if available
        sqlite_path = getattr(settings, 'sqlite_path', None)
        result = call_ai_with_fallback(payload, settings, sqlite_path)
        
        if result is None:
            return None
        
        ai_text = ""
        if "choices" in result and len(result["choices"]) > 0:
            ai_text = result["choices"][0]["message"]["content"]
        
        return {
            "text": ai_text,
            "eye_shape": None,
            "recommended_style": None,
            "final_style": None,
        }
        
    except Exception as e:
        logger.exception(f"Error: {e}")
        return None
