import os
import logging
import asyncio
import nest_asyncio

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

# --------------------------------------------------------------------
#            1. БАЗОВІ НАЛАШТУВАННЯ ТА ГЛОБАЛЬНІ ЗМІННІ
# --------------------------------------------------------------------
# Дозволяємо повторне використання існуючого event-loop (Heroku/Jupyter)
nest_asyncio.apply()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Стан розмови
COLLECT, CONFIRM1, CONFIRM2 = range(3)

# Дані бота та адміністратора
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7574826063:AAF4bq0_bvC1jSl0ynrWyaH_fGtyLi7j5Cw")
ADMIN_ID = 2045410830  # замініть на ваш ідентифікатор

# Лічильник (умовна статистика)
announcement_count = 0

# --------------------------------------------------------------------
#                    2. ХЕНДЛЕРИ СТАРТУ ТА ГОЛОВНОЇ КНОПКИ
# --------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Команда /start: надсилає фото, привітальний текст та кнопку «Розмістити оголошення».
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
    # Повертаємо ConversationHandler.END, бо поки розмова не почалась
    return ConversationHandler.END

async def post_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Починаємо процес збору даних про оголошення.
    Пояснюємо користувачеві, що можна надсилати фото й текст у різних повідомленнях.
    """
    query = update.callback_query
    await query.answer()

    instructions = (
        "Будь ласка, надішліть усе необхідне для оголошення (в довільній послідовності):\n"
        "• Фото (за бажанням)\n"
        "• Опис оголошення\n"
        "• Ціну\n"
        "• Номер телефону\n"
        "• Ім'я\n\n"
        "Якщо спочатку надсилаєте фото без підпису — у наступному повідомленні додайте текст.\n"
        "Можете також надіслати все одразу як фото з підписом.\n"
        "Надішліть /done, коли закінчите або якщо все вже відправили."
    )
    await query.message.reply_text(instructions)

    # Ініціалізуємо user_data
    context.user_data["photo"] = None
    context.user_data["ad_text"] = ""
    return COLLECT

# --------------------------------------------------------------------
#             3. ГОЛОВНИЙ ХЕНДЛЕР ЗБОРУ ДАНИХ (COLLECT)
# --------------------------------------------------------------------
async def collect_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Збирає фото та текст із кількох повідомлень у довільному порядку.
    Користувач надсилає фото і/або текст. Якщо з'являється фото без підпису, зберігаємо file_id.
    Якщо з'являється текст, додаємо його до загального ad_text.
    Якщо користувач набрав /done, переходимо до першого підтвердження.
    """
    if update.message.photo:
        # Якщо в повідомленні є фото
        photo_file = update.message.photo[-1]
        context.user_data["photo"] = photo_file.file_id
        caption = update.message.caption
        if caption:
            # Додаємо caption до загального тексту
            existing_text = context.user_data["ad_text"]
            context.user_data["ad_text"] = existing_text + "\n" + caption
        await update.message.reply_text("Фото збережено. Якщо треба додати ще дані, надішліть текст або інше фото.")
        return COLLECT

    elif update.message.text:
        # Перевіряємо, чи це /done
        if update.message.text.strip().lower() == "/done":
            # Якщо текст відсутній узагалі, просимо додати
            if not context.user_data["ad_text"].strip() and not context.user_data["photo"]:
                await update.message.reply_text(
                    "Ви ще нічого не додали (ані фото, ані текст). Будь ласка, додайте хоч якусь інформацію."
                )
                return COLLECT
            # Інакше переходимо до попереднього перегляду
            return await show_confirmation_1(update, context)

        # Якщо звичайний текст
        existing_text = context.user_data["ad_text"]
        # Додаємо новий текст до існуючого з переносом рядка
        context.user_data["ad_text"] = (existing_text + "\n" + update.message.text).strip()
        await update.message.reply_text("Текст додано. Якщо все, надішліть /done, інакше можна ще додати дані.")
        return COLLECT

    # Якщо прийшло якесь інше повідомлення (документ, стікер тощо)
    await update.message.reply_text("Наразі бот приймає лише фото, текст або команду /done.")
    return COLLECT

# --------------------------------------------------------------------
#                 4. ПЕРШЕ ПІДТВЕРДЖЕННЯ (CONFIRM1)
# --------------------------------------------------------------------
async def show_confirmation_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показує користувачеві перший екран підтвердження:
    - Фото (якщо є)
    - Зібраний текст
    Користувач може підтвердити або скасувати.
    """
    preview_text = (
        "Ось що ви надали:\n\n"
        f"{context.user_data['ad_text']}\n\n"
        "Підтвердити чи скасувати?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Підтвердити", callback_data="confirm1")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Оскільки тут вперше відправляємо прев’ю, робимо це у вигляді нового повідомлення
    if context.user_data["photo"]:
        await update.message.reply_photo(
            photo=context.user_data["photo"],
            caption=preview_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(preview_text, reply_markup=reply_markup)

    return CONFIRM1

async def confirmation_handler_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Якщо користувач натиснув «Підтвердити» — показуємо "фінальний" вигляд (як в каналі).
    Якщо «Скасувати» — редагуємо повідомлення і завершуємо розмову.
    """
    query = update.callback_query
    await query.answer()

    if query.data == "confirm1":
        return await show_confirmation_2(query, context)
    else:
        # Скасування
        if query.message.photo:
            # Якщо це фотоповідомлення з caption
            await query.edit_message_caption("Оголошення скасовано. Якщо бажаєте, почніть заново /start.")
        else:
            await query.edit_message_text("Оголошення скасовано. Якщо бажаєте, почніть заново /start.")
        return ConversationHandler.END

# --------------------------------------------------------------------
#               5. ДРУГЕ (ФІНАЛЬНЕ) ПІДТВЕРДЖЕННЯ (CONFIRM2)
# --------------------------------------------------------------------
async def show_confirmation_2(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Відправляє "фінальне прев’ю" повідомлення: саме так воно виглядатиме у каналі.
    """
    final_preview_text = (
        "Нове оголошення:\n\n"
        f"{context.user_data['ad_text']}"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data="publish")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Надсилаємо нове повідомлення з прев’ю (щоб не плутатися з редагуванням)
    if context.user_data["photo"]:
        # Відправляємо нове повідомлення у тому ж чаті
        await query.message.reply_photo(
            photo=context.user_data["photo"],
            caption=final_preview_text,
            reply_markup=reply_markup
        )
    else:
        await query.message.reply_text(final_preview_text, reply_markup=reply_markup)
    return CONFIRM2

async def confirmation_handler_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Фінальне рішення: якщо «publish» — відправляємо адміну,
    якщо «cancel» — скасовуємо.
    """
    query = update.callback_query
    await query.answer()

    if query.data == "publish":
        global announcement_count
        announcement_count += 1

        # Формуємо повідомлення адміну
        admin_message = (
            "Нове оголошення:\n\n"
            f"{context.user_data['ad_text']}\n\n"
            f"Зв'язатися з користувачем: tg://user?id={query.from_user.id}"
        )
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

        # Повідомляємо користувачу
        thanks_text = (
            "Дякуємо! Ваше оголошення обробляється.\n"
            "Очікуйте — ми з вами зв’яжемося."
        )
        # Якщо це повідомлення з фото
        if query.message.photo:
            await query.edit_message_caption(thanks_text)
        else:
            await query.edit_message_text(thanks_text)

    else:
        # Скасування
        if query.message.photo:
            await query.edit_message_caption("Оголошення скасовано. Якщо бажаєте, почніть заново /start.")
        else:
            await query.edit_message_text("Оголошення скасовано. Якщо бажаєте, почніть заново /start.")

    return ConversationHandler.END

# --------------------------------------------------------------------
#                       6. ФАЛЛБЕК / CANCEL
# --------------------------------------------------------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Якщо користувач увів /cancel у будь-який момент — завершуємо розмову.
    """
    await update.message.reply_text("Оголошення скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --------------------------------------------------------------------
#                    7. АДМІНІСТРАТИВНІ КОМАНДИ
# --------------------------------------------------------------------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Команда /broadcast (лише для ADMIN_ID).
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 Недостатньо прав для виконання цієї команди.")
        return

    if context.args:
        message_to_broadcast = " ".join(context.args)
        # Вкажіть, куди відправляти розсилку (канал/група)
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
    Команда /stats для перегляду кількості оголошень (лише для ADMIN_ID).
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 Недостатньо прав для виконання цієї команди.")
        return

    await update.message.reply_text(f"📊 Статистика:\nКількість оголошень: {announcement_count}")

# --------------------------------------------------------------------
#                       8. MAIN (WEBHOOK / POLLING)
# --------------------------------------------------------------------
async def main():
    """
    Основна асинхронна функція, що створює Application, 
    реєструє хендлери та запускає бота (webhook/polling).
    """
    application = Application.builder().token(BOT_TOKEN).build()

    # Побудова розмови
    conv_handler = ConversationHandler(
        entry_points=[
            # Натискання кнопки «Розмістити оголошення» + /start
            CallbackQueryHandler(post_ad_callback, pattern="^post_ad$"),
            CommandHandler("start", start),
        ],
        states={
            COLLECT: [
                MessageHandler(filters.TEXT | filters.PHOTO, collect_data),
                # Якщо користувач вводить /done (замість тексту)
                # — сам командний хендлер не потрібен, бо ми перевіряємо /done в collect_data
            ],
            CONFIRM1: [
                CallbackQueryHandler(confirmation_handler_1, pattern="^(confirm1|cancel)$"),
            ],
            CONFIRM2: [
                CallbackQueryHandler(confirmation_handler_2, pattern="^(publish|cancel)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
        per_message=True,  # Щоб CallbackQueryHandler відстежувався у кожному повідомленні
    )

    # Реєструємо розмову та адміністративні команди
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats))

    # Запускаємо або Webhook (Heroku) або Polling (локально)
    port = int(os.environ.get("PORT", "8443"))
    HEROKU_APP_NAME = os.environ.get("HEROKU_APP_NAME")
    if HEROKU_APP_NAME:
        webhook_url = f"https://{HEROKU_APP_NAME}.herokuapp.com/{BOT_TOKEN}"
        # Запускаємо webhook
        await application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url,
        )
    else:
        # Запускаємо звичайний long-polling
        await application.run_polling()

# Точка входу
if __name__ == "__main__":
    asyncio.run(main())
