"""
AI Adapter Layer
Converts unified internal payload format to provider-specific formats
Config-driven approach - no hardcoded logic
"""

import logging
import json
import re
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Load provider config
_config = None

def load_config():
    """Load provider configuration from JSON file"""
    global _config
    if _config is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "ai_providers.json"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                _config = json.load(f)
            logger.info(f"[ADAPTER] Loaded config for {len(_config['providers'])} providers")
        except Exception as e:
            logger.error(f"[ADAPTER] Failed to load config: {e}")
            _config = {"providers": {}, "detection_rules": [], "format_converters": {}}
    return _config


def detect_provider(endpoint_url: str, model_id: str = None) -> str:
    """
    Detect AI provider from endpoint URL or model ID using config rules
    
    Returns: provider name or "unknown"
    """
    config = load_config()
    
    if not endpoint_url:
        return "unknown"
    
    url_lower = endpoint_url.lower()
    model_lower = model_id.lower() if model_id else ""
    
    # Check detection rules from config
    for rule in config.get("detection_rules", []):
        provider = rule["provider"]
        
        # Check URL patterns
        for pattern in rule.get("url_contains", []):
            if pattern.lower() in url_lower:
                logger.debug(f"[ADAPTER] Detected {provider} from URL pattern: {pattern}")
                return provider
        
        # Check model patterns
        for pattern in rule.get("model_contains", []):
            if pattern.lower() in model_lower:
                logger.debug(f"[ADAPTER] Detected {provider} from model pattern: {pattern}")
                return provider
    
    return "unknown"


def has_image_content(payload: Dict[str, Any]) -> bool:
    """Check if payload contains image content"""
    messages = payload.get("messages", [])
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "image_url":
                    return True
    return False


def convert_to_gemini(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert OpenAI-style payload to Gemini format.
    
    Handles both text-only and multimodal (text + image) payloads.
    """
    try:
        messages = payload.get("messages", [])
        parts = []
        
        for message in messages:
            role = message.get("role", "user")
            
            # Skip system messages for Gemini (they don't support system role)
            if role == "system":
                continue
            
            content = message.get("content")
            
            # Handle string content (text-only, like CHAT_MODE)
            if isinstance(content, str):
                if content.strip():
                    parts.append({"text": content})
            
            # Handle array content (multimodal, like PHOTO_MODE)
            elif isinstance(content, list):
                for item in content:
                    item_type = item.get("type")
                    
                    if item_type == "text":
                        text = item.get("text", "")
                        if text:
                            parts.append({"text": text})
                    
                    elif item_type == "image_url":
                        image_url = item.get("image_url", {}).get("url", "")
                        
                        # Extract base64 data from data URL
                        if image_url.startswith("data:"):
                            match = re.match(r'data:image/(\w+);base64,(.+)', image_url)
                            if match:
                                mime_type = match.group(1)
                                base64_data = match.group(2)
                                
                                parts.append({
                                    "inline_data": {
                                        "mime_type": f"image/{mime_type}",
                                        "data": base64_data
                                    }
                                })
        
        # If no parts, add a default text part
        if not parts:
            parts.append({"text": "Hello"})
        
        gemini_payload = {
            "contents": [
                {
                    "parts": parts
                }
            ]
        }
        
        has_image = has_image_content(payload)
        logger.debug(f"[ADAPTER] Converted to Gemini format: {len(parts)} parts (image: {has_image})")
        return gemini_payload
        
    except Exception as e:
        logger.error(f"[ADAPTER] Failed to convert to Gemini format: {e}")
        return {
            "contents": [
                {
                    "parts": [
                        {"text": "Error converting payload"}
                    ]
                }
            ]
        }





def convert_payload(payload: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """
    Convert unified internal payload to provider-specific format using config
    
    Args:
        payload: OpenAI-style payload (internal format)
        provider: Provider name from config
    
    Returns:
        Converted payload for the specific provider
    """
    config = load_config()
    provider_config = config["providers"].get(provider)
    
    if not provider_config:
        logger.warning(f"[ADAPTER] Unknown provider '{provider}', using OpenAI format")
        return payload
    
    request_format = provider_config.get("request_format", "openai")
    
    # Convert based on format
    if request_format == "gemini":
        converted = convert_to_gemini(payload)
    elif request_format == "openai":
        converted = payload.copy()
    else:
        logger.warning(f"[ADAPTER] Unknown format '{request_format}', using as-is")
        converted = payload.copy()
    
    # Add extra params if defined
    extra_params = provider_config.get("extra_params", {})
    if extra_params:
        converted.update(extra_params)
        logger.debug(f"[ADAPTER] Added extra params: {list(extra_params.keys())}")
    
    return converted


def convert_response(response: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """
    Convert provider-specific response to unified OpenAI-style format using config
    
    Args:
        response: Provider-specific response
        provider: Provider name
    
    Returns:
        OpenAI-style response with "choices" array
    """
    config = load_config()
    provider_config = config["providers"].get(provider)
    
    if not provider_config:
        return response
    
    response_format = provider_config.get("response_format", "openai")
    
    if response_format == "gemini":
        # Gemini response: {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
        # Convert to: {"choices": [{"message": {"content": "..."}}]}
        try:
            if "candidates" in response and len(response["candidates"]) > 0:
                text = response["candidates"][0]["content"]["parts"][0]["text"]
                return {
                    "choices": [
                        {
                            "message": {
                                "content": text
                            }
                        }
                    ]
                }
            else:
                logger.error("[ADAPTER] Invalid Gemini response structure")
                return response
        except (KeyError, IndexError) as e:
            logger.error(f"[ADAPTER] Failed to convert Gemini response: {e}")
            return response
    
    # OpenAI format - return as-is
    return response


def get_headers(provider: str, api_key: str) -> Dict[str, str]:
    """
    Get appropriate headers for provider using config
    
    Args:
        provider: Provider name
        api_key: API key
    
    Returns:
        Headers dict
    """
    config = load_config()
    provider_config = config["providers"].get(provider)
    
    if not provider_config:
        # Default to Bearer auth
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    headers = provider_config.get("headers", {}).copy()
    auth_type = provider_config.get("auth_type", "bearer")
    
    # Add auth header if needed
    if auth_type == "bearer":
        headers["Authorization"] = f"Bearer {api_key}"
    # For query_param auth (like Gemini), API key goes in URL, not headers
    
    return headers


def get_request_url(provider: str, endpoint_url: str, model_id: str, api_key: str) -> str:
    """
    Get the correct request URL for provider.
    
    Config URLs end at /v1, this function appends /chat/completions.
    
    Args:
        provider: Provider name
        endpoint_url: Base URL ending at /v1 (e.g., https://api.groq.com/openai/v1)
        model_id: Model ID
        api_key: API key
    
    Returns:
        Full request URL with /chat/completions appended
    """
    config = load_config()
    provider_config = config["providers"].get(provider)
    
    if not provider_config:
        # Default: append /chat/completions
        return f"{endpoint_url}/chat/completions"
    
    url_pattern = provider_config.get("url_pattern", "{endpoint_url}")
    
    # Replace placeholders
    url = url_pattern.format(
        endpoint_url=endpoint_url,
        model=model_id,
        api_key=api_key
    )
    
    # For OpenAI-style providers, append /chat/completions
    if provider in ["openai", "nvidia", "openrouter"]:
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
    
    return url
