import logging
import os
import shutil
unused_folder = 'unused_servers'
used_folder = 'used_servers'
from datetime import datetime, timedelta
from pymongo import MongoClient
from telegram import LabeledPrice
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update, Bot
)
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    Application, PreCheckoutQueryHandler, MessageHandler, filters,ShippingQueryHandler
)
from config import TELEGRAM_BOT_TOKEN, PAYMENTS_TOKEN
from text import get_start_text

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)
logger = logging.getLogger(__name__)

choice = ''
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
                InlineKeyboardButton(text="Связаться с Менеджером\n", callback_data='call_manager')
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
    subscription_duration = {
        '1': ('1 месяц', 250),
        '3': ('3 месяца', 675),
        '6': ('6 месяцев', 1275),
        '12': ('12 месяцев', 2250)
    }

    # Получение информации о подписке
    duration, price = subscription_duration[subscription_choice]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Оплатить", callback_data=f'oplata_{subscription_choice}')
            ]
        ]
    )

    await query.edit_message_text(
        text=f"Вы выбрали подписку на {duration}. Пожалуйста, нажмите кнопку ниже, чтобы оплатить.",
        reply_markup=keyboard
    )


async def get_key(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    unused_folder = 'unused_servers'
    used_folder = 'used_servers'

    if await check_subscription(user_id):
        client = MongoClient('localhost:27017')  # mongodb://mongo:27017/
        db = client['subscribers']
        collection = db['servers']

        server_info = collection.find_one({"user_id": user_id, "is_free": 'false'})

        if server_info:
            assigned_server_id = server_info['server_id']
            assigned_server_file = os.path.join(used_folder, f"{assigned_server_id}_{user_id}.conf")

            if os.path.isfile(assigned_server_file):
                with open(assigned_server_file, 'r') as file:
                    file_content = file.read()
                    await context.bot.send_message(chat_id=user_id, text=file_content)
                await query.edit_message_text(
                    text="Ваш конфигурационный файл был повторно отправлен."
                )
                return
            else:
                await query.edit_message_text(
                    text="Произошла ошибка: файл вашего сервера не найден."
                )
                return

        files = os.listdir(unused_folder)
        if files:
            first_file = files[0]
            file_path = os.path.join(unused_folder, first_file)

            with open(file_path, 'r') as file:
                file_content = file.read()
                await context.bot.send_message(chat_id=user_id, text=file_content)
                await query.edit_message_text(
                    text="Ваша подписка активна. Конфигурационный файл был отправлен."
                )

            if os.path.isfile(file_path):
                name, ext = os.path.splitext(first_file)
                new_filename = f"{name}_{user_id}{ext}"
                new_file_path = os.path.join(used_folder, new_filename)
                shutil.move(file_path, new_file_path)

                collection.insert_one({
                    "user_id": user_id,
                    "is_free": 'false',
                    "server_id": name
                })

                print(f"Файл {first_file} перемещён и переименован в {new_filename} в {used_folder}")
        else:
            await query.edit_message_text(
                text="Нет доступных файлов для отправки."
            )
    else:
        await query.edit_message_text(
            text="Ваша подписка не активна. Пожалуйста, оплатите подписку."
        )

async def check_subscription(user_id: int) -> bool:
    client = MongoClient('localhost:27017')
    db = client['subscribers']
    collection = db['subs']

    # Ищем подписку пользователя
    subscription = collection.find_one({"user_id": user_id})

    if not subscription:
        return False

    # Проверяем, не истекла ли подписка
    current_time = datetime.utcnow()
    end_time = datetime.fromisoformat(subscription["subscription_end_time"].rstrip('Z'))

    return current_time <= end_time


async def oplata(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    # Проверяем, есть ли свободные серверы
    unused_folder = 'unused_servers'
    files = os.listdir(unused_folder)

    if not files:
        # Если папка пустая, уведомляем пользователя и отменяем оплату
        await query.edit_message_text(
            text="Извините, в данный момент нет свободных серверов. Пожалуйста, попробуйте позже."
        )
        return

    # Если серверы есть, продолжаем с обработкой оплаты
    subscription_choice = query.data.split('_')[1]
    subscription_duration = {
        '1': 250,
        '3': 675,
        '6': 1275,
        '12': 2250
    }

    price = subscription_duration[subscription_choice]

    # Сохраняем выбор подписки в context.user_data
    context.user_data['subscription_choice'] = subscription_choice

    # Передача цены в send_invoice
    await send_invoice(update, context, price)


async def send_invoice(update: Update, context: CallbackContext, price: int) -> None:
    query = update.callback_query
    await query.answer()
    title = "Подписка на сервис"
    description = "Подписка на VPN сервис"
    payload = "subscription_payment"
    currency = "RUB"
    prices = [LabeledPrice("Подписка", price * 100)]

    try:
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=title,
            description=description,
            payload=payload,
            provider_token=PAYMENTS_TOKEN,
            currency=currency,
            prices=prices,
            start_parameter="test-payment"
        )

    except Exception as e:
        await context.bot.send_message(chat_id=query.message.chat_id,
                                       text=f"Произошла ошибка при отправке инвойса: {e}")


async def precheckout_callback(update: Update, context: CallbackContext) -> None:
    query = update.pre_checkout_query
    if query.invoice_payload != 'subscription_payment':
        await query.answer(ok=False, error_message="Что-то пошло не так...")
    else:
        await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    client = MongoClient('localhost:27017')
    db = client['subscribers']
    collection = db['subs']
    current_time = datetime.utcnow()


    subscription_choice = context.user_data.get('subscription_choice', '1')
    subscription_durations = {
        '1': 30,  # 1 месяц
        '3': 90,  # 3 месяца
        '6': 180,  # 6 месяцев
        '12': 365  # 12 месяцев
    }


    days_to_add = subscription_durations.get(subscription_choice, 30)


    subscription = collection.find_one({"user_id": user_id})

    if subscription:

        end_time = datetime.fromisoformat(subscription["subscription_end_time"].rstrip('Z'))

        if end_time > current_time:

            new_end_time = end_time + timedelta(days=days_to_add)
        else:

            new_end_time = current_time + timedelta(days=days_to_add)


        collection.update_one(
            {"user_id": user_id},
            {"$set": {"subscription_end_time": new_end_time.isoformat() + 'Z'}}
        )
    else:

        new_end_time = current_time + timedelta(days=days_to_add)

        collection.insert_one({
            "user_id": user_id,
            "subscription_end_time": new_end_time.isoformat() + 'Z',
            "subscription_choice": subscription_choice
        })


    await update.message.reply_text(
        f"Оплата прошла успешно! Ваша подписка активирована на {days_to_add // 30} месяцев.")


async def handle_manager_contact(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()


    chat_link = 'https://t.me/alxterek'
    await query.edit_message_text(
        text=f"Пожалуйста, [свяжитесь с нами здесь]({chat_link}) для дальнейшего общения.",
        parse_mode='Markdown'
    )

def main() -> None:
    """Запуск бота."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(handle_subscription_choice, pattern='^buy_subscription$'))

    application.add_handler(CallbackQueryHandler(handle_payment, pattern='^subscribe_1_month$'))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern='^subscribe_3_months$'))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern='^subscribe_6_months$'))
    application.add_handler(CallbackQueryHandler(handle_payment, pattern='^subscribe_12_months$'))
    application.add_handler(CallbackQueryHandler(oplata, pattern='^oplata_(1|3|6|12)$'))
    application.add_handler(CallbackQueryHandler(get_key, pattern='^buy_key$'))
    application.add_handler(CallbackQueryHandler(handle_manager_contact, pattern='^call_manager$'))

    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()