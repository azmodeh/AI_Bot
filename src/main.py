import logging
import asyncio
import sys
from pathlib import Path
from telethon import TelegramClient, events, Button
from telethon.tl.custom import Message
from dotenv import load_dotenv

# Add src directory to path for imports
src_dir = Path(__file__).parent.absolute()
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from utils.config_loader import load_settings, load_messages
from utils.logger import configure_logging
from utils.db import init_db, get_channels, add_chat_message, get_chat_history
from utils.spam_filter import initialize_spam_filter, get_spam_filter
from utils.queue_manager import (
    initialize_queue,
    get_queue,
    start_workers,
    AIJob
)
from utils.chat_handler import process_chat_message
from utils.ai_connector import generate_final_explanation
from utils.admin_panel import (
    admin_command_handler,
    admin_callback_handler,
    admin_text_handler
)
from utils.db import update_user_activity

logger = logging.getLogger(__name__)

# Get project root and load config
project_root = Path(__file__).parent.parent.absolute()
load_dotenv(dotenv_path=project_root / 'config' / 'config.env')

settings = None
messages = None
client = None
user_states = {}


async def process_ai_job(job: AIJob):
    """
    Process an AI job from the queue.
    
    Args:
        job: AIJob instance containing user_id, job_type, payload, message_id
    """
    try:
        logger.info(f"[JOB_PROCESSOR] Processing {job.job_type} job for user {job.user_id}")
        
        if job.job_type == "photo":
            await process_photo_job(job)
        elif job.job_type == "chat":
            await process_chat_job(job)
        else:
            logger.error(f"[JOB_PROCESSOR] Unknown job type: {job.job_type}")
            
    except Exception as e:
        logger.exception(f"[JOB_PROCESSOR] Error processing job: {e}")
        try:
            await client.send_message(job.user_id, messages["ai_error"])
        except:
            pass


async def process_photo_job(job: AIJob):
    """Process a photo analysis job"""
    user_id = job.user_id
    message = job.payload["message"]
    mode = job.payload.get("mode", "before")
    
    try:
        image_url = f"tg://message_{message.id}"
        
        ai_result = await generate_final_explanation(
            image_url,
            message,
            settings,
            mode=mode
        )
        
        if ai_result is None:
            await client.send_message(user_id, messages["ai_error"])
            return
        
        caption = ai_result["text"]
        if len(caption) > 1000:
            caption = caption[:997] + "..."
        
        # Add buttons for user actions
        buttons = [
            [
                Button.inline("📸 تحلیل عکس جدید", b"NEW_PHOTO"),
                Button.inline("💬 چت با ربات", b"START_CHAT_MODE")
            ],
            [
                Button.inline("🔙 منوی اصلی", b"BACK_TO_MENU")
            ]
        ]
        
        await client.send_file(
            user_id,
            message.media,
            caption=caption,
            buttons=buttons
        )
        
        logger.info(f"[PHOTO_JOB] Completed for user {user_id}")
        
    except Exception as e:
        logger.exception(f"[PHOTO_JOB] Error: {e}")
        await client.send_message(user_id, messages["ai_error"])


async def process_chat_job(job: AIJob):
    """Process a chat message job"""
    user_id = job.user_id
    user_message = job.payload["message_text"]
    
    try:
        ai_response = await process_chat_message(
            user_id,
            user_message,
            settings.sqlite_path,
            settings
        )
        
        if ai_response is None:
            await client.send_message(user_id, messages["ai_error"])
            return
        
        await client.send_message(user_id, ai_response)
        
        logger.info(f"[CHAT_JOB] Completed for user {user_id}")
        
    except Exception as e:
        logger.exception(f"[CHAT_JOB] Error: {e}")
        await client.send_message(user_id, messages["ai_error"])


async def start_handler(event: events.NewMessage.Event):
    """Handle /start command"""
    try:
        user_id = event.sender_id
        logger.info(f"[START] User {user_id} sent /start")
        
        # Update user activity
        update_user_activity(settings.sqlite_path, user_id)
        
        if user_id in user_states:
            del user_states[user_id]
        
        keyboard = [
            [
                Button.inline(messages["start_photo_button"], b"START_PHOTO_MODE"),
                Button.inline(messages["start_chat_button"], b"START_CHAT_MODE")
            ]
        ]
        
        await event.respond(messages["start"], buttons=keyboard)
        
    except Exception as e:
        logger.exception(f"Error in start_handler: {e}")


async def start_mode_callback_handler(event: events.CallbackQuery.Event):
    """Handle mode selection callbacks"""
    try:
        data = event.data.decode("utf-8")
        user_id = event.sender_id
        
        if data == "START_PHOTO_MODE":
            user_states[user_id] = "photo_mode"
            await event.answer()
            await event.edit(messages["photo_mode_prompt"])
            logger.info(f"User {user_id} entered photo mode")
            
        elif data == "START_CHAT_MODE":
            user_states[user_id] = "CHAT_MODE"
            await event.answer()
            await event.edit(messages["chat_mode_welcome"])
            logger.info(f"User {user_id} entered CHAT_MODE")
            
        elif data == "NEW_PHOTO":
            user_states[user_id] = "photo_mode"
            await event.answer()
            await event.respond(messages["photo_mode_prompt"])
            logger.info(f"User {user_id} requested new photo analysis")
            
        elif data == "BACK_TO_MENU":
            if user_id in user_states:
                del user_states[user_id]
            await event.answer()
            
            keyboard = [
                [
                    Button.inline(messages["start_photo_button"], b"START_PHOTO_MODE"),
                    Button.inline(messages["start_chat_button"], b"START_CHAT_MODE")
                ]
            ]
            await event.respond(messages["start"], buttons=keyboard)
            logger.info(f"User {user_id} returned to main menu")
            
    except Exception as e:
        logger.exception(f"Error in start_mode_callback_handler: {e}")
        await event.answer(messages["generic_error"], alert=True)


async def photo_handler(event: events.NewMessage.Event):
    """Handle photo messages"""
    try:
        user_id = event.sender_id
        
        # Update user activity
        update_user_activity(settings.sqlite_path, user_id)
        
        if user_id in user_states and user_states[user_id] == "CHAT_MODE":
            await event.respond(messages["chat_mode_no_photo"])
            return
        
        spam_filter = get_spam_filter()
        if spam_filter.check_spam(user_id):
            await event.respond(messages["spam_detected"])
            return
        
        queue = get_queue()
        
        job = AIJob(
            user_id=user_id,
            job_type="photo",
            payload={"message": event.message, "mode": "before"},
            message_id=event.message.id
        )
        
        position = await queue.enqueue(job)
        
        if position > 4:
            await event.respond(messages["queue_notification"].format(position=position))
        
        logger.info(f"[PHOTO] Enqueued for user {user_id}, position {position}")
        
    except Exception as e:
        logger.exception(f"Error in photo_handler: {e}")
        await event.respond(messages["generic_error"])


async def text_handler(event: events.NewMessage.Event):
    """Handle text messages"""
    try:
        user_id = event.sender_id
        
        # Update user activity
        update_user_activity(settings.sqlite_path, user_id)
        
        # Check for admin text handler
        await admin_text_handler(event, settings, settings.sqlite_path)
        
        if user_id in user_states and user_states[user_id] == "CHAT_MODE":
            spam_filter = get_spam_filter()
            if spam_filter.check_spam(user_id):
                await event.respond(messages["spam_detected"])
                return
            
            queue = get_queue()
            
            job = AIJob(
                user_id=user_id,
                job_type="chat",
                payload={"message_text": event.text.strip()},
                message_id=event.message.id
            )
            
            position = await queue.enqueue(job)
            
            if position > 4:
                await event.respond(messages["queue_notification"].format(position=position))
            
            async with client.action(user_id, 'typing'):
                await asyncio.sleep(0.5)
            
            logger.info(f"[CHAT] Enqueued for user {user_id}, position {position}")
            return
        
        await event.respond(messages["non_photo"])
        
    except Exception as e:
        logger.exception(f"Error in text_handler: {e}")


def main():
    global settings, messages, client
    
    configure_logging()
    logger.info("Starting AI Bot with Queue System...")
    
    settings = load_settings()
    messages = load_messages(settings.locale, settings.messages_file_path)
    logger.info(f"Loaded {len(messages)} message keys")
    
    init_db(settings.sqlite_path)
    
    channels_count = len(get_channels(settings.sqlite_path))
    logger.info(f"Loaded {channels_count} required channels")
    
    Path(settings.temp_dir).mkdir(parents=True, exist_ok=True)
    
    initialize_spam_filter(max_messages=5, time_window=2.0)
    logger.info("Spam filter initialized")
    
    initialize_queue(max_concurrent_jobs=3)
    logger.info("Queue initialized with 3 workers")
    
    session_path = project_root / "data" / "sessions" / "lash_ai_session"
    logger.info(f"Session path: {session_path}")
    client = TelegramClient(str(session_path), settings.api_id, settings.api_hash)
    
    # Admin handlers
    async def admin_handler(event):
        await admin_command_handler(event, settings)
    
    async def admin_callback(event):
        await admin_callback_handler(event, settings, settings.sqlite_path)
    
    # Register handlers
    client.on(events.NewMessage(pattern=r"^/start$"))(start_handler)
    client.on(events.NewMessage(pattern=r"^/admin$"))(admin_handler)
    client.on(events.NewMessage(func=lambda e: e.photo and not e.text.startswith("/")))(photo_handler)
    client.on(events.NewMessage(func=lambda e: not e.photo and not e.text.startswith("/")))(text_handler)
    client.on(events.CallbackQuery(pattern=r"^(START_|NEW_|BACK_)"))(start_mode_callback_handler)
    client.on(events.CallbackQuery(pattern=r"^ADMIN:"))(admin_callback)
    
    logger.info("Starting Telegram client...")
    
    async def start_bot():
        await client.start(bot_token=settings.bot_token)
        await start_workers(process_ai_job)
        logger.info("Bot is running with queue workers...")
        await client.run_until_disconnected()
    
    client.loop.run_until_complete(start_bot())


if __name__ == "__main__":
    main()
