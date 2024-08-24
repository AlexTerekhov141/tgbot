import logging
import aiohttp
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    Application,
)
from config import TELEGRAM_BOT_TOKEN
from text import get_start_text

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)
logger = logging.getLogger(__name__)


BUTTON_SEND_TEXT_TO_CHAT = 'Отправить текст с кнопки в чат'

async def start(update: Update, _: CallbackContext) -> None:
    name = update.message.from_user.first_name
    if not name:
        name = 'Anonymous user'
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Получить ключ\n", callback_data='buy_key')
            ],
            [
                InlineKeyboardButton(text="Купить подписку\n", callback_data='buy_subscription')
            ],
            [
                InlineKeyboardButton(text="Связаться с Менеджером\n", callback_data='buy_subscription')
            ]
        ]
    )
    await update.message.reply_text(get_start_text(name), reply_markup=keyboard)

async def handle_subscription_choice(update: Update, _: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    # Меню выбора подписки
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 месяц – 250 рублей", callback_data='subscribe_1_month'),
                InlineKeyboardButton(text="3 месяца – 675 рублей (10% скидка)", callback_data='subscribe_3_months')
            ],
            [
                InlineKeyboardButton(text="6 месяцев – 1275 рублей (15% скидка)", callback_data='subscribe_6_months'),
                InlineKeyboardButton(text="12 месяцев – 2250 рублей (25% скидка)", callback_data='subscribe_12_months')
            ]
        ]
    )

    # Отправка сообщения с клавиатурой
    await query.edit_message_text(
        text="⏰ Выберите длительность подписки:",
        reply_markup=keyboard
    )

async def handle_payment(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    subscription_choice = query.data.split('_')[1]


    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Оплатить", url="https://example.com/payment")
            ]
        ]
    )


    await query.edit_message_text(
        text=f"Вы выбрали подписку на {subscription_choice}. Пожалуйста, нажмите кнопку ниже, чтобы оплатить.",
        reply_markup=keyboard
    )

"""async def get_key(update: Update, _: CallbackContext) -> None:"""

def main() -> None:
    """Запуск бота."""

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()


    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(handle_subscription_choice, pattern='^buy_subscription$'))


    application.add_handler(CallbackQueryHandler(handle_payment, pattern='^subscribe_1_month$'))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern='^subscribe_3_months$'))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern='^subscribe_6_months$'))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern='^subscribe_12_months$'))

    """application.add_handler(CallbackQueryHandler(get_key(), pattern='^buy_key$'))"""

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
