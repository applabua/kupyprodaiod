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

# Константи для станів діалогу (оновлено)
AD_DETAILS, CONFIRMATION1, CONFIRMATION2 = range(3)

# Дані бота та адміністратора
BOT_TOKEN = "7574826063:AAF4bq0_bvC1jSl0ynrWyaH_fGtyLi7j5Cw"
ADMIN_ID = 2045410830

# Лічильник оголошень
announcement_count = 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка команди /start — відправляє привітання з картинкою."""
    image_url = "https://i.ibb.co/Y7k6mN9G/image.png"
    welcome_text = (
        "Привіт! 😊 Ласкаво просимо до бота для швидкого розміщення оголошення!\n\n"
        "За допомогою цього бота ви можете легко та швидко опублікувати ваше оголошення.\n"
        "Розміщення оголошення коштує лише 200 грн. 🛍️\n\n"
        "Натисніть кнопку нижче, щоб розпочати."
    )
    keyboard = [[InlineKeyboardButton("Розмістити оголошення 📢", callback_data="post_ad")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_photo(photo=image_url, caption=welcome_text, reply_markup=reply_markup)
    return ConversationHandler.END

async def post_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Старт процесу розміщення оголошення після натискання кнопки."""
    query = update.callback_query
    await query.answer()
    prompt_text = (
        "📣 Будь ласка, надішліть ваше оголошення в одному повідомленні.\n\n"
        "Ви можете додати фото (якщо потрібно) та вказати опис, ціну, номер телефону, ім'я "
        "та посилання, якщо потрібно.\n\n"
        "Наприклад:\n"
        "Опис: Продається велосипед, 5000 грн\n"
        "Телефон: 123456789\n"
        "Ім'я: Іван\n"
        "Посилання: www.example.com\n\n"
        "Надішліть, будь ласка, деталі вашого оголошення."
    )
    await query.message.reply_text(prompt_text)
    return AD_DETAILS

async def ad_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обробка даних оголошення.
    Якщо фото надіслано, зберігається file_id, а текст – з caption.
    Якщо немає фото – зберігається текст повідомлення.
    """
    if update.message.photo:
        photo_file = update.message.photo[-1]
        context.user_data["photo"] = photo_file.file_id
        ad_text = update.message.caption
        if not ad_text:
            await update.message.reply_text("Будь ласка, додайте також текст оголошення у опис фото.")
            return AD_DETAILS
    else:
        context.user_data["photo"] = None
        ad_text = update.message.text
    context.user_data["ad_text"] = ad_text
    summary = (
        "📋 Ось ваші дані оголошення:\n\n"
        f"🖼 Фото: {'✅' if context.user_data['photo'] else '❌'}\n"
        f"📝 Деталі оголошення: {ad_text}\n"
        f"💰 Ціна розміщення: 200 грн\n\n"
        "Підтвердіть, чи всі дані вірні."
    )
    keyboard = [
        [InlineKeyboardButton("✅ Підтвердити", callback_data="confirm1")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(summary, reply_markup=reply_markup)
    return CONFIRMATION1

async def confirmation1_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Перший крок підтвердження – показ даних для перевірки."""
    query = update.callback_query
    await query.answer()
    if query.data == "confirm1":
        preview = (
            "🆕 Прев'ю вашого оголошення:\n\n"
            f"📝 {context.user_data.get('ad_text')}\n"
            f"💰 Ціна розміщення: 200 грн"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Публікувати", callback_data="publish")],
            [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if context.user_data.get("photo"):
            await query.message.reply_photo(photo=context.user_data.get("photo"), caption=preview, reply_markup=reply_markup)
        else:
            await query.message.reply_text(preview, reply_markup=reply_markup)
        return CONFIRMATION2
    else:
        await query.edit_message_text("Оголошення скасовано. Якщо бажаєте, почніть заново, натиснувши /start.")
        return ConversationHandler.END

async def confirmation2_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Фінальне підтвердження – після нього оголошення надсилається адміністратору."""
    query = update.callback_query
    await query.answer()
    if query.data == "publish":
        global announcement_count
        announcement_count += 1

        admin_message = (
            "🆕 Нове оголошення:\n\n"
            f"📝 Деталі: {context.user_data.get('ad_text')}\n"
            f"💰 Ціна розміщення: 200 грн\n"
            f"🔗 Зв'язатися з користувачем: tg://user?id={update.effective_user.id}"
        )
        try:
            if context.user_data.get("photo"):
                await context.bot.send_photo(chat_id=ADMIN_ID, photo=context.user_data.get("photo"), caption=admin_message)
            else:
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
        except Exception as e:
            logger.error(f"Помилка при відправленні оголошення адміну: {e}")
        await query.edit_message_text("Дякуємо! Ваше оголошення обробляється та скоро буде опубліковано. 😊")
        return ConversationHandler.END
    else:
        await query.edit_message_text("Оголошення скасовано. Якщо бажаєте, почніть заново, натиснувши /start.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда для скасування процесу розміщення оголошення."""
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
            AD_DETAILS: [MessageHandler(filters.TEXT | filters.PHOTO, ad_details_handler)],
            CONFIRMATION1: [CallbackQueryHandler(confirmation1_handler, pattern="^(confirm1|cancel)$")],
            CONFIRMATION2: [CallbackQueryHandler(confirmation2_handler, pattern="^(publish|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
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
            close_loop=False,
        )
    else:
        await application.run_polling(close_loop=False)

if __name__ == "__main__":
    asyncio.run(main())
