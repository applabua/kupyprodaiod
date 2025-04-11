import os
import logging
import asyncio
import nest_asyncio  # для уникнення помилки закриття запущеного event loop

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

# Застосовуємо nest_asyncio для коректної роботи event loop
nest_asyncio.apply()

# Посилання на проект на GitHub:
# https://applabua.github.io/kupyprodaiod/

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константи для станів діалогу
PHOTO, DESCRIPTION, TARIFF, PHONE, NAME, CONFIRMATION = range(6)

# Дані бота та адміністратора
BOT_TOKEN = "7574826063:AAF4bq0_bvC1jSl0ynrWyaH_fGtyLi7j5Cw"
ADMIN_ID = 2045410830

# Лічильник оголошень
announcement_count = 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка команди /start — привітання та кнопка для створення оголошення."""
    keyboard = [
        [InlineKeyboardButton("Розмістити оголошення 📢", callback_data="post_ad")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = (
        "Привіт! Ви на каналі оголошень **«Купи/Продай Одеська область»** 🛍️\n\n"
        "Тут можна швидко знайти чи продати будь-який товар або послугу у вашому регіоні.\n\n"
        "Натисніть кнопку нижче, щоб розмістити ваше оголошення."
    )
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    return ConversationHandler.END


async def post_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Старт процесу створення оголошення після натискання кнопки."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📸 Будь ласка, надішліть фото оголошення (якщо є). Якщо фото немає – введіть /skip",
    )
    return PHOTO


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка фото оголошення."""
    photo_file = update.message.photo[-1]
    context.user_data["photo"] = photo_file.file_id
    await update.message.reply_text("✏️ Тепер введіть опис оголошення та вкажіть ціну:")
    return DESCRIPTION


async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск завантаження фото."""
    context.user_data["photo"] = None
    await update.message.reply_text("✏️ Тепер введіть опис оголошення та вкажіть ціну:")
    return DESCRIPTION


async def description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка опису оголошення."""
    context.user_data["description"] = update.message.text
    # Запит тарифу з вказаною вартістю
    keyboard = [
        [InlineKeyboardButton("Звичайне оголошення (300 грн)", callback_data="tariff_normal")],
        [InlineKeyboardButton("ТОП оголошення (500 грн/24 год)", callback_data="tariff_top")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💰 Виберіть тип оголошення:\n"
        "• Звичайне оголошення — 300 грн\n"
        "• ТОП оголошення — 500 грн на 24 години\n\n"
        "Зробіть свій вибір:",
        reply_markup=reply_markup,
    )
    return TARIFF


async def tariff_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору тарифу оголошення."""
    query = update.callback_query
    await query.answer()
    if query.data == "tariff_normal":
        context.user_data["tariff"] = "Звичайне оголошення (300 грн)"
    elif query.data == "tariff_top":
        context.user_data["tariff"] = "ТОП оголошення (500 грн/24 год)"
    await query.edit_message_text(
        text=f"Ви обрали: {context.user_data['tariff']}\n\n📞 Будь ласка, введіть ваш номер телефону:"
    )
    return PHONE


async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка номера телефону."""
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("👤 Введіть ваше ім'я:")
    return NAME


async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка імені та формування зведеної інформації для підтвердження."""
    context.user_data["name"] = update.message.text
    summary = (
        "📋 Ось ваші дані для оголошення:\n\n"
        f"🖼 Фото: {'✅' if context.user_data.get('photo') else '❌'}\n"
        f"📝 Опис та ціна: {context.user_data.get('description')}\n"
        f"💰 Тип оголошення: {context.user_data.get('tariff')}\n"
        f"📞 Телефон: {context.user_data.get('phone')}\n"
        f"👤 Ім'я: {context.user_data.get('name')}\n\n"
        "Підтвердіть, чи всі дані вірні."
    )
    keyboard = [
        [InlineKeyboardButton("✅ Підтвердити", callback_data="confirm")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(summary, reply_markup=reply_markup)
    return CONFIRMATION


async def confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка підтвердження оголошення."""
    query = update.callback_query
    await query.answer()
    if query.data == "confirm":
        global announcement_count
        announcement_count += 1

        message_text = (
            "🆕 Нове оголошення:\n\n"
            f"🖼 Фото: {'є' if context.user_data.get('photo') else 'немає'}\n"
            f"📝 Опис та ціна: {context.user_data.get('description')}\n"
            f"💰 Тип оголошення: {context.user_data.get('tariff')}\n"
            f"📞 Телефон: {context.user_data.get('phone')}\n"
            f"👤 Ім'я: {context.user_data.get('name')}\n"
        )
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
            logger.error(f"Помилка при відправленні оголошення адміну: {e}")

        await query.edit_message_text("Дякуємо! Ваше оголошення обробляється та скоро буде опубліковано. 😊")
    else:
        await query.edit_message_text(
            "Оголошення скасовано. Якщо бажаєте, почніть заново, натиснувши /start."
        )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда для скасування процесу створення оголошення."""
    await update.message.reply_text("Оголошення скасовано. 😞", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# --- Адміністративні команди --- #

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /broadcast для розсилки повідомлень (тільки для адміністратора)."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 Недостатньо прав для виконання цієї команди.")
        return
    if context.args:
        message_to_broadcast = " ".join(context.args)
        # Замініть CHANNEL_ID на фактичний ID каналу або групи для розсилки
        CHANNEL_ID = -1001234567890  
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=message_to_broadcast)
            await update.message.reply_text("✅ Повідомлення відправлено до каналу.")
        except Exception as e:
            logger.error(f"Помилка розсилки: {e}")
            await update.message.reply_text("🚫 Помилка при відправленні повідомлення.")
    else:
        await update.message.reply_text("Введіть текст повідомлення після команди /broadcast.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /stats для отримання статистики (тільки для адміністратора)."""
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
        # Якщо потрібно, можна встановити додатковий параметр per_message=True
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats))

    # Налаштування запуску: використання webhook або polling
    port = int(os.environ.get("PORT", "8443"))
    HEROKU_APP_NAME = os.environ.get("HEROKU_APP_NAME")
    if HEROKU_APP_NAME:
        webhook_url = f"https://{HEROKU_APP_NAME}.herokuapp.com/{BOT_TOKEN}"
        await application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url,
            close_loop=False,  # Вказуємо, щоб не закривати event loop
        )
    else:
        await application.run_polling(close_loop=False)  # Параметр close_loop=False

if __name__ == "__main__":
    asyncio.run(main())
