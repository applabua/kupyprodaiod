import os
import logging
import asyncio
import nest_asyncio  # для унеможливлення помилки закриття запущеного event loop

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обробка команди /start — надсилає привітальне повідомлення з картинкою
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

    await update.message.reply_photo(
        photo=image_url,
        caption=welcome_text,
        reply_markup=reply_markup
    )
    return ConversationHandler.END


async def post_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обробка натискання кнопки «Розмістити оголошення».
    Пропонуємо користувачу відправити все одним повідомленням:
    фото (якщо потрібно), опис, ціну, телефон та ім’я.
    """
    query = update.callback_query
    await query.answer()

    instructions = (
        "Будь ласка, надішліть одним повідомленням:\n"
        "• Фото (за бажанням)\n"
        "• Опис оголошення\n"
        "• Ціну\n"
        "• Номер телефону\n"
        "• Ім'я\n\n"
        "Наприклад:\n"
        "«Продається велосипед, 5000 грн, Телефон: 123456789, Ім'я: Іван».\n"
        "Якщо додаєте фото, текст розмістіть у «підписі» до фото."
    )
    await query.message.reply_text(instructions)
    return AD_DETAILS


async def ad_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отримуємо дані оголошення від користувача (фото + підпис, або лише текст).
    Зберігаємо в user_data, показуємо перший екран підтвердження.
    """
    if update.message.photo:
        # Якщо є фото
        photo_file = update.message.photo[-1]
        context.user_data["photo"] = photo_file.file_id
        ad_text = update.message.caption
        if not ad_text:
            await update.message.reply_text(
                "Ви надіслали фото без підпису.\nБудь ласка, додайте опис (текст) у підпис до фото."
            )
            return AD_DETAILS
    else:
        # Якщо немає фото, зберігаємо лише текст
        context.user_data["photo"] = None
        ad_text = update.message.text

    context.user_data["ad_text"] = ad_text

    # Перше підтвердження (скоротимо, але покажемо фото, якщо є)
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
        await update.message.reply_photo(
            photo=context.user_data["photo"],
            caption=preview_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(preview_text, reply_markup=reply_markup)

    return CONFIRMATION1


async def confirmation_handler_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обробка першого підтвердження. Якщо «підтвердити» — показуємо
    фінальний вигляд (друге підтвердження).
    """
    query = update.callback_query
    await query.answer()

    if query.data == "confirm1":
        # Формуємо прев’ю, як воно виглядатиме в каналі:
        final_preview_text = (
            "Нове оголошення:\n\n"
            f"{context.user_data.get('ad_text')}"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Підтвердити публікацію", callback_data="publish")],
            [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Відправляємо фінальний вигляд
        if context.user_data["photo"]:
            await query.message.reply_photo(
                photo=context.user_data["photo"],
                caption=final_preview_text,
                reply_markup=reply_markup
            )
        else:
            await query.message.reply_text(final_preview_text, reply_markup=reply_markup)

        return CONFIRMATION2
    else:
        # Скасування
        await query.edit_message_text("Оголошення скасовано. Якщо бажаєте, почніть заново, натиснувши /start.")
        return ConversationHandler.END


async def confirmation_handler_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Фінальне підтвердження: надсилаємо оголошення адміністратору,
    надсилаємо користувачеві повідомлення про обробку.
    """
    query = update.callback_query
    await query.answer()

    if query.data == "publish":
        global announcement_count
        announcement_count += 1

        # Формуємо повідомлення для адміністратора
        admin_message = (
            "Нове оголошення:\n\n"
            f"{context.user_data.get('ad_text')}\n\n"
            f"Зв'язатися з користувачем: tg://user?id={update.effective_user.id}"
        )

        # Надсилаємо адміністратору
        try:
            if context.user_data["photo"]:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=context.user_data["photo"],
                    caption=admin_message
                )
            else:
                await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
        except Exception as e:
            logger.error(f"Помилка при відправленні оголошення адміну: {e}")

        # Повідомляємо користувача
        final_text = (
            "Дякуємо! Ваше оголошення обробляється.\n"
            "Очікуйте — ми з вами зв’яжемося."
        )
        await query.edit_message_text(final_text)
        return ConversationHandler.END
    else:
        # Скасування
        await query.edit_message_text("Оголошення скасовано. Якщо бажаєте, почніть заново, натиснувши /start.")
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Вихід з розмови / скасування.
    """
    await update.message.reply_text("Оголошення скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# --- Адміністративні команди --- #

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда /broadcast для розсилки повідомлень (тільки для адміністратора).
    """
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
    """
    Команда /stats для отримання статистики (тільки для адміністратора).
    """
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 Недостатньо прав для виконання цієї команди.")
        return

    await update.message.reply_text(f"📊 Статистика:\nКількість оголошень: {announcement_count}")


async def main() -> None:
    """
    Основна функція запуску бота.
    Визначаємо, чи запускаємося на Heroku (webhook) чи локально (polling).
    """
    application = Application.builder().token(BOT_TOKEN).build()

    # Налаштовуємо ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(post_ad_callback, pattern="^post_ad$"),
            CommandHandler("start", start),
        ],
        states={
            AD_DETAILS: [
                MessageHandler(filters.TEXT | filters.PHOTO, ad_details_handler),
            ],
            CONFIRMATION1: [
                CallbackQueryHandler(confirmation_handler_1, pattern="^(confirm1|cancel)$"),
            ],
            CONFIRMATION2: [
                CallbackQueryHandler(confirmation_handler_2, pattern="^(publish|cancel)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Додаємо обробники
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats))

    # Запуск: webhook або polling
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
