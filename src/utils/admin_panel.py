"""
Admin Panel for Telegram Bot
Provides comprehensive admin controls and monitoring
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict
from telethon import events, Button
from telethon.tl.custom import Message

from .db import (
    get_all_users,
    get_user_stats,
    get_channel_id,
    set_channel_id,
    get_ai_stats,
    clear_old_cache,
    get_user_count
)
from .queue_manager import get_queue
from .config_loader import BotSettings

logger = logging.getLogger(__name__)

# Admin states
admin_states = {}


def is_admin(user_id: int, settings: BotSettings) -> bool:
    """Check if user is admin"""
    if not settings.admin_ids:
        return False
    return user_id in settings.admin_ids


def get_main_menu_keyboard():
    """Get main admin menu keyboard"""
    return [
        [
            Button.inline("👥 کاربران", b"ADMIN:USERS"),
            Button.inline("📢 کانال اجباری", b"ADMIN:CHANNEL")
        ],
        [
            Button.inline("🧵 صف پردازش", b"ADMIN:QUEUE"),
            Button.inline("📊 گزارش AI", b"ADMIN:AI_STATS")
        ],
        [
            Button.inline("🧹 پاک‌سازی", b"ADMIN:CLEANUP")
        ]
    ]


async def show_admin_menu(event, edit=False):
    """Show main admin menu"""
    text = "🔧 **پنل مدیریت**\n\nیکی از گزینه‌های زیر را انتخاب کنید:"
    keyboard = get_main_menu_keyboard()
    
    if edit:
        await event.edit(text, buttons=keyboard)
    else:
        await event.respond(text, buttons=keyboard)


async def show_users_page(event, sqlite_path: str, page: int = 0):
    """Show users list with pagination"""
    users = get_all_users(sqlite_path)
    
    if not users:
        await event.edit(
            "👥 **کاربران**\n\nهیچ کاربری ثبت نشده است.",
            buttons=[[Button.inline("🔙 بازگشت", b"ADMIN:MENU")]]
        )
        return
    
    per_page = 5
    total_pages = (len(users) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]
    
    text = f"👥 **کاربران** (صفحه {page + 1}/{total_pages})\n\n"
    
    for user in page_users:
        user_id = user['user_id']
        first_seen = user.get('first_seen', 'نامشخص')
        last_activity = user.get('last_activity', 'نامشخص')
        total_requests = user.get('total_requests', 0)
        
        text += f"**ID:** `{user_id}`\n"
        text += f"اولین بازدید: {first_seen}\n"
        text += f"آخرین فعالیت: {last_activity}\n"
        text += f"تعداد درخواست: {total_requests}\n"
        text += "─────────────\n"
    
    # Pagination buttons
    buttons = []
    nav_row = []
    
    if page > 0:
        nav_row.append(Button.inline("◀️ قبلی", f"ADMIN:USERS:{page-1}".encode()))
    
    if page < total_pages - 1:
        nav_row.append(Button.inline("بعدی ▶️", f"ADMIN:USERS:{page+1}".encode()))
    
    if nav_row:
        buttons.append(nav_row)
    
    buttons.append([Button.inline("🔙 بازگشت", b"ADMIN:MENU")])
    
    await event.edit(text, buttons=buttons)


async def show_channel_menu(event, sqlite_path: str):
    """Show channel management menu"""
    current_channel = get_channel_id(sqlite_path)
    
    if current_channel:
        text = f"📢 **کانال اجباری**\n\nکانال فعلی: `{current_channel}`"
    else:
        text = "📢 **کانال اجباری**\n\nهیچ کانالی تنظیم نشده است."
    
    buttons = [
        [Button.inline("✏️ تغییر کانال", b"ADMIN:SET_CHANNEL")],
        [Button.inline("🔙 بازگشت", b"ADMIN:MENU")]
    ]
    
    await event.edit(text, buttons=buttons)


async def show_queue_status(event):
    """Show queue processing status"""
    try:
        queue = get_queue()
        
        queue_length = queue.queue.qsize()
        active_workers = queue.max_workers
        
        text = "🧵 **صف پردازش**\n\n"
        text += f"📋 تعداد کارها در صف: **{queue_length}**\n"
        text += f"⚙️ تعداد worker های فعال: **{active_workers}**\n"
        text += f"🔄 وضعیت: {'در حال پردازش' if queue_length > 0 else 'آماده'}\n"
        
        buttons = [
            [Button.inline("🔄 بروزرسانی", b"ADMIN:QUEUE")],
            [Button.inline("🔙 بازگشت", b"ADMIN:MENU")]
        ]
        
        await event.edit(text, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Error showing queue status: {e}")
        await event.edit(
            "❌ خطا در نمایش وضعیت صف",
            buttons=[[Button.inline("🔙 بازگشت", b"ADMIN:MENU")]]
        )


async def show_ai_stats(event, sqlite_path: str):
    """Show AI usage statistics"""
    stats = get_ai_stats(sqlite_path)
    
    text = "📊 **گزارش AI**\n\n"
    text += f"🟢 Primary: **{stats.get('primary', 0)}** درخواست\n"
    text += f"🟡 Fallback 1: **{stats.get('fallback1', 0)}** درخواست\n"
    text += f"🟠 Fallback 2: **{stats.get('fallback2', 0)}** درخواست\n"
    text += f"🔴 خطاها: **{stats.get('failures', 0)}** مورد\n"
    text += f"\n📈 مجموع: **{stats.get('total', 0)}** درخواست"
    
    buttons = [
        [Button.inline("🔄 بروزرسانی", b"ADMIN:AI_STATS")],
        [Button.inline("🔙 بازگشت", b"ADMIN:MENU")]
    ]
    
    await event.edit(text, buttons=buttons)


async def show_cleanup_confirm(event):
    """Show cleanup confirmation"""
    text = "🧹 **پاک‌سازی**\n\n"
    text += "این عملیات موارد زیر را پاک می‌کند:\n"
    text += "• صف کارها\n"
    text += "• کش قدیمی\n"
    text += "• state های منقضی شده\n\n"
    text += "⚠️ **آیا مطمئن هستید؟**"
    
    buttons = [
        [
            Button.inline("✅ بله", b"ADMIN:CLEANUP_CONFIRM"),
            Button.inline("❌ خیر", b"ADMIN:MENU")
        ]
    ]
    
    await event.edit(text, buttons=buttons)


async def perform_cleanup(event, sqlite_path: str):
    """Perform cleanup operations"""
    try:
        # Clear queue
        queue = get_queue()
        cleared_jobs = 0
        while not queue.queue.empty():
            try:
                queue.queue.get_nowait()
                cleared_jobs += 1
            except:
                break
        
        # Clear old cache
        cleared_cache = clear_old_cache(sqlite_path)
        
        # Clear admin states
        admin_states.clear()
        
        text = "✅ **پاک‌سازی انجام شد**\n\n"
        text += f"🗑️ کارهای پاک شده: {cleared_jobs}\n"
        text += f"🗑️ کش پاک شده: {cleared_cache}\n"
        text += f"🗑️ state های پاک شده: تمام موارد"
        
        buttons = [[Button.inline("🔙 بازگشت", b"ADMIN:MENU")]]
        
        await event.edit(text, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        await event.edit(
            "❌ خطا در پاک‌سازی",
            buttons=[[Button.inline("🔙 بازگشت", b"ADMIN:MENU")]]
        )


async def admin_command_handler(event: events.NewMessage.Event, settings: BotSettings):
    """Handle /admin command"""
    user_id = event.sender_id
    
    if not is_admin(user_id, settings):
        await event.respond("❌ دسترسی غیرمجاز.")
        return
    
    await show_admin_menu(event)


async def admin_callback_handler(event: events.CallbackQuery.Event, settings: BotSettings, sqlite_path: str):
    """Handle admin panel callbacks"""
    user_id = event.sender_id
    
    if not is_admin(user_id, settings):
        await event.answer("❌ دسترسی غیرمجاز.", alert=True)
        return
    
    data = event.data.decode('utf-8')
    
    if not data.startswith("ADMIN:"):
        return
    
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    
    try:
        if action == "MENU":
            await show_admin_menu(event, edit=True)
            await event.answer()
            
        elif action == "USERS":
            page = int(parts[2]) if len(parts) > 2 else 0
            await show_users_page(event, sqlite_path, page)
            await event.answer()
            
        elif action == "CHANNEL":
            await show_channel_menu(event, sqlite_path)
            await event.answer()
            
        elif action == "SET_CHANNEL":
            admin_states[user_id] = "ADMIN_SET_CHANNEL"
            await event.edit(
                "📢 **تنظیم کانال اجباری**\n\n"
                "لطفاً username یا ID کانال را ارسال کنید:\n"
                "مثال: @mychannel یا -1001234567890",
                buttons=[[Button.inline("❌ لغو", b"ADMIN:CHANNEL")]]
            )
            await event.answer()
            
        elif action == "QUEUE":
            await show_queue_status(event)
            await event.answer()
            
        elif action == "AI_STATS":
            await show_ai_stats(event, sqlite_path)
            await event.answer()
            
        elif action == "CLEANUP":
            await show_cleanup_confirm(event)
            await event.answer()
            
        elif action == "CLEANUP_CONFIRM":
            await perform_cleanup(event, sqlite_path)
            await event.answer("✅ پاک‌سازی انجام شد")
            
        else:
            await event.answer("❌ دستور نامعتبر")
            
    except Exception as e:
        logger.exception(f"Error in admin callback: {e}")
        await event.answer("❌ خطا در پردازش", alert=True)


async def admin_text_handler(event: events.NewMessage.Event, settings: BotSettings, sqlite_path: str):
    """Handle admin text messages (for setting channel, etc.)"""
    user_id = event.sender_id
    
    if not is_admin(user_id, settings):
        return
    
    if user_id not in admin_states:
        return
    
    state = admin_states[user_id]
    
    if state == "ADMIN_SET_CHANNEL":
        channel_input = event.text.strip()
        
        try:
            # Save channel ID
            set_channel_id(sqlite_path, channel_input)
            
            del admin_states[user_id]
            
            await event.respond(
                f"✅ کانال اجباری تنظیم شد: `{channel_input}`",
                buttons=[[Button.inline("🔙 بازگشت به پنل", b"ADMIN:MENU")]]
            )
            
        except Exception as e:
            logger.error(f"Error setting channel: {e}")
            await event.respond(
                "❌ خطا در تنظیم کانال. لطفاً دوباره تلاش کنید.",
                buttons=[[Button.inline("🔙 بازگشت", b"ADMIN:CHANNEL")]]
            )
