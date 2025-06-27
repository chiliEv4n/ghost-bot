import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

TOKEN = "7761910626:AAFT_eRxUjozvapaJxmTHkolMZANBfsI47o"
LOG_CHANNEL_ID = -1002538510971  # آیدی کانال لاگ

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ساختار داده: active_chats = { user_id: { partner_id: {receiver, type, last_active} } }
active_chats = {}
chat_history = {}

def get_display_name(user):
    if hasattr(user, "username") and user.username:
        return f"@{user.username}"
    elif hasattr(user, "full_name") and user.full_name:
        return user.full_name
    else:
        return "کاربر ناشناس"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = update.effective_user.id

    if args:
        try:
            target_id = int(args[0])
            context.user_data["target_id"] = target_id
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
    user_chats = active_chats.get(user_id, {})

    for partner_id in list(user_chats):
        # حذف دوطرفه چت از هر دو طرف
        partner_chats = active_chats.get(partner_id, {})
        user_chats.pop(partner_id, None)
        partner_chats.pop(user_id, None)

        # حذف پیام‌های ذخیره شده (اختیاری)
        for uid in [user_id, partner_id]:
            messages = chat_history.pop(uid, [])
            for chat_id, msg_id in messages:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception as e:
                    logger.warning(f"خطا در حذف پیام: {e}")

        # ارسال پیام پایان چت به طرف مقابل (اختیاری)
        try:
            await context.bot.send_message(chat_id=partner_id, text="❌ طرف مقابل چت ناشناس را پایان داد.")
        except:
            pass

    await update.message.reply_text("✅ همه چت‌های دوطرفه پایان یافت.")

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
        context.user_data["target_id"] = target_id

        if user_id not in active_chats:
            active_chats[user_id] = {}

        active_chats[user_id][target_id] = {
            "receiver": target_id,
            "last_active": datetime.now(),
            "type": "oneway"
        }
        await query.message.reply_text("✉️ پیام خود را ارسال کنید.")

    elif data.startswith("duo_"):
        target_id = int(data.split("_")[1])
        context.user_data["target_id"] = target_id

        for uid in [user_id, target_id]:
            if uid not in active_chats:
                active_chats[uid] = {}

        active_chats[user_id][target_id] = {
            "receiver": target_id,
            "last_active": datetime.now(),
            "type": "twoway"
        }
        active_chats[target_id][user_id] = {
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

    elif data.startswith("select_"):
        target_id = int(data.split("_")[1])
        context.user_data["target_id"] = target_id
        await query.message.reply_text(f"✅ مخاطب فعال: {target_id}\n✉️ حالا پیام‌هاتو بفرست.")

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_chats = active_chats.get(user_id, {})

    duo_targets = [uid for uid, data in user_chats.items() if data.get("type") == "twoway"]
    if not duo_targets:
        await update.message.reply_text("❌ چت دوطرفه فعالی نداری.")
        return

    buttons = [[InlineKeyboardButton(str(uid), callback_data=f"select_{uid}")] for uid in duo_targets]
    await update.message.reply_text("👥 انتخاب کن با کدوم مخاطب چت می‌کنی:", reply_markup=InlineKeyboardMarkup(buttons))

async def forward_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id

    # اگر مخاطب خاصی از پنل انتخاب شده
    target_id = context.user_data.get("target_id")
    if target_id:
        try:
            await message.copy(chat_id=target_id)
            await message.reply_text("✅ پیام برای مخاطب انتخابی ارسال شد.")
        except Exception as e:
            logger.error(f"خطا در ارسال پیام پنل: {e}")
        return

    user_chats = active_chats.get(user_id, {})
    for partner_id, chat in user_chats.items():
        if datetime.now() - chat["last_active"] > timedelta(days=3):
            continue

        receiver_id = chat["receiver"]

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
            receiver_chat = await context.bot.get_chat(receiver_id)

            sender_name = get_display_name(sender)
            receiver_name = get_display_name(receiver_chat)

            sender_photos = await sender.get_profile_photos()
            receiver_photos = await receiver_chat.get_profile_photos()

            log_text = (
                f"📨 پیام ناشناس\n"
                f"👤 فرستنده: {sender_name} (ID: {sender.id})\n"
                f"👥 گیرنده: {receiver_name} (ID: {receiver_id})\n"
                f"🕒 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            if sender_photos.total_count > 0:
                await context.bot.send_photo(
                    chat_id=LOG_CHANNEL_ID,
                    photo=sender_photos.photos[0][-1].file_id,
                    caption=log_text
                )
            else:
                await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=log_text)

            # ارسال پیام اصلی به کانال لاگ هم بکن
            await message.copy(chat_id=LOG_CHANNEL_ID)

        except Exception as e:
            logger.error(f"خطا در لاگ‌گیری: {e}")

        chat["last_active"] = datetime.now()

        if chat["type"] == "oneway":
            await message.reply_text("✅ پیام شما ارسال شد.")
            return  # فقط یک ارسال برای یک طرف

async def main():
    app = ApplicationBuilder().token('7761910626:AAFT_eRxUjozvapaJxmTHkolMZANBfsI47o').build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("end", end_chat))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), forward_any))

    await app.run_polling()
import asyncio

if __name__ == "__main__":
    asyncio.run(main())


