import logging
from telegram import (
    Bot,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InputMediaPhoto
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext
)
import datetime

# =========================================================
# ВАШІ ДАНІ: вставте власний токен та айді адміна
TOKEN = "ВАШ_ТОКЕН"  # <-- Поставте сюди токен вашого бота
ADMIN_ID = 111111111  # <-- Поставте сюди ваш айді
# =========================================================

# Логери (щоб було зручно відстежувати помилки й події)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# СТАНИ ДЛЯ РОЗМОВИ
ASK_PHOTO, ASK_DESCRIPTION, ASK_CONTACT, ASK_CONFIRM = range(4)

# ОСНОВНИЙ ХЕНДЛЕР /start
def start(update: Update, context: CallbackContext) -> int:
    """Коли користувач натискає /start: вітальне повідомлення і кнопка 'Розмістити оголошення'."""
    user = update.message.from_user

    greeting_text = (
        "Привіт, " + "😊" + f" {user.first_name}!\n\n"
        "Це бот для швидкого розміщення оголошень у каналі «Купи/Продай Одеська область».\n"
        f"Вартість одного оголошення: 200 грн {chr(0x1F4B0)}\n\n"
        "Щоб розпочати, натисніть кнопку нижче:"
    )

    keyboard = [
        [InlineKeyboardButton("Розмістити оголошення 📝", callback_data="place_ad")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(greeting_text, reply_markup=reply_markup)
    return ConversationHandler.END

# ОБРОБКА КНОПКИ "Розмістити оголошення"
def place_ad_callback(update: Update, context: CallbackContext) -> int:
    """Починаємо приймати дані від користувача: пропонуємо (за бажанням) надіслати фото."""
    query = update.callback_query
    query.answer()

    text = (
        "Будь ласка, надішліть фото для оголошення (або пропустіть цей крок /skip),\n"
        "або просто надішліть повідомлення без фото, щоб пропустити."
    )
    query.message.reply_text(text)
    return ASK_PHOTO

def ask_photo(update: Update, context: CallbackContext) -> int:
    """Користувач надсилає фото. Зберігаємо file_id і переходимо далі."""
    if update.message.photo:
        # Якщо є фото
        photo_file_id = update.message.photo[-1].file_id
        context.user_data["photo"] = photo_file_id
        update.message.reply_text("Чудово! Фото збережено.\n\nТепер надішліть опис вашого оголошення:")
    else:
        # Якщо надсилає щось не фото
        update.message.reply_text("Не вдалося розпізнати фото. Спробуйте ще раз або пропустіть командою /skip.\n\nЯкщо не потрібно фото, просто введіть /skip")
        return ASK_PHOTO

    return ASK_DESCRIPTION

def skip_photo(update: Update, context: CallbackContext) -> int:
    """Користувач вирішив пропустити фото."""
    context.user_data["photo"] = None
    update.message.reply_text("Гаразд, фото не додаватимемо.\n\nТепер надішліть опис вашого оголошення:")
    return ASK_DESCRIPTION

def ask_description(update: Update, context: CallbackContext) -> int:
    """Отримуємо опис оголошення."""
    description = update.message.text
    context.user_data["description"] = description

    update.message.reply_text("Прийнято! Тепер вкажіть номер телефону або посилання на свій профіль:")
    return ASK_CONTACT

def ask_contact(update: Update, context: CallbackContext) -> int:
    """Отримуємо контакт користувача (телефон або профіль)."""
    contact = update.message.text
    context.user_data["contact"] = contact

    # Переходимо до підтвердження (попередньо формуємо передперегляд)
    return confirm_ad(update, context)

def confirm_ad(update: Update, context: CallbackContext) -> int:
    """Формуємо попередній перегляд оголошення та просимо підтвердити."""
    if update.message:
        # Якщо викликано з ask_contact
        user_input = update.message.text
        # зберігати user_input уже не потрібно, бо ми зробили це вище
    data = context.user_data

    # Формуємо підсумковий текст
    final_text = "Ваше оголошення виглядатиме так:\n\n"
    if data.get("photo"):
        final_text += "Фото: [буде додане]\n"
    final_text += f"Опис: {data.get('description', '')}\n"
    final_text += f"Контакт: {data.get('contact', '')}\n"
    final_text += "\nПідтверджуєте розміщення оголошення?"

    keyboard = [
        [
            InlineKeyboardButton("Підтвердити ✅", callback_data="confirm_yes"),
            InlineKeyboardButton("Скасувати ❌", callback_data="confirm_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(final_text, reply_markup=reply_markup)
    return ASK_CONFIRM

def confirmation_callback(update: Update, context: CallbackContext) -> int:
    """Обробляємо результат підтвердження оголошення користувачем."""
    query = update.callback_query
    query.answer()
    choice = query.data

    if choice == "confirm_yes":
        # Надсилаємо повідомлення користувачеві про успішне прийняття
        query.message.reply_text(
            "Дякуємо! Ваше оголошення прийнято. Очікуйте, ми обробляємо ваше оголошення. " + "✅"
        )
        # Відправляємо адмінові деталі
        send_ad_to_admin(query, context)
    else:
        query.message.reply_text("Ваше оголошення скасовано. Якщо хочете почати спочатку - натисніть /start.")
        # Очищуємо user_data
        context.user_data.clear()

    return ConversationHandler.END

def send_ad_to_admin(query, context: CallbackContext):
    """Відправляємо передперегляд замовлення адміну, з датою та часом, посиланням на чат і т.д."""
    data = context.user_data
    user = query.message.chat  # інформація про користувача

    # Формуємо текст оголошення
    preview_text = "Нове замовлення на оголошення:\n\n"
    if data.get("photo"):
        preview_text += "Фото: [додано]\n"
    preview_text += f"Опис: {data.get('description', '')}\n"
    preview_text += f"Контакт: {data.get('contact', '')}\n"
    preview_text += f"\nДата/Час: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    preview_text += f"Юзер: @{user.username if user.username else user.first_name}\n"
    preview_text += f"ID: {user.id}\n\n"
    preview_text += "Посилання на чат: "
    preview_text += f"tg://user?id={user.id}\n"
    preview_text += "-----------------------"

    bot: Bot = context.bot

    # Якщо є фото, відправляємо першим фото + підпис
    if data.get("photo"):
        bot.send_photo(
            chat_id=ADMIN_ID,
            photo=data["photo"],
            caption=preview_text
        )
    else:
        bot.send_message(
            chat_id=ADMIN_ID,
            text=preview_text
        )

    # Очищуємо контекст (щоб не змішувати наступні спроби)
    context.user_data.clear()


# ==============
# ОБРОБКА КОМАНД АДМІНА
# ==============
def admin_help(update: Update, context: CallbackContext):
    """Команда /admin_help - відображає список команд для адміна."""
    if update.effective_user.id != ADMIN_ID:
        return
    text = (
        "Команди для адміна:\n"
        "/admin_help - список команд\n"
        "/admin_stats - переглянути якусь статистику (демо)\n"
        "/admin_sayhi - бот привітається від імені адміна (демо)\n"
        "та інші ідеї, які можете додати самостійно.\n"
    )
    update.message.reply_text(text)

def admin_stats(update: Update, context: CallbackContext):
    """Команда /admin_stats - умовна статистика (демо)."""
    if update.effective_user.id != ADMIN_ID:
        return
    text = "Статистика (демо):\n- Кількість унікальних користувачів: 42\n- Оголошень сьогодні: 5\n"
    update.message.reply_text(text)

def admin_sayhi(update: Update, context: CallbackContext):
    """Демонстраційна команда для адміна."""
    if update.effective_user.id != ADMIN_ID:
        return
    update.message.reply_text("Привіт від вашого адміна! " + "💙💛")


# ==========================================
# ОСНОВНА ФУНКЦІЯ НАЛАШТУВАННЯ ТА ЗАПУСКУ БОТА
# ==========================================
def main():
    """Запуск бота."""
    updater = Updater(TOKEN, use_context=True)

    dp = updater.dispatcher

    # 1. Команда /start
    dp.add_handler(CommandHandler("start", start))

    # 2. Обробник CallbackQuery від кнопок
    dp.add_handler(CallbackQueryHandler(place_ad_callback, pattern="^place_ad$"))

    # 3. Логіка покрокового збирання оголошення:
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.text & ~Filters.command, ask_photo)],
        states={
            ASK_PHOTO: [
                MessageHandler(Filters.photo, ask_photo),
                CommandHandler("skip", skip_photo),
                MessageHandler(Filters.text & ~Filters.command, ask_photo)
            ],
            ASK_DESCRIPTION: [
                MessageHandler(Filters.text & ~Filters.command, ask_description)
            ],
            ASK_CONTACT: [
                MessageHandler(Filters.text & ~Filters.command, ask_contact)
            ],
            ASK_CONFIRM: [
                CallbackQueryHandler(confirmation_callback, pattern="^(confirm_yes|confirm_no)$")
            ]
        },
        fallbacks=[]
    )
    dp.add_handler(conv_handler)

    # 4. Команди для адміна
    dp.add_handler(CommandHandler("admin_help", admin_help))
    dp.add_handler(CommandHandler("admin_stats", admin_stats))
    dp.add_handler(CommandHandler("admin_sayhi", admin_sayhi))

    # Запускаємо бота
    updater.start_polling()
    logger.info("Bot has started. Press Ctrl+C to stop.")
    updater.idle()

if __name__ == "__main__":
    main()
