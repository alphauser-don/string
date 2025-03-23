import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler
)
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Configuration
API_ID = int(os.getenv('BOT_API_ID'))
API_HASH = os.getenv('BOT_API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID'))
LOG_CHAT_ID = OWNER_ID

# Conversation states
API_ID_STATE, API_HASH_STATE, PHONE_STATE, OTP_STATE, PASSWORD_STATE = range(5)

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Hello {user.full_name} (@{user.username})!\n"
        f"🆔 Your ID: {user.id}\n\n"
        "Use /cmds to see available commands"
    )

async def cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = [
        "/start - Start the bot",
        "/cmds - Show this commands list",
        "/genstring - Generate new Telethon string session",
        "/revoke - Revoke current string session"
    ]
    if update.effective_user.id == OWNER_ID:
        commands += [
            "\n👑 Owner Commands:",
            "/stats - Bot statistics",
            "/broadcast - Broadcast message",
            "/ban - Ban user",
            "/unban - Unban user",
            "/maintenance - Toggle maintenance mode"
        ]
    await update.message.reply_text("\n".join(commands))

async def genstring_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Let's generate your string session!\nPlease enter your API_ID:")
    return API_ID_STATE

async def receive_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['api_id'] = int(update.message.text)
        await update.message.reply_text("Great! Now send your API_HASH:")
        return API_HASH_STATE
    except ValueError:
        await update.message.reply_text("API_ID must be a number! Try again:")
        return API_ID_STATE

async def receive_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['api_hash'] = update.message.text
    await update.message.reply_text("Now send your phone number (international format):")
    return PHONE_STATE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    client = TelegramClient(
        StringSession(),
        context.user_data['api_id'],
        context.user_data['api_hash']
    )
    await client.connect()
    try:
        sent_code = await client.send_code_request(context.user_data['phone'])
        context.user_data['client'] = client
        context.user_data['phone_code_hash'] = sent_code.phone_code_hash
        await update.message.reply_text("Enter the OTP you received:")
        return OTP_STATE
    except Exception as e:
        await handle_error(update, e)
        return ConversationHandler.END

async def receive_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    otp = update.message.text.strip()
    client = context.user_data['client']
    try:
        await client.sign_in(
            phone=context.user_data['phone'],
            code=otp,
            phone_code_hash=context.user_data['phone_code_hash']
        )
        string_session = client.session.save()
        await update.message.reply_text(f"✅ String session generated:\n`{string_session}`", parse_mode='Markdown')
        await client.disconnect()
    except Exception as e:
        if "two-step verification" in str(e).lower():
            await update.message.reply_text("Enter your 2FA password:")
            return PASSWORD_STATE
        else:
            await handle_error(update, e)
    return ConversationHandler.END

async def receive_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    client = context.user_data['client']
    try:
        await client.sign_in(password=password)
        string_session = client.session.save()
        await update.message.reply_text(f"✅ String session generated:\n`{string_session}`", parse_mode='Markdown')
        await client.disconnect()
    except Exception as e:
        await handle_error(update, e)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Session generation cancelled")
    return ConversationHandler.END

async def handle_error(update: Update, error):
    logger.error(f"Error: {error}", exc_info=True)
    await update.message.reply_text("❌ An error occurred. Please contact @rishabh_zz")
    await context.bot.send_message(LOG_CHAT_ID, f"Error occurred:\n{error}\n\nUser: {update.effective_user}")

# Owner commands
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    # Add stats logic here
    await update.message.reply_text("📊 Bot statistics")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    # Add broadcast logic here
    await update.message.reply_text("📢 Broadcast message sent")

async def maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    # Add maintenance toggle logic
    await update.message.reply_text("🔧 Maintenance mode toggled")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Conversation handler for string generation
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('genstring', genstring_start)],
        states={
            API_ID_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_id)],
            API_HASH_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_hash)],
            PHONE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
            OTP_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_otp)],
            PASSWORD_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_2fa)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('cmds', cmds))
    application.add_handler(conv_handler)
    
    # Owner commands
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CommandHandler('maintenance', maintenance))

    application.run_polling()

if __name__ == '__main__':
    main()
