import os
import asyncio
from collections import deque

from dotenv import load_dotenv
load_dotenv()

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

TOKEN = os.getenv("BOT_TOKEN")

# Waiting queue and active chat map
waiting = deque()
active = {}  # user_id -> partner_id

def is_waiting(uid: int) -> bool:
    return uid in waiting

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid in active:
        await update.message.reply_text("You are already chatting. Use /stop or /next.")
        return

    if is_waiting(uid):
        await update.message.reply_text("You are already in queue. Please wait…")
        return

    if waiting:
        partner = waiting.popleft()

        # Pair them
        active[uid] = partner
        active[partner] = uid

        await context.bot.send_message(partner, "🔗 Connected to a stranger! Say hi 🙂\nUse /next to change partner or /stop to end.")
        await update.message.reply_text("🔗 Connected to a stranger! Say hi 🙂\nUse /next to change partner or /stop to end.")
    else:
        waiting.append(uid)
        await update.message.reply_text("⏳ Waiting for a partner…\nUse /stop to exit queue.")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # Remove from waiting queue if present
    if is_waiting(uid):
        try:
            waiting.remove(uid)
        except ValueError:
            pass
        await update.message.reply_text("✅ Removed from queue.")
        return

    # Disconnect if chatting
    if uid in active:
        partner = active.pop(uid)
        active.pop(partner, None)

        await context.bot.send_message(partner, "❌ Stranger disconnected. Use /start to find a new partner.")
        await update.message.reply_text("❌ Chat ended. Use /start to find a new partner.")
    else:
        await update.message.reply_text("You are not chatting. Use /start.")

async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # End current chat and immediately start again
    await cmd_stop(update, context)
    await asyncio.sleep(0.2)
    await cmd_start(update, context)

async def cmd_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔒 Privacy: This bot relays messages between matched users.\n"
        "We do not display usernames. Avoid sharing personal info.\n"
        "Note: Hosting logs may contain technical metadata (timestamps/errors)."
    )

async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid not in active:
        await update.message.reply_text("You are not connected. Use /start.")
        return

    partner = active[uid]

    # IMPORTANT: do NOT forward_message (that leaks sender info)
    # Send a new message instead.
    msg = update.message

    # Relay text
    if msg.text:
        await context.bot.send_message(partner, msg.text)

    # Relay stickers
    elif msg.sticker:
        await context.bot.send_sticker(partner, msg.sticker.file_id)

    # Relay photos
    elif msg.photo:
        await context.bot.send_photo(partner, msg.photo[-1].file_id, caption=msg.caption or "")

    # Relay voice
    elif msg.voice:
        await context.bot.send_voice(partner, msg.voice.file_id, caption=msg.caption or "")

    else:
        await update.message.reply_text("This message type is not supported yet.")

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("next", cmd_next))
    app.add_handler(CommandHandler("privacy", cmd_privacy))

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, relay))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()