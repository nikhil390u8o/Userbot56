import os
import asyncio
import random
import nest_asyncio
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Load .env variables
load_dotenv()
nest_asyncio.apply()

# Environment variables
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
WELCOME_IMAGE = os.getenv("WELCOME_IMAGE_URL")
GIRL_IMAGE = os.getenv("GIRL_IMAGE_URL")
OWNER_ID = int(os.getenv("OWNER_ID"))
SUPPORT_CHANNEL = os.getenv("SUPPORT_CHANNEL")
SUPPORT_GROUP = os.getenv("SUPPORT_GROUP")
OWNER_USERNAME = os.getenv("OWNER_USERNAME")

userbots = {}
waiting_for_string = set()

# Empty list — you can fill with your own clean raid messages later
raid_messages = []

# Love messages (clean)
love_messages = [
    "💖 Love is a journey, not a destination.",
    "💕 Every heartbeat whispers your name.",
    "💫 In your smile, I see the stars.",
    "🌹 You light up my world like nobody else.",
]

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    waiting_for_string.add(user_id)

    keyboard = [
        [InlineKeyboardButton("Channel", url=SUPPORT_CHANNEL),
         InlineKeyboardButton("Group", url=SUPPORT_GROUP)],
        [InlineKeyboardButton("Help", callback_data="help")],
        [InlineKeyboardButton("My Lord", url=f"https://t.me/{OWNER_USERNAME}")]
    ]

    await update.message.reply_photo(
        photo=WELCOME_IMAGE,
        caption="Welcome! Send your Telethon string session to start.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Telethon userbot handlers
async def register_userbot_handlers(client, me):
    @client.on(events.NewMessage(pattern=r"\.ping"))
    async def ping(event):
        m = await event.respond("Pinging...")
        await asyncio.sleep(0.5)
        await m.edit(f"✅ Alive as {me.first_name}")

    @client.on(events.NewMessage(pattern=r"\.alive"))
    async def alive(event):
        await event.respond(f"Yes boss! {me.first_name} is online.")

    @client.on(events.NewMessage(pattern=r"\.raid(?:\s+\d+)?"))
    async def raid(event):
        if not raid_messages:
            return await event.respond("⚠️ No raid messages configured.")
        if not event.is_reply:
            return await event.reply("Reply to a message with `.raid <count>`")

        reply_msg = await event.get_reply_message()
        user = await reply_msg.get_sender()
        mention = f"@{user.username}" if user.username else f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

        args = event.raw_text.split()
        count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5

        await event.reply(f"Raiding {mention} with {count} messages...", parse_mode="html")
        for i in range(count):
            text = raid_messages[i % len(raid_messages)]
            await event.respond(f"{mention}, {text}", parse_mode="html")

    @client.on(events.NewMessage(pattern=r"\.love(?:\s+\d+)?"))
    async def love(event):
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

# When user sends string
async def receive_string(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in waiting_for_string:
        return

    string = update.message.text.strip()
    msg = await update.message.reply_text("Processing...")

    try:
        client = TelegramClient(StringSession(string), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            waiting_for_string.discard(user_id)
            return await msg.edit_text("Invalid string session.")

        me = await client.get_me()
        userbots[user_id] = client
        waiting_for_string.discard(user_id)

        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"New session: {me.first_name} | @{me.username or 'no username'} | ID: {me.id}",
        )

        await register_userbot_handlers(client, me)
        await client.start()
        await msg.edit_text("✅ Your client is now connected.")

    except Exception as e:
        waiting_for_string.discard(user_id)
        await msg.edit_text(f"❌ Error: {e}")

# Handle buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help":
        keyboard = [
            [InlineKeyboardButton("Stop Bot", callback_data="stop")],
            [InlineKeyboardButton("Go Back", callback_data="back")]
        ]
        await query.edit_message_media(
            InputMediaPhoto(GIRL_IMAGE, caption="Commands: .ping, .alive, .raid, .love"),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "stop":
        user_id = query.from_user.id
        if user_id in userbots:
            await userbots[user_id].disconnect()
            del userbots[user_id]
            await query.edit_message_caption("🛑 Userbot stopped.")
        else:
            await query.edit_message_caption("⚠️ No active userbot.")

    elif query.data == "back":
        keyboard = [
            [InlineKeyboardButton("Channel", url=SUPPORT_CHANNEL),
             InlineKeyboardButton("Group", url=SUPPORT_GROUP)],
            [InlineKeyboardButton("Help", callback_data="help")],
            [InlineKeyboardButton("Owner", url=f"https://t.me/{OWNER_USERNAME}")]
        ]
        await query.edit_message_media(
            InputMediaPhoto(WELCOME_IMAGE, caption="Send your Telethon string session to start."),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# Start the bot
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_string))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
