import os
import logging
import asyncio
import nest_asyncio  # для работы с event loop в Heroku

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    LabeledPrice,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    PreCheckoutQueryHandler,
    filters,
)

# Применяем nest_asyncio для корректного функционирования event loop
nest_asyncio.apply()

# Ссылка на проект на GitHub:
# https://applabua.github.io/kupyprodaiod/

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы состояний разговора
AD_DETAILS, CONFIRMATION = range(1, 3)  # AD_DETAILS = 1, CONFIRMATION = 2

# Данные бота и администратора
BOT_TOKEN = "7574826063:AAF4bq0_bvC1jSl0ynrWyaH_fGtyLi7j5Cw"
ADMIN_ID = 2045410830

# Токен платёжного провайдера (замените на реальный, полученный от Telegram)
PAYMENT_PROVIDER_TOKEN = "PROVIDER_TOKEN_HERE"  # Замените на реальный токен

# --------------------- Команды бота --------------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка команды /start.
    Отправляет приветственное сообщение с картинкой, информирующее о возможности быстрого размещения объявления
    и указывающее стоимость (300 грн). В сообщении присутствует кнопка для размещения объявления.
    """
    greeting_text = (
        "Привіт!\n\n"
        "За допомогою цього бота ви можете швидко розмістити своє оголошення.\n"
        "Вартість розміщення оголошення – 300 грн.\n\n"
        "Натисніть кнопку нижче, щоб розпочати."
    )
    keyboard = [
        [InlineKeyboardButton("Розмістити оголошення 📢", callback_data="post_ad")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Отправляем картинку с приветствием
    if update.message:
        await update.message.reply_photo(
            photo="https://i.ibb.co/Y7k6mN9G/image.png",
            caption=greeting_text,
            reply_markup=reply_markup,
        )
    else:
        # Если update пришёл не как сообщение, отправим текст
        await update.effective_chat.send_message(greeting_text, reply_markup=reply_markup)
    return ConversationHandler.END


async def post_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка нажатия кнопки "Розмістити оголошення".
    Просит пользователя отправить объявление одним сообщением, в котором должны быть:
    – Фото (якщо є), опис, ціна, номер телефону, ім'я та посилання.
    """
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Будь ласка, надішліть ваше оголошення одним повідомленням.\n"
        "Повідомлення має містити фото (якщо є), опис, ціну, номер телефону, ваше ім'я та посилання."
    )
    return AD_DETAILS


async def ad_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка введённых пользователем данных объявления.
    Если есть прикреплённое фото, сохраняем его file_id и используем подпись как детали объявления;
    иначе — используем текст сообщения.
    После сохранения показываем предпросмотр объявления и просим подтвердить.
    """
    if update.message.photo:
        # Сохраняем фото и используем caption как описание (если имеется)
        context.user_data["photo"] = update.message.photo[-1].file_id
        if update.message.caption:
            context.user_data["ad_details"] = update.message.caption
        else:
            context.user_data["ad_details"] = "Без опису"
    else:
        context.user_data["photo"] = None
        context.user_data["ad_details"] = update.message.text

    preview_text = (
        "Ось як буде виглядати ваше оголошення:\n\n"
        f"{context.user_data['ad_details']}\n\n"
        "Вартість розміщення оголошення: 300 грн.\n\n"
        "Підтвердіть, будь ласка, якщо всі дані вірні."
    )
    keyboard = [
        [InlineKeyboardButton("Підтвердити", callback_data="confirm_ad")],
        [InlineKeyboardButton("Скасувати", callback_data="cancel_ad")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if context.user_data.get("photo"):
        await update.message.reply_photo(
            photo=context.user_data["photo"],
            caption=preview_text,
            reply_markup=reply_markup,
        )
    else:
        await update.message.reply_text(preview_text, reply_markup=reply_markup)
    return CONFIRMATION


async def ad_confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка подтверждения предпросмотра объявления.
    Если пользователь подтверждает, отправляется инвойс для оплаты.
    Если отменяет — объявление счищается.
    """
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_ad":
        # Отправляем инвойс на оплату 300 грн.
        prices = [LabeledPrice("Оплата розміщення оголошення", 30000)]  # 300 грн * 100
        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title="Оплата розміщення оголошення",
            description="Оплатіть 300 грн для розміщення оголошення",
            payload="ad_payment",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="UAH",
            prices=prices,
            start_parameter="ad_payment",
        )
        await query.edit_message_text("Інвойс відправлено. Будь ласка, здійсніть оплату.")
        return ConversationHandler.END
    else:
        await query.edit_message_text("Оголошення скасовано. Якщо бажаєте, почніть заново, натиснувши /start.")
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка команды /cancel — завершение процесса создания объявления.
    """
    await update.message.reply_text("Оголошення скасовано. 😞", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# --------------------- Обработчики платежей --------------------- #

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка pre-checkout запроса, отвечаем OK для продолжения оплаты.
    """
    query = update.pre_checkout_query
    try:
        await query.answer(ok=True)
    except Exception as e:
        logger.error(f"PreCheckoutQuery error: {e}")


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка успешного платежа.
    После оплаты отправляются данные объявления админу, а пользователю – уведомление об успешной оплате.
    """
    user_data = context.user_data
    order_details = "Нове оголошення:\n\n"
    if user_data.get("photo"):
        order_details += "Фото: є\n"
    else:
        order_details += "Фото: відсутнє\n"
    order_details += f"Деталі оголошення: {user_data.get('ad_details', '')}\n"
    order_details += f"Користувач: {update.effective_user.full_name} (ID: {update.effective_user.id})"
    try:
        if user_data.get("photo"):
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=user_data["photo"], caption=order_details)
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text=order_details)
    except Exception as e:
        logger.error(f"Помилка при відправленні оголошення адміну: {e}")
    await update.message.reply_text("Ваше оголошення успішно оплачено та відправлено на модерацію. Дякуємо!")
    # Очищаем данные пользователя, если необходимо
    context.user_data.clear()


# --------------------- Главная функция --------------------- #

async def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(post_ad_callback, pattern="^post_ad$"),
            CommandHandler("start", start),
        ],
        states={
            AD_DETAILS: [MessageHandler(filters.TEXT | filters.PHOTO, ad_details_handler)],
            CONFIRMATION: [CallbackQueryHandler(ad_confirmation_callback, pattern="^(confirm_ad|cancel_ad)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    # Обработчики платежей
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # Настройка запуска: через webhook (если задан HEROKU_APP_NAME) или polling
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
