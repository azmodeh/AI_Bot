import logging
from telethon import TelegramClient
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.errors import (
    ChannelInvalidError,
    ChannelPrivateError,
    UserNotParticipantError,
)

logger = logging.getLogger(__name__)


async def is_user_allowed(
    client: TelegramClient,
    user_id: int,
    sqlite_path: str,
) -> bool:
    """
    Check if user is a member of all required channels.
    Channels are loaded dynamically from database.
    
    Args:
        client: Telethon client instance
        user_id: User ID to check
        sqlite_path: Path to SQLite database
        
    Returns:
        True if user is allowed (member of all channels or no channels required)
    """
    from .db import get_channels
    
    required_channels = get_channels(sqlite_path)
    
    if not required_channels:
        return True
    
    for channel_ref in required_channels:
        try:
            channel = await client.get_entity(channel_ref)
            
            try:
                await client(GetParticipantRequest(
                    channel=channel,
                    participant=user_id
                ))
            except UserNotParticipantError:
                logger.info(f"User {user_id} is not a participant in {channel_ref}")
                return False
                
        except (ChannelInvalidError, ChannelPrivateError) as e:
            logger.warning(f"Channel {channel_ref} is invalid or private: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error checking channel {channel_ref}: {e}")
            return False
    
    return True
