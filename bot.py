import os
import logging
import asyncio
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Включаем логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы состояний разговора
PHOTO, DESCRIPTION, PHONE, NAME, CONFIRMATION = range(5)

# Задаём данные бота и администратора
BOT_TOKEN = "7574826063:AAF4bq0_bvC1jSl0ynrWyaH_fGtyLi7j5Cw"
ADMIN_ID = 2045410830

# Глобальная переменная для подсчёта объявлений
announcement_count = 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка команды /start — приветствие и кнопка для создания объявления."""
    keyboard = [
        [InlineKeyboardButton("Розмістити оголошення 📢", callback_data="post_ad")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = (
        "Привіт! Ви на каналі оголошень **«Купи/Продай Одеська область»** 🛍️\n\n"
        "Тут ви можете швидко знайти або продати будь-що: техніка, одяг, послуги, нерухомість та інше!\n\n"
        "Натисніть кнопку нижче, щоб розмістити ваше оголошення."
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    return ConversationHandler.END


async def post_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запуск процесу створення оголошення після натискання кнопки."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📸 Будь ласка, надішліть фото оголошення (якщо є). Якщо фото немає, використовуйте команду /skip",
    )
    return PHOTO


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка фото объявления."""
    photo_file = update.message.photo[-1]
    # Сохраняем file_id для последующей отправки администратору
    context.user_data["photo"] = photo_file.file_id
    await update.message.reply_text("✏️ Тепер надішліть опис оголошення та ціну:")
    return DESCRIPTION


async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск фото объявления."""
    context.user_data["photo"] = None
    await update.message.reply_text("✏️ Тепер надішліть опис оголошення та ціну:")
    return DESCRIPTION


async def description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка описания объявления."""
    context.user_data["description"] = update.message.text
    await update.message.reply_text("📞 Будь ласка, надішліть ваш номер телефону:")
    return PHONE


async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка номера телефона."""
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("👤 Вкажіть ваше ім'я:")
    return NAME


async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка имени отправителя объявления и формирование сводки для подтверждения."""
    context.user_data["name"] = update.message.text

    summary = "📋 Ось ваші дані для оголошення:\n\n"
    if context.user_data.get("photo"):
        summary += "🖼 Фото: ✅\n"
    else:
        summary += "🖼 Фото: ❌\n"
    summary += f"📝 Опис та ціна: {context.user_data.get('description')}\n"
    summary += f"📞 Телефон: {context.user_data.get('phone')}\n"
    summary += f"👤 Ім'я: {context.user_data.get('name')}\n\n"
    summary += "Будь ласка, підтвердіть, чи всі дані вірні."

    keyboard = [
        [InlineKeyboardButton("✅ Підтвердити", callback_data="confirm")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(summary, reply_markup=reply_markup)
    return CONFIRMATION


async def confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка подтверждения объявления."""
    query = update.callback_query
    await query.answer()
    if query.data == "confirm":
        global announcement_count
        announcement_count += 1

        message_text = "🆕 Нове оголошення:\n\n"
        if context.user_data.get("photo"):
            message_text += "🖼 Фото: є\n"
        else:
            message_text += "🖼 Фото: немає\n"
        message_text += f"📝 Опис та ціна: {context.user_data.get('description')}\n"
        message_text += f"📞 Телефон: {context.user_data.get('phone')}\n"
        message_text += f"👤 Ім'я: {context.user_data.get('name')}\n"

        # Надсилаємо оголошення адміну
        try:
            if context.user_data.get("photo"):
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=context.user_data.get("photo"),
                    caption=message_text,
                )
            else:
                await context.bot.send_message(chat_id=ADMIN_ID, text=message_text)
        except Exception as e:
            logger.error(f"Помилка при надсиланні оголошення адміну: {e}")

        await query.edit_message_text("Дякуємо! Ваше оголошення обробляється та незабаром буде опубліковано. 😊")
    else:
        await query.edit_message_text(
            "Оголошення скасовано. Якщо бажаєте, можете почати заново, натиснувши кнопку /start."
        )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда для скасування процесу створення оголошення."""
    await update.message.reply_text("Оголошення скасовано. 😞", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# Адміністративні команди

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для розсилки повідомлень (тільки для адміністратора).  
    Використання: /broadcast ваше повідомлення"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 Недостатньо прав для виконання цієї команди.")
        return
    if context.args:
        message_to_broadcast = " ".join(context.args)
        # ЗАМІНІТЬ CHANNEL_ID на фактичний ID каналу або групи
        CHANNEL_ID = -1001234567890  
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=message_to_broadcast)
            await update.message.reply_text("✅ Повідомлення відправлено до каналу.")
        except Exception as e:
            logger.error(f"Помилка під час розсилки: {e}")
            await update.message.reply_text("🚫 Помилка під час відправлення повідомлення.")
    else:
        await update.message.reply_text("Будь ласка, введіть текст повідомлення після команди /broadcast")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для отримання статистики (тільки для адміністратора)."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 Недостатньо прав для виконання цієї команди.")
        return
    await update.message.reply_text(f"📊 Статистика:\nКількість оголошень: {announcement_count}")


async def main() -> None:
    """Основна функція для запуску бота."""
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(post_ad_callback, pattern="^post_ad$"),
            CommandHandler("start", start),
        ],
        states={
            PHOTO: [
                MessageHandler(filters.PHOTO, photo_handler),
                CommandHandler("skip", skip_photo),
            ],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_handler)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_handler)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
            CONFIRMATION: [CallbackQueryHandler(confirmation_handler, pattern="^(confirm|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats))

    # Налаштування для роботи через webhook на Heroku
    port = int(os.environ.get("PORT", "8443"))
    HEROKU_APP_NAME = os.environ.get("HEROKU_APP_NAME")
    if HEROKU_APP_NAME:
        webhook_url = f"https://{HEROKU_APP_NAME}.herokuapp.com/{BOT_TOKEN}"
        await application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url,
        )
    else:
        # Для локального тестування використовуємо polling
        await application.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
