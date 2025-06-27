# main.py
import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
        ApplicationBuilder, CommandHandler, MessageHandler,
        CallbackQueryHandler, ContextTypes, filters
    )

    # به جای استفاده از .env، مستقیماً مقداردهی می‌کنیم
TOKEN = "7761910626:AAFT_eRxUjozvapaJxmTHkolMZANBfsI47o"
LOG_CHANNEL_ID = -1002538510971  # عدد کانال لاگ

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

active_chats = {}
chat_history = {}

def get_display_name(user):
    return f"@{user.username}" if user.username else user.full_name

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id

    if args:
        target_id = int(args[0])
        context.user_data["target_id"] = target_id

        try:
            user = await context.bot.get_chat(target_id)
            display_name = get_display_name(user)
        except:
            display_name = "کاربر ناشناس"

        await update.message.reply_text(
            f"👤 انتخاب کن چیکار می‌خوای بکنی برای {display_name}:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✉️ ارسال پیام ناشناس به\n{display_name}", callback_data=f"sendto_{target_id}")],
                [InlineKeyboardButton(f"🔁 چت دو طرفه با\n{display_name}", callback_data=f"duo_{target_id}")],
                [InlineKeyboardButton("🎯 دریافت لینک ناشناس من", callback_data="getlink")]
            ])
        )
    else:
        await update.message.reply_text(
            "👋 خوش اومدی! با این ربات می‌تونی پیام ناشناس دریافت یا ارسال کنی.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 دریافت لینک ناشناس من", callback_data="getlink")]
            ])
        )

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = active_chats.pop(user_id, None)

    if chat:
        receiver_id = chat["receiver"]
        active_chats.pop(receiver_id, None)

        for uid in [user_id, receiver_id]:
            messages = chat_history.pop(uid, [])
            for chat_id, msg_id in messages:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception as e:
                    logger.warning(f"خطا در حذف پیام: {e}")

        await update.message.reply_text("✅ چت ناشناس پایان یافت.")

        try:
            await context.bot.send_message(
                chat_id=receiver_id,
                text="❌ طرف مقابل چت ناشناس را پایان داد."
            )
        except:
            pass
    else:
        await update.message.reply_text("⛔ چت فعالی برای پایان دادن وجود ندارد.")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "getlink":
        await query.message.reply_text(
            f"📎 لینک ناشناس شما:\nhttps://t.me/{context.bot.username}?start={user_id}",
                disable_web_page_preview=True
        )

    elif data.startswith("sendto_"):
        target_id = int(data.split("_")[1])

        if user_id in active_chats and active_chats[user_id].get("receiver") == target_id and active_chats[user_id].get("type") == "twoway":
            await query.message.reply_text("⚠️ چت دوطرفه با این کاربر فعال است. نیازی به ارسال یک‌طرفه نیست.")
            return

        context.user_data["target_id"] = target_id
        active_chats[user_id] = {
            "receiver": target_id,
            "last_active": datetime.now(),
            "type": "oneway"
        }
        await query.message.reply_text("✉️ پیام خود را ارسال کنید.")

    elif data.startswith("duo_"):
        target_id = int(data.split("_")[1])
        context.user_data["target_id"] = target_id

        active_chats[user_id] = {
            "receiver": target_id,
            "last_active": datetime.now(),
            "type": "twoway"
        }
        active_chats[target_id] = {
            "receiver": user_id,
            "last_active": datetime.now(),
            "type": "twoway"
        }
        await query.message.reply_text(
            f"🔓 چت دو طرفه با <a href='tg://user?id={target_id}'>کاربر</a> آغاز شد!\n\n⏳ این گفتگو تا ۳ روز فعال است.\n✅ برای پایان، از دستور /end استفاده کن.",
            parse_mode="HTML"
        )

    elif data.startswith("report_"):
        reporter_id = user_id
        reported_user_id = int(data.split("_")[1])
        await context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=f"🚨 پیام گزارش شده!\n👤 گزارش‌دهنده: {reporter_id}\n👤 فرستنده: {reported_user_id}"
        )
        await query.message.reply_text("🚨 پیام گزارش شد. ممنون از همکاری‌ت!")

async def forward_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id

    chat = active_chats.get(user_id)
    if chat and datetime.now() - chat["last_active"] < timedelta(days=3):
        receiver_id = chat["receiver"]

        if chat["type"] == "twoway" and receiver_id not in active_chats:
            active_chats[receiver_id] = {
                "receiver": user_id,
                "last_active": datetime.now(),
                "type": "twoway"
            }

        try:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚠️ گزارش پیام", callback_data=f"report_{user_id}")]
            ])
            sent_msg = await message.copy(chat_id=receiver_id, reply_markup=keyboard)
            chat_history.setdefault(user_id, []).append((sent_msg.chat_id, sent_msg.message_id))
            chat_history.setdefault(receiver_id, []).append((sent_msg.chat_id, sent_msg.message_id))
        except Exception as e:
            logger.error(f"خطا در ارسال پیام: {e}")

        try:
            sender = message.from_user
            receiver = await context.bot.get_chat(receiver_id)

            log_text = (
                f"📨 پیام ناشناس\n"
                f"👤 فرستنده: {sender.full_name} "
                f"(@{sender.username if sender.username else 'بدون یوزرنیم'}) "
                f"(ID: {sender.id})\n"
                f"👥 گیرنده: {receiver.full_name} "
                f"(@{receiver.username if receiver.username else 'بدون یوزرنیم'}) "
                f"(ID: {receiver.id})\n"
                f"🕒 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_text)
            await message.copy(chat_id=LOG_CHANNEL_ID)
        except Exception as e:
            logger.error(f"خطا در لاگ‌گیری: {e}")

        chat["last_active"] = datetime.now()

        if chat["type"] == "oneway":
            await message.reply_text("✅ پیام شما ارسال شد.")
        return

    await message.reply_text("⛔ چت ناشناس فعالی ندارید.")

if __name__ == '__main__':
   

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("end", end_chat))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_any))

    app.run_polling()
            await message.copy(chat_id=LOG_CHANNEL_ID)  # بدون ذخیره در chat_history
        except Exception as e:
            logger.error(f"خطا در لاگ‌گیری: {e}")

        chat["last_active"] = datetime.now()

        if chat["type"] == "oneway":
            await message.reply_text("✅ پیام شما ارسال شد.")
        return

    await message.reply_text("⛔ چت ناشناس فعالی ندارید.")

if __name__ == '__main__':
   

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("end", end_chat))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_any))

    app.run_polling()
