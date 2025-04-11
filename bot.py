import os
import logging
import nest_asyncio  # Для уникнення проблем із event loop

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

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Стан розмови
AD_DETAILS, CONFIRMATION1, CONFIRMATION2 = range(3)

# Дані бота та адміністратора
BOT_TOKEN = "7574826063:AAF4bq0_bvC1jSl0ynrWyaH_fGtyLi7j5Cw"
ADMIN_ID = 2045410830

# Лічильник оголошень
announcement_count = 0

def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обробка команди /start — відправляє привітальне повідомлення з картинкою
    та кнопкою для розміщення оголошення.
    """
    image_url = "https://i.ibb.co/Y7k6mN9G/image.png"
    welcome_text = (
        "Привіт! 😊 Ласкаво просимо до бота для швидкого розміщення оголошень!\n\n"
        "За допомогою цього бота ви можете легко опублікувати ваше оголошення.\n"
        "Вартість розміщення оголошення 200 грн.\n\n"
        "Натисніть кнопку нижче, щоб почати."
    )
    keyboard = [[InlineKeyboardButton("Розмістити оголошення 📢", callback_data="post_ad")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_photo(photo=image_url, caption=welcome_text, reply_markup=reply_markup)
    return ConversationHandler.END

def post_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обробка натискання кнопки «Розмістити оголошення».
    Пропонуємо користувачу відправити всі дані одним повідомленням:
    фото (за бажанням), опис, ціну, номер телефону та ім'я.
    """
    query = update.callback_query
    query.answer()
    instructions = (
        "Будь ласка, надішліть одним повідомленням:\n"
        "• Фото (за бажанням)\n"
        "• Опис оголошення\n"
        "• Ціну\n"
        "• Номер телефону\n"
        "• Ім'я\n\n"
        "Наприклад:\n"
        "«Продається велосипед, 5000 грн, Телефон: 123456789, Ім'я: Іван».\n"
        "Якщо додаєте фото, текст додайте до підпису."
    )
    query.message.reply_text(instructions)
    return AD_DETAILS

def ad_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отримуємо дані оголошення від користувача (фото + підпис або лише текст).
    Зберігаємо отримані дані й показуємо користувачу перший екран підтвердження.
    """
    if update.message.photo:
        photo_file = update.message.photo[-1]
        context.user_data["photo"] = photo_file.file_id
        ad_text = update.message.caption
        if not ad_text:
            update.message.reply_text(
                "Ви надіслали фото без підпису.\nБудь ласка, додайте опис (текст) у підпис до фото."
            )
            return AD_DETAILS
    else:
        context.user_data["photo"] = None
        ad_text = update.message.text

    context.user_data["ad_text"] = ad_text

    preview_text = (
        "Ви надали такі дані:\n\n"
        f"{ad_text}\n\n"
        "Підтвердити чи скасувати?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Підтвердити", callback_data="confirm1")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if context.user_data["photo"]:
        update.message.reply_photo(
            photo=context.user_data["photo"],
            caption=preview_text,
            reply_markup=reply_markup
        )
    else:
        update.message.reply_text(preview_text, reply_markup=reply_markup)

    return CONFIRMATION1

def confirmation_handler_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Перший крок підтвердження: якщо користувач підтверджує, відправляємо
    фінальний прев’ю оголошення, яке виглядатиме в каналі.
    У випадку скасування використовуємо edit_message_caption (якщо фото є)
    або edit_message_text.
    """
    query = update.callback_query
    query.answer()
    if query.data == "confirm1":
        final_preview_text = (
            "Нове оголошення:\n\n"
            f"{context.user_data.get('ad_text')}"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Підтвердити публікацію", callback_data="publish")],
            [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if context.user_data["photo"]:
            query.message.reply_photo(
                photo=context.user_data["photo"],
                caption=final_preview_text,
                reply_markup=reply_markup
            )
        else:
            query.message.reply_text(final_preview_text, reply_markup=reply_markup)
        return CONFIRMATION2
    else:
        if query.message.photo:
            query.edit_message_caption("Оголошення скасовано. Якщо бажаєте, почніть заново, натиснувши /start.")
        else:
            query.edit_message_text("Оголошення скасовано. Якщо бажаєте, почніть заново, натиснувши /start.")
        return ConversationHandler.END

def confirmation_handler_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Фінальне підтвердження: при згоді оголошення надсилається адміністратору,
    а користувачу відправляється повідомлення:
    "Дякуємо! Ваше оголошення обробляється. Очікуйте — ми з вами зв’яжемося."
    При скасуванні застосовується аналогічне редагування повідомлення.
    """
    query = update.callback_query
    query.answer()
    if query.data == "publish":
        global announcement_count
        announcement_count += 1

        admin_message = (
            "Нове оголошення:\n\n"
            f"{context.user_data.get('ad_text')}\n\n"
            f"Зв'язатися з користувачем: tg://user?id={update.effective_user.id}"
        )
        try:
            if context.user_data["photo"]:
                context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=context.user_data["photo"],
                    caption=admin_message
                )
            else:
                context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
        except Exception as e:
            logger.error(f"Помилка при відправленні оголошення адміну: {e}")

        final_text = (
            "Дякуємо! Ваше оголошення обробляється.\n"
            "Очікуйте — ми з вами зв’яжемося."
        )
        if query.message.photo:
            query.edit_message_caption(final_text)
        else:
            query.edit_message_text(final_text)
        return ConversationHandler.END
    else:
        if query.message.photo:
            query.edit_message_caption("Оголошення скасовано. Якщо бажаєте, почніть заново, натиснувши /start.")
        else:
            query.edit_message_text("Оголошення скасовано. Якщо бажаєте, почніть заново, натиснувши /start.")
        return ConversationHandler.END

def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    update.message.reply_text("Оголошення скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- Адміністративні команди --- #

def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        update.message.reply_text("🚫 Недостатньо прав для виконання цієї команди.")
        return

    if context.args:
        message_to_broadcast = " ".join(context.args)
        CHANNEL_ID = -1001234567890  # Замініть на фактичний ID каналу або групи
        try:
            context.bot.send_message(chat_id=CHANNEL_ID, text=message_to_broadcast)
            update.message.reply_text("✅ Повідомлення відправлено до каналу.")
        except Exception as e:
            logger.error(f"Помилка розсилки: {e}")
            update.message.reply_text("🚫 Помилка при відправленні повідомлення.")
    else:
        update.message.reply_text("Введіть текст повідомлення після команди /broadcast.")

def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        update.message.reply_text("🚫 Недостатньо прав для виконання цієї команди.")
        return
    update.message.reply_text(f"📊 Статистика:\nКількість оголошень: {announcement_count}")

def main():
    """
    Основна функція запуску бота.
    Використовує webhook (якщо працюємо на Heroku) або polling.
    """
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(post_ad_callback, pattern="^post_ad$"),
            CommandHandler("start", start),
        ],
        states={
            AD_DETAILS: [MessageHandler(filters.TEXT | filters.PHOTO, ad_details_handler)],
            CONFIRMATION1: [CallbackQueryHandler(confirmation_handler_1, pattern="^(confirm1|cancel)$")],
            CONFIRMATION2: [CallbackQueryHandler(confirmation_handler_2, pattern="^(publish|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats))

    port = int(os.environ.get("PORT", "8443"))
    HEROKU_APP_NAME = os.environ.get("HEROKU_APP_NAME")
    if HEROKU_APP_NAME:
        webhook_url = f"https://{HEROKU_APP_NAME}.herokuapp.com/{BOT_TOKEN}"
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url,
            close_loop=False,
        )
    else:
        application.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
