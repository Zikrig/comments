import os
import logging
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# Хранилище активных отзывов (в продакшене лучше использовать БД)
active_reviews: Dict[int, Dict] = {}


def get_start_keyboard():
    """Клавиатура для стартового меню"""
    keyboard = [
        [InlineKeyboardButton("Новый отзыв", callback_data="new_review")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_review_keyboard():
    """Клавиатура во время создания отзыва"""
    keyboard = [
        [InlineKeyboardButton("Завершить текущий отзыв", callback_data="finish_review")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_text = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот для приема отзывов. "
        "Нажмите кнопку ниже, чтобы начать создавать новый отзыв."
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_start_keyboard()
    )


async def new_review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Новый отзыв'"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Инициализируем новый отзыв
    active_reviews[user_id] = {
        'messages': [],
        'photos': []
    }
    
    response_text = (
        "Принято! Что-то еще? Просто продолжайте писать или нажмите "
        "\"завершить текущий отзыв\""
    )
    
    await query.edit_message_text(
        response_text,
        reply_markup=get_review_keyboard()
    )


async def finish_review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Завершить текущий отзыв'"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in active_reviews:
        await query.edit_message_text(
            "У вас нет активного отзыва. Нажмите 'Новый отзыв', чтобы начать.",
            reply_markup=get_start_keyboard()
        )
        return
    
    review_data = active_reviews[user_id]
    
    # Отправляем отзыв админу
    await send_review_to_admin(context, user_id, review_data)
    
    # Удаляем активный отзыв
    del active_reviews[user_id]
    
    # Благодарность пользователю
    thank_you_text = (
        "Спасибо за ваш отзыв! 🙏\n\n"
        "Ваш отзыв был отправлен администратору. "
        "Если хотите оставить еще один отзыв, нажмите кнопку ниже."
    )
    
    await query.edit_message_text(
        thank_you_text,
        reply_markup=get_start_keyboard()
    )


async def send_review_to_admin(context: ContextTypes.DEFAULT_TYPE, user_id: int, review_data: Dict):
    """Отправка отзыва администратору"""
    if ADMIN_ID == 0:
        logger.warning("ADMIN_ID не установлен, отзыв не будет отправлен")
        return
    
    user = await context.bot.get_chat(user_id)
    user_info = f"Отзыв от: {user.first_name} (@{user.username or 'без username'}) [ID: {user_id}]"
    
    # Отправляем информацию о пользователе
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📝 Новый отзыв\n\n{user_info}"
    )
    
    # Отправляем текстовые сообщения
    if review_data['messages']:
        messages_text = "\n\n".join(review_data['messages'])
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💬 Текст отзыва:\n\n{messages_text}"
        )
    
    # Отправляем фотографии
    if review_data['photos']:
        for photo_file_id in review_data['photos']:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo_file_id,
                caption=f"📷 Фото из отзыва от {user.first_name}"
            )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    
    # Проверяем, есть ли активный отзыв
    if user_id not in active_reviews:
        await update.message.reply_text(
            "У вас нет активного отзыва. Нажмите 'Новый отзыв', чтобы начать.",
            reply_markup=get_start_keyboard()
        )
        return
    
    # Добавляем текст в отзыв
    text = update.message.text or update.message.caption or ""
    if text:
        active_reviews[user_id]['messages'].append(text)
    
    # Отправляем подтверждение
    response_text = (
        "Принято! Что-то еще? Просто продолжайте писать или нажмите "
        "\"завершить текущий отзыв\""
    )
    
    await update.message.reply_text(
        response_text,
        reply_markup=get_review_keyboard()
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий"""
    user_id = update.effective_user.id
    
    # Проверяем, есть ли активный отзыв
    if user_id not in active_reviews:
        await update.message.reply_text(
            "У вас нет активного отзыва. Нажмите 'Новый отзыв', чтобы начать.",
            reply_markup=get_start_keyboard()
        )
        return
    
    # Добавляем фото в отзыв
    photo = update.message.photo[-1]  # Берем фото наибольшего размера
    active_reviews[user_id]['photos'].append(photo.file_id)
    
    # Добавляем подпись к фото, если есть
    if update.message.caption:
        active_reviews[user_id]['messages'].append(f"[Подпись к фото]: {update.message.caption}")
    
    # Отправляем подтверждение
    response_text = (
        "Принято! Что-то еще? Просто продолжайте писать или нажмите "
        "\"завершить текущий отзыв\""
    )
    
    await update.message.reply_text(
        response_text,
        reply_markup=get_review_keyboard()
    )


def main():
    """Основная функция запуска бота"""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не установлен! Установите переменную окружения BOT_TOKEN.")
    
    if ADMIN_ID == 0:
        logger.warning("ADMIN_ID не установлен! Отзывы не будут отправляться админу.")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(new_review_callback, pattern="^new_review$"))
    application.add_handler(CallbackQueryHandler(finish_review_callback, pattern="^finish_review$"))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

