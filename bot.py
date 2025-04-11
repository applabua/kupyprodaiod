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

# Разрешаем повторное использование event loop (актуально для Heroku/Jupyter)
nest_asyncio.apply()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
COLLECT, CONFIRM1, CONFIRM2 = range(3)

# Укажите токен бота, полученный от BotFather
BOT_TOKEN = "7574826063:AAF4bq0_bvC1jSl0ynrWyaH_fGtyLi7j5Cw"

# ID администратора (ваш Telegram ID)
ADMIN_ID = 2045410830

announcement_count = 0

# /start: приветствие с изображением и кнопкой
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    image_url = "https://i.ibb.co/Y7k6mN9G/image.png"
    welcome_text = (
        "Привіт! 😊 Ласкаво просимо до бота для швидкого розміщення оголошень! 🚀\n\n"
        "За допомогою цього бота ви можете легко та швидко опублікувати ваше оголошення.\n"
        "Вартість розміщення оголошення — 200 грн. 💰\n\n"
        "Натисніть кнопку нижче, щоб почати 📢"
    )
    keyboard = [[InlineKeyboardButton("Розмістити оголошення 📢", callback_data="post_ad")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_photo(
        photo=image_url,
        caption=welcome_text,
        reply_markup=reply_markup
    )
    return ConversationHandler.END

# Начало сбора данных
async def post_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    instructions = (
        "Будь ласка, надішліть усі дані для вашого оголошення (у довільному порядку):\n"
        "📸 Фото (за бажанням)\n"
        "📝 Опис оголошення\n"
        "💰 Ціна\n"
        "📞 Номер телефону\n"
        "👤 Ім'я\n\n"
        "Якщо спочатку надсилаєте фото без підпису, потім можете надіслати текст окремо.\n"
        "Введіть /done, коли завершите введення."
    )
    await query.message.reply_text(instructions)
    context.user_data["photo"] = None
    context.user_data["ad_text"] = ""
    return COLLECT

# Сбор данных (фото и текст)
async def collect_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.photo:
        photo_file = update.message.photo[-1]
        context.user_data["photo"] = photo_file.file_id
        caption = update.message.caption
        if caption:
            context.user_data["ad_text"] += ("\n" + caption) if context.user_data["ad_text"] else caption
        await update.message.reply_text("📸 Фото збережено! Надсилайте ще текст або фото. Введіть /done для завершення.")
        return COLLECT
    elif update.message.text:
        text = update.message.text.strip()
        if text.lower() == "/done":
            if not context.user_data["ad_text"] and not context.user_data["photo"]:
                await update.message.reply_text("❗️ Ви не додали інформації. Будь ласка, спробуйте ще раз.")
                return COLLECT
            return await show_confirmation_1(update, context)
        else:
            context.user_data["ad_text"] += ("\n" + text) if context.user_data["ad_text"] else text
            await update.message.reply_text("📝 Текст збережено! Надсилайте ще або введіть /done для продовження.")
            return COLLECT
    else:
        await update.message.reply_text("❗️ Надсилайте лише фото або текст. Введіть /done для завершення.")
        return COLLECT

# Первичное подтверждение
async def show_confirmation_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    preview_text = (
        "Ось що ви надали:\n\n"
        f"{context.user_data['ad_text']}\n\n"
        "Підтвердіть чи скасуйте:"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Підтвердити", callback_data="confirm1")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Ось попередній перегляд👇")
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
    query = update.callback_query
    await query.answer()
    if query.data == "confirm1":
        return await show_confirmation_2(query, context)
    else:
        if query.message.photo:
            await query.edit_message_caption("❌ Оголошення скасовано. Почніть заново, ввівши /start.")
        else:
            await query.edit_message_text("❌ Оголошення скасовано. Почніть заново, ввівши /start.")
        return ConversationHandler.END

# Финальное подтверждение
async def show_confirmation_2(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    final_preview_text = (
        "Нове оголошення:\n\n"
        f"{context.user_data['ad_text']}"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Опублікувати", callback_data="publish")],
        [InlineKeyboardButton("❌ Скасувати", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Ось фінальний вигляд👇")
    if context.user_data["photo"]:
        await query.message.reply_photo(
            photo=context.user_data["photo"],
            caption=final_preview_text,
            reply_markup=reply_markup
        )
    else:
        await query.message.reply_text(final_preview_text, reply_markup=reply_markup)
    return CONFIRM2

async def confirmation_handler_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "publish":
        global announcement_count
        announcement_count += 1
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
            logger.error(f"Помилка надсилання оголошення адміну: {e}")
        thanks_text = (
            "Дякуємо! Ваше оголошення обробляється. 🤝\n"
            "Очікуйте — ми з вами зв’яжемося! 📞"
        )
        if query.message.photo:
            await query.edit_message_caption(thanks_text)
        else:
            await query.edit_message_text(thanks_text)
        return ConversationHandler.END
    else:
        if query.message.photo:
            await query.edit_message_caption("❌ Оголошення скасовано. Спробуйте ще раз, ввівши /start.")
        else:
            await query.edit_message_text("❌ Оголошення скасовано. Спробуйте ще раз, ввівши /start.")
        return ConversationHandler.END

# Обработка команды /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Оголошення скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Админ-команды: /broadcast и /stats
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 У вас немає прав для виконання цієї команди.")
        return
    if context.args:
        message_to_broadcast = " ".join(context.args)
        CHANNEL_ID = -1001234567890  # Замените на реальный ID канала/группы
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=message_to_broadcast)
            await update.message.reply_text("✅ Повідомлення успішно відправлено.")
        except Exception as e:
            logger.error(f"Помилка розсилки: {e}")
            await update.message.reply_text("🚫 Помилка при розсилці повідомлення.")
    else:
        await update.message.reply_text("Введіть текст повідомлення після команди /broadcast.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 У вас немає прав для виконання цієї команди.")
        return
    await update.message.reply_text(f"📊 Статистика:\nКількість оголошень: {announcement_count}")

# Основная функция запуска бота (webhook для Heroku или polling)
async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(post_ad_callback, pattern="^post_ad$"),
            CommandHandler("start", start),
        ],
        states={
            COLLECT: [MessageHandler(filters.TEXT | filters.PHOTO, collect_data)],
            CONFIRM1: [CallbackQueryHandler(confirmation_handler_1, pattern="^(confirm1|cancel)$")],
            CONFIRM2: [CallbackQueryHandler(confirmation_handler_2, pattern="^(publish|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
        per_message=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats))

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
        await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
