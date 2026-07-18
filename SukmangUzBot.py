# -*- coding: utf-8 -*-
import subprocess
import sys
import os
import json
import asyncio
import logging
import re
import html

# --- 1. KUTUBXONALARNI AVTOMATIK O'RNATISH ---
try:
    import aiogram
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiogram==3.10.0"])
    import aiogram

try:
    import aiohttp
    from aiohttp import web
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
    import aiohttp
    from aiohttp import web

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, TelegramObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- 2. SOZLAMALAR ---
API_TOKEN = '7970454395:AAGhKYvCQlSqkBo0doo4t1_VVta2rzXR-zo'
BOT_ID = int(API_TOKEN.split(':')[0])

# Bot egasi (owner) Telegram ID raqami
OWNER_ID = 8659710238

# Render sozlamalari (Render avtomatik PORT beradi, RENDER_EXTERNAL_URL ham beriladi)
PORT = int(os.getenv("PORT", 10000))
SELF_URL = os.getenv("RENDER_EXTERNAL_URL", "")  # masalan: https://sizning-botingiz.onrender.com
PING_INTERVAL = 5 * 60  # 5 daqiqa

CHATS_FILE = "known_chats.json"

BAD_WORDS = [
    'dalbayob', 'yeban', 'yban', 'yiban', 'suka', 'harp', 'harip', 'jalab',
    'gandon', 'oneniami', 'ayeniami', 'ami', 'omi', 'sikaman', 'sikib',
    'haram', 'qotoq', 'qoto', 'qotaq', 'kot', 'dnx', 'pashol', 'pasholnaxuy',
    'ske', 'buveniami', 'buveniomi', 'om', 'am', 'xxx', 'skaman', 'skay',
    'gey', 'sperma', 'porno', 'pornografiya'
]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- 3. TOZALASH FUNKSIYASI ---
def deep_clean(text: str):
    replacements = {'\u0430': 'a', '\u0435': 'e', '\u043e': 'o', '\u0440': 'p', '\u0441': 's', '\u0445': 'x', '\u0443': 'y'}
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z\u0400-\u04FF\s]', '', text)
    for cyr, lat in replacements.items():
        text = text.replace(cyr, lat)
    return text

# --- 4. GURUH/LICHKALAR RO'YXATINI SAQLASH (reklama tarqatish uchun) ---
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_chats():
    try:
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(known_chats), f)
    except Exception as e:
        logging.warning(f"Chatlarni saqlashda xatolik: {e}")

known_chats = load_chats()

class ChatTrackerMiddleware(BaseMiddleware):
    """Har bir xabar kelganda shu chat ID sini ro'yxatga qo'shib boradi."""
    async def __call__(self, handler, event: TelegramObject, data):
        chat = getattr(event, "chat", None)
        if chat is not None and chat.id not in known_chats:
            known_chats.add(chat.id)
            save_chats()
        return await handler(event, data)

dp.message.middleware(ChatTrackerMiddleware())

# --- 5. BOTNING ADMIN HUQUQINI TEKSHIRISH ---
async def bot_can_delete(chat_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, BOT_ID)
        if member.status == "creator":
            return True
        return bool(getattr(member, "can_delete_messages", False))
    except Exception:
        return False

# --- 6. KIRDI-CHIQDINI TOZALASH ---
@dp.message(F.chat.type.in_({"group", "supergroup"}), F.content_type.in_({"new_chat_members", "left_chat_member"}))
async def delete_join_left_messages(message: Message):
    try:
        await message.delete()
    except Exception:
        pass

# --- 7. ASOSIY MODERATOR ---
@dp.message(F.chat.type.in_({"group", "supergroup"}), F.text, ~F.text.startswith('/'))
async def group_moderator(message: Message):
    if message.sender_chat or message.is_automatic_forward:
        return
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status in ['administrator', 'creator']:
            return
    except Exception:
        pass

    cleaned_text = deep_clean(message.text)
    words_in_message = cleaned_text.split()
    is_bad = False
    for bad_word in BAD_WORDS:
        if len(bad_word) <= 3:
            if bad_word in words_in_message:
                is_bad = True
                break
        elif bad_word in cleaned_text:
            is_bad = True
            break

    is_ad = "t.me/" in message.text.lower() or "http" in message.text.lower()

    if is_bad or is_ad:
        can_delete = await bot_can_delete(message.chat.id)

        if can_delete:
            try:
                await message.delete()
            except Exception:
                pass

        user_name = html.escape(message.from_user.full_name)
        user_mention = f'<a href="tg://user?id={message.from_user.id}">{user_name}</a>'

        if is_bad:
            msg = f"{user_mention} iltimos, so'kinmang! \U0001F910"
        else:
            msg = f"{user_mention} reklama tarqatmang! \U0001F6AB"

        # Agar botda o'chirish huquqi bo'lmasa, shuni so'raydi
        if not can_delete:
            msg += ("\n\n\u26A0\uFE0F Men bu turdagi xabarlarni o'chira olishim uchun "
                    "menga <b>admin huquqini</b> (xabarlarni o'chirish) bering!")

        try:
            await message.answer(msg, parse_mode="HTML")
        except Exception:
            pass

# --- 8. START BUYRUG'I ---
@dp.message(Command("start"))
async def start_cmd(message: Message):
    user_name = html.escape(message.from_user.full_name)

    text = (
        f"Assalomu alaykum, {user_name}! \U0001F44B\n"
        "Men guruhlarda tartib saqlaydigan botman.\n\n"
        "<b>Vazifalarim:</b>\n"
        "1. So'kinishlarni o'chirish \U0001F92C\n"
        "2. Reklamani cheklash \U0000274C\n"
        "3. Kirdi-chiqdi xabarlarini tozalash \U00002728\n\n"
        "Men ishlashim uchun meni guruhingizga admin qiling! \U0001F46E"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="Botni guruhga qo'shish \U00002795",
        url="https://t.me/SukmangUzBot?startgroup=true&admin=delete_messages+restrict_members"
    ))

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

# --- 9. OWNER UCHUN REKLAMA TARQATISH BUYRUG'I (/rek) ---
@dp.message(F.chat.type == "private", Command("rek"))
async def broadcast_ad(message: Message):
    if message.from_user.id != OWNER_ID:
        return  # faqat owner ishlata oladi

    if not message.reply_to_message:
        await message.answer(
            "Reklama qilmoqchi bo'lgan postingizga <b>reply</b> qilib, "
            "shu reply ostida <code>/rek</code> deb yozing.",
            parse_mode="HTML"
        )
        return

    source = message.reply_to_message
    status_msg = await message.answer("\u23F3 Reklama yuborilmoqda...")

    sent, failed = 0, 0
    for chat_id in list(known_chats):
        if chat_id == message.chat.id:
            continue  # o'ziga o'zi yubormaydi
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=source.chat.id,
                message_id=source.message_id
            )
            sent += 1
        except Exception as e:
            failed += 1
            err = str(e).lower()
            if "bot was blocked" in err or "chat not found" in err or "kicked" in err or "forbidden" in err:
                known_chats.discard(chat_id)
        await asyncio.sleep(0.05)  # Telegram limitiga tegib qolmaslik uchun

    save_chats()
    await status_msg.edit_text(
        f"\u2705 Reklama tarqatildi!\n\nYuborildi: <b>{sent}</b>\nXatolik: <b>{failed}</b>",
        parse_mode="HTML"
    )

# --- 10. RENDER UCHUN "TIRIK TURISH" (KEEP-ALIVE) ---
# Render'ning bepul tarifi 15 daqiqa so'rov kelmasa, ilovani "uxlatib" qo'yadi.
# Shuning uchun: (a) kichik veb-server ochib, tashqi so'rovlarni qabul qiladi,
# (b) o'ziga o'zi har 5 daqiqada so'rov yuborib turadi.

async def handle_ping(request):
    return web.Response(text="Bot ishlamoqda!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Keep-alive server {PORT}-portda ishga tushdi.")

async def self_ping_loop():
    if not SELF_URL:
        logging.warning("RENDER_EXTERNAL_URL topilmadi, self-ping o'chirilgan.")
        return
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(PING_INTERVAL)
            try:
                async with session.get(SELF_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    logging.info(f"Self-ping yuborildi, status: {resp.status}")
            except Exception as e:
                logging.warning(f"Self-ping xatolik: {e}")

# --- 11. DASTURNI ISHGA TUSHIRISH ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await start_web_server()
    asyncio.create_task(self_ping_loop())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())