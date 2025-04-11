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
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Проект размещён на GitHub: https://applabua.github.io/kupyprodaiod/

# Настраиваем логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы состояний разговора
# Состояния: PHOTO, DESCRIPTION, TARIFF, PHONE, NAME, CONFIRMATION
PHOTO, DESCRIPTION, TARIFF, PHONE, NAME, CONFIRMATION = range(6)

# Данные бота и администратора
BOT_TOKEN = "7574826063:AAF4bq0_bvC1jSl0ynrWyaH_fGtyLi7j5Cw"
ADMIN_ID = 2045410830

# Счётчик объявлений
announcement_count = 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка команды /start — приветствие и кнопка для создания объявления."""
    keyboard = [
        [InlineKeyboardButton("Розмістити оголошення 📢", callback_data="post_ad")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = (
        "Привіт! Ви на каналі оголошень **«Купи/Продай Одеська область»** 🛍️\n\n"
        "Тут ви можете швидко знайти або продати будь-який товар чи послугу у вашому регіоні.\n\n"
        "Натисніть кнопку нижче, щоб розмістити ваше оголошення."
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    return ConversationHandler.END

async def post_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запуск процесу створення оголошення після натискання кнопки."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📸 Будь ласка, надішліть фото оголошення (якщо є). Якщо фото відсутнє, використовуйте команду /skip"
    )
    return PHOTO

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка фото оголошення."""
    photo_file = update.message.photo[-1]
    context.user_data["photo"] = photo_file.file_id
    await update.message.reply_text("✏️ Тепер надішліть опис оголошення та вкажіть його ціну:")
    return DESCRIPTION

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск фото оголошення."""
    context.user_data["photo"] = None
    await update.message.reply_text("✏️ Тепер надішліть опис оголошення та вкажіть його ціну:")
    return DESCRIPTION

async def description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка описания оголошення."""
    context.user_data["description"] = update.message.text
    # Запит вибору тарифу для оголошення
    keyboard = [
        [InlineKeyboardButton("Звичайне оголошення (300 грн)", callback_data="tariff_normal")],
        [InlineKeyboardButton("ТОП оголошення (500 грн/24 год)", callback_data="tariff_top")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💰 Вкажіть тип оголошення:\n"
        "• Звичайне оголошення — 300 грн\n"
        "• ТОП оголошення — 500 грн на 24 години\n\n"
        "Будь ласка, зробіть вибір:",
        reply_markup=reply_markup
    )
    return TARIFF

async def tariff_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка вибору тарифу оголошення."""
    query = update.callback_query
    await query.answer()
    if query.data == "tariff_normal":
        context.user_data["tariff"] = "Звичайне оголошення (300 грн)"
    elif query.data == "tariff_top":
        context.user_data["tariff"] = "ТОП оголошення (500 грн/24 год)"
    await query.edit_message_text(
        text=f"Ви обрали: {context.user_data['tariff']}\n\n📞 Будь ласка, надішліть ваш номер телефону:"
    )
    return PHONE

async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка номера телефону."""
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("👤 Вкажіть ваше ім'я:")
    return NAME

async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка імені відправника оголошення та формування сводки для підтвердження."""
    context.user_data["name"] = update.message.text

    summary = "📋 Ось ваші дані для оголошення:\n\n"
    summary += "🖼 Фото: " + ("✅" if context.user_data.get("photo") else "❌") + "\n"
    summary += f"📝 Опис та ціна: {context.user_data.get('description')}\n"
    summary += f"💰 Тип оголошення: {context.user_data.get('tariff')}\n"
    summary += f"📞 Телефон: {context.user_data.get('phone')}\n"
    summary += f"👤 Ім'я: {context.user_data.get('name')}\n\n"
    summary += "Будь ласка, підтвердіть, чи всі дані вірні."
    
    keyboard = [
        [InlineKeyboardButton("✅ Підтвердити", callback_data="confirm")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(summary, reply_markup=reply_markup)
    return CONFIRMATION

async def confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка підтвердження оголошення."""
    query = update.callback_query
    await query.answer()
    if query.data == "confirm":
        global announcement_count
        announcement_count += 1

        message_text = "🆕 Нове оголошення:\n\n"
        message_text += "🖼 Фото: " + ("є" if context.user_data.get("photo") else "немає") + "\n"
        message_text += f"📝 Опис та ціна: {context.user_data.get('description')}\n"
        message_text += f"💰 Тип оголошення: {context.user_data.get('tariff')}\n"
        message_text += f"📞 Телефон: {context.user_data.get('phone')}\n"
        message_text += f"👤 Ім'я: {context.user_data.get('name')}\n"

        # Надсилання оголошення адміну
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
        await query.edit_message_text("Оголошення скасовано. Якщо бажаєте, можете почати заново, натиснувши кнопку /start.")
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
        # ЗАМІНІТЬ CHANNEL_ID на фактичний ID каналу або групи, куди потрібно розсилати повідомлення
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
    """Основна функція запуску бота."""
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
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, description_handler)
            ],
            TARIFF: [
                CallbackQueryHandler(tariff_callback, pattern="^(tariff_normal|tariff_top)$")
            ],
            PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone_handler)
            ],
            NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)
            ],
            CONFIRMATION: [
                CallbackQueryHandler(confirmation_handler, pattern="^(confirm|cancel)$")
            ],
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
        # Для локального тестування – polling
        await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
