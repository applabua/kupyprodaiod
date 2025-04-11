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

# ----------------------------------------------
# 1) Общая настройка и глобальные переменные
# ----------------------------------------------
nest_asyncio.apply()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога для объявления
COLLECT, CONFIRM1, CONFIRM2 = range(3)

# Состояния диалога для рассылки (начиная с числа, не конфликтующего с объявлением)
BROADCAST_TEXT = 10
BROADCAST_BUTTON_CHOICE = 11
BROADCAST_BUTTON_LABEL = 12
BROADCAST_BUTTON_URL = 13

# ==== ВАЖНО! Укажите актуальный токен вашего бота ====
BOT_TOKEN = "7574826063:AAF4bq0_bvC1jSl0ynrWyaH_fGtyLi7j5Cw"

# ID вашего Telegram-аккаунта (для команд /broadcast и /stats)
ADMIN_ID = 2045410830

# Счётчик объявлений
announcement_count = 0

# ----------------------------------------------
# 2) Команды для работы с объявлениями (как прежде)
# ----------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отправляет фото с приветственным текстом и кнопкой "Розмістити оголошення 📢".
    """
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

async def post_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Инструкции по отправке данных объявления.
    """
    query = update.callback_query
    await query.answer()
    instructions = (
        "Будь ласка, надішліть усі дані для вашого оголошення (у довільному порядку):\n"
        "📸 Фото (за бажанням)\n"
        "📝 Опис оголошення\n"
        "💰 Ціна\n"
        "📞 Номер телефону\n"
        "👤 Ім'я\n\n"
        "Введіть /done, коли завершите введення."
    )
    context.user_data["photo"] = None
    context.user_data["ad_text"] = ""
    await query.message.reply_text(instructions)
    return COLLECT

async def collect_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохраняет фото и текст. При вводе /done переходит к подтверждению.
    """
    if update.message.photo:
        photo_file = update.message.photo[-1]
        context.user_data["photo"] = photo_file.file_id

        caption = update.message.caption
        if caption:
            context.user_data["ad_text"] += ("\n" + caption) if context.user_data["ad_text"] else caption

        await update.message.reply_text("📸 Фото збережено! Якщо потрібно, надішліть ще текст чи фото. /done для завершення.")
        return COLLECT

    elif update.message.text:
        text = update.message.text.strip()
        if text.lower() == "/done":
            if not context.user_data["ad_text"] and not context.user_data["photo"]:
                await update.message.reply_text("❗️ Ви не додали жодної інформації. Будь ласка, спробуйте ще раз.")
                return COLLECT
            return await show_confirmation_1(update, context)
        else:
            context.user_data["ad_text"] += ("\n" + text) if context.user_data["ad_text"] else text
            await update.message.reply_text("📝 Текст збережено! Можете надсилати ще або /done, щоб продовжити.")
            return COLLECT

    else:
        await update.message.reply_text("❗️ Будь ласка, надішліть лише фото або текст. /done для завершення.")
        return COLLECT

async def show_confirmation_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает предварительный просмотр введённого объявления с кнопками подтверждения.
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
    effective_message = update.message or update.effective_message
    await effective_message.reply_text("Ось попередній перегляд👇")
    if context.user_data["photo"]:
        await effective_message.reply_photo(
            photo=context.user_data["photo"],
            caption=preview_text,
            reply_markup=reply_markup
        )
    else:
        await effective_message.reply_text(preview_text, reply_markup=reply_markup)
    return CONFIRM1

async def confirmation_handler_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает первый выбор: подтверждение (переход к финальному просмотру) или отмена.
    """
    query = update.callback_query
    await query.answer()
    if query.data == "confirm1":
        return await show_confirmation_2(query, context)
    else:
        if query.message.photo:
            await query.edit_message_caption("❌ Оголошення скасовано. Почніть заново командою /start.")
        else:
            await query.edit_message_text("❌ Оголошення скасовано. Почніть заново командою /start.")
        return ConversationHandler.END

async def show_confirmation_2(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показывает финальный вид объявления (как оно будет опубликовано).
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
    """
    Принимает окончательное решение пользователя: публиковать объявление или отменить.
    """
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
            await query.edit_message_caption("❌ Оголошення скасовано. Спробуйте ще раз /start.")
        else:
            await query.edit_message_text("❌ Оголошення скасовано. Спробуйте ще раз /start.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Завершает разговор и очищает клавиатуру.
    """
    effective_message = update.message or update.effective_message
    await effective_message.reply_text("❌ Оголошення скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ----------------------------------------------
# 3) Реализация интерактивного бродкаста для ADMIN
# ----------------------------------------------
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Начало диалога для рассылки. Проверяет права администратора и запрашивает текст сообщения.
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 У вас немає прав для виконання цієї команди.")
        return ConversationHandler.END
    await update.message.reply_text("Введіть текст повідомлення для розсилки:")
    return BROADCAST_TEXT

async def broadcast_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохраняет текст сообщения для рассылки и спрашивает, нужна ли кнопка-ссилка.
    """
    text = update.message.text.strip()
    context.user_data["broadcast_text"] = text

    keyboard = [
        [InlineKeyboardButton("Так", callback_data="button_yes")],
        [InlineKeyboardButton("Ні", callback_data="button_no")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Бажаєте додати кнопку з посиланням під повідомленням?", reply_markup=reply_markup)
    return BROADCAST_BUTTON_CHOICE

async def broadcast_button_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обрабатывает выбор — добавлять кнопку или нет.
    """
    query = update.callback_query
    await query.answer()
    if query.data == "button_yes":
        await query.edit_message_text("Введіть назву кнопки:")
        return BROADCAST_BUTTON_LABEL
    else:
        # Если кнопка не нужна – переходим к отправке сообщения
        return await broadcast_final(update, context)

async def broadcast_button_label_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохраняет название кнопки и запрашивает URL для кнопки.
    """
    button_label = update.message.text.strip()
    context.user_data["broadcast_button_label"] = button_label
    await update.message.reply_text("Введіть URL для кнопки:")
    return BROADCAST_BUTTON_URL

async def broadcast_button_url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохраняет URL кнопки и отправляет сообщение в канал.
    """
    button_url = update.message.text.strip()
    context.user_data["broadcast_button_url"] = button_url
    return await broadcast_final(update, context)

async def broadcast_final(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отправляет сообщение в заданный канал, добавляя кнопку если она указана.
    """
    # Обновлённый ID канала
    CHANNEL_ID = 1002647717586  
    text = context.user_data.get("broadcast_text", "")
    # Если были переданы данные для кнопки, создаём разметку
    if "broadcast_button_label" in context.user_data and "broadcast_button_url" in context.user_data:
        button_label = context.user_data["broadcast_button_label"]
        button_url = context.user_data["broadcast_button_url"]
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(button_label, url=button_url)]])
    else:
        reply_markup = None

    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, reply_markup=reply_markup)
        # Ответ админу: сообщение отправлено
        if update.callback_query:
            await update.callback_query.edit_message_text("✅ Повідомлення успішно відправлено.")
        else:
            await update.message.reply_text("✅ Повідомлення успішно відправлено.")
    except Exception as e:
        logger.error(f"Помилка розсилки: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text("🚫 Помилка при розсилці повідомлення.")
        else:
            await update.message.reply_text("🚫 Помилка при розсилці повідомлення.")

    return ConversationHandler.END

async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отмена рассылки.
    """
    await update.message.reply_text("Розсилка скасована.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ----------------------------------------------
# 4) Команда статистики (как прежде)
# ----------------------------------------------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /stats: Статистика (только ADMIN_ID).
    """
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 У вас немає прав для виконання цієї команди.")
        return
    await update.message.reply_text(f"📊 Статистика:\nКількість оголошень: {announcement_count}")

# ----------------------------------------------
# 5) Основная функция main() для запуска (webhook / polling)
# ----------------------------------------------
async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Диалог для работы с объявлениями
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
        per_chat=True
    )
    application.add_handler(conv_handler)

    # Диалог для рассылки (broadcast) с кнопочным выбором для кнопки-ссылки
    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_text_handler)],
            BROADCAST_BUTTON_CHOICE: [CallbackQueryHandler(broadcast_button_choice_handler, pattern="^(button_yes|button_no)$")],
            BROADCAST_BUTTON_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_button_label_handler)],
            BROADCAST_BUTTON_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_button_url_handler)],
        },
        fallbacks=[CommandHandler("cancel", broadcast_cancel)],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(broadcast_handler)

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

# Точка входа – запуск main() асинхронно
if __name__ == "__main__":
    asyncio.run(main())
