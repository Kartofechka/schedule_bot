import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import json
import schedule
import time
from threading import Thread
from datetime import datetime
import asyncio
import locale

TOKEN = "8022446939:AAF0Ivz9sBP0QGh--ZC2VRZp7abDxonL1aQ"

# Попробуем установить русскую локаль для корректного отображения месяцев
try:
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'Russian_Russia.1251')
    except:
        print("Не удалось установить русскую локаль, будут использоваться английские названия месяцев")

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
SELECTING_ACTION, VIEWING_SCHEDULE, SELECTING_DAY = range(3)

# Загрузка расписания
def load_schedule(filename="schedule_201_2.json"):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

# Функция для получения русских названий месяцев
def get_russian_month(month_num):
    months = {
        1: 'янв.', 2: 'фев.', 3: 'мар.', 4: 'апр.',
        5: 'мая', 6: 'июн.', 7: 'июл.', 8: 'авг.',
        9: 'сен.', 10: 'окт.', 11: 'нояб.', 12: 'дек.'
    }
    return months.get(month_num, '')

# Функция для получения текущей даты в формате расписания
def get_current_schedule_date():
    now = datetime.now()
    day = now.day
    month_rus = get_russian_month(now.month)
    return f"{day} {month_rus}"

# Функция для получения дня недели на русском
def get_russian_weekday(weekday_num):
    weekdays = {
        0: 'Понедельник',
        1: 'Вторник', 
        2: 'Среда',
        3: 'Четверг',
        4: 'Пятница',
        5: 'Суббота',
        6: 'Воскресенье'
    }
    return weekdays.get(weekday_num, '')

# Функция для поиска расписания на сегодня
def find_today_schedule(schedule_data):
    today_date = get_current_schedule_date()
    today_weekday = get_russian_weekday(datetime.now().weekday())
    
    logger.info(f"Ищем расписание для: {today_weekday} ({today_date})")
    
    # Сначала ищем по точной дате
    for day in schedule_data['days']:
        if day['date'] == today_date:
            logger.info(f"Найдено по дате: {day['day_name']} ({day['date']})")
            return day
    
    # Если не нашли по дате, ищем по дню недели
    for day in schedule_data['days']:
        if day['day_name'] == today_weekday:
            logger.info(f"Найдено по дню недели: {day['day_name']} ({day['date']})")
            return day
    
    # Если сегодня воскресенье, ищем понедельник
    if today_weekday == 'Воскресенье':
        for day in schedule_data['days']:
            if day['day_name'] == 'Понедельник':
                logger.info(f"Воскресенье - найдено расписание на понедельник: {day['day_name']} ({day['date']})")
                return day
    
    logger.info("Расписание на сегодня не найдено")
    return None

# Главная клавиатура
def get_main_keyboard():
    keyboard = [
        ['📅 Расписание на сегодня', '📋 Расписание на неделю'],
        ['📆 Расписание по дням', '❓ Помощь'],
        ['/start']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Клавиатура для выбора дней
def get_days_keyboard(schedule_data):
    keyboard = []
    for day in schedule_data['days']:
        keyboard.append([f"{day['day_name']} ({day['date']})"])
    keyboard.append(['🔙 Назад'])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Показать расписание на сегодня
async def show_today_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    schedule_data = load_schedule()
    if not schedule_data:
        await update.message.reply_text(
            "❌ Расписание не найдено",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    today_schedule = find_today_schedule(schedule_data)
    today_date = get_current_schedule_date()
    today_weekday = get_russian_weekday(datetime.now().weekday())
    
    if not today_schedule or not today_schedule['lessons']:
        await update.message.reply_text(
            f"📅 На сегодня ({today_weekday}, {today_date}) занятий нет 🎉",
            reply_markup=get_main_keyboard()
        )
    else:
        message = f"📅 Расписание на сегодня ({today_weekday}, {today_date}):\n\n"
        for i, lesson in enumerate(today_schedule['lessons'], 1):
            message += f"{i}. ⏰ {lesson['time_range']}\n"
            message += f"   📚 {lesson['subject']}\n"
            message += f"   👨‍🏫 {lesson['teacher']}\n"
            message += f"   🏫 {lesson['room']} | {lesson['type']}\n\n"
        
        await update.message.reply_text(
            message, 
            reply_markup=get_main_keyboard()
        )
    
    return SELECTING_ACTION

# Показать расписание на неделю
async def show_week_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    schedule_data = load_schedule()
    if not schedule_data:
        await update.message.reply_text(
            "❌ Расписание не найдено",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    message = "📋 Расписание на неделю:\n\n"
    
    for day in schedule_data['days']:
        message += f"📅 {day['day_name']} ({day['date']}):\n"
        
        if not day['lessons']:
            message += "   🎉 Нет занятий\n\n"
        else:
            for i, lesson in enumerate(day['lessons'], 1):
                    message += f"{i}. ⏰ {lesson['time_range']}\n"
                    message += f"   📚 {lesson['subject']}\n"
                    message += f"   👨‍🏫 {lesson['teacher']}\n"
                    message += f"   🏫 {lesson['room']} | {lesson['type']}\n\n" 
            message += "\n"
    
    # Если сообщение слишком длинное, разбиваем на части
    if len(message) > 4096:
        parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # Последняя часть
                await update.message.reply_text(
                    part, 
                    reply_markup=get_main_keyboard()
                )
            else:
                await update.message.reply_text(part)
    else:
        await update.message.reply_text(
            message, 
            reply_markup=get_main_keyboard()
        )
    
    return SELECTING_ACTION

# Выбор дня для просмотра расписания
async def select_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    schedule_data = load_schedule()
    if not schedule_data:
        await update.message.reply_text(
            "❌ Расписание не найдено",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    await update.message.reply_text(
        "Выберите день для просмотра расписания:",
        reply_markup=get_days_keyboard(schedule_data)
    )
    
    return SELECTING_DAY

# Показать расписание для выбранного дня
async def show_day_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    schedule_data = load_schedule()
    if not schedule_data:
        await update.message.reply_text(
            "❌ Расписание не найдено",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    selected_day = update.message.text
    
    # Ищем выбранный день
    target_day = None
    for day in schedule_data['days']:
        day_str = f"{day['day_name']} ({day['date']})"
        if day_str == selected_day:
            target_day = day
            break
    
    if not target_day:
        await update.message.reply_text(
            "❌ День не найден",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    message = f"📅 {target_day['day_name']} ({target_day['date']}):\n\n"
    
    if not target_day['lessons']:
        message += "🎉 Нет занятий"
    else:
        for i, lesson in enumerate(target_day['lessons'], 1):
            message += f"{i}. ⏰ {lesson['time_range']}\n"
            message += f"   📚 {lesson['subject']}\n"
            message += f"   👨‍🏫 {lesson['teacher']}\n"
            message += f"   🏫 {lesson['room']} | {lesson['type']}\n\n"
    
    await update.message.reply_text(
        message, 
        reply_markup=get_main_keyboard()
    )
    return SELECTING_ACTION

# Помощь
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    help_text = """
🤖 **Команды бота:**

📅 **Расписание на сегодня** - показать занятия на сегодня
📋 **Расписание на неделю** - показать всё расписание
📆 **Расписание по дням** - выбрать конкретный день

⚡ **Быстрые команды:**
/start - запустить бота
/today - расписание на сегодня  
/week - расписание на неделю
/help - показать эту справку
    """
    
    await update.message.reply_text(
        help_text, 
        reply_markup=get_main_keyboard()
    )
    return SELECTING_ACTION

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    
    if text == '📅 Расписание на сегодня':
        return await show_today_schedule(update, context)
    elif text == '📋 Расписание на неделю':
        return await show_week_schedule(update, context)
    elif text == '📆 Расписание по дням':
        return await select_day(update, context)
    elif text == '❓ Помощь':
        return await help_command(update, context)
    elif text == '🔙 Назад':
        return await start(update, context)
    else:
        # Проверяем, не выбрал ли пользователь день из списка
        schedule_data = load_schedule()
        if schedule_data:
            for day in schedule_data['days']:
                day_str = f"{day['day_name']} ({day['date']})"
                if text == day_str:
                    return await show_day_schedule(update, context)
        
        await update.message.reply_text(
            "Не понимаю команду 😕\nИспользуйте кнопки меню или /help",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info(f"Пользователь {user.first_name} запустил бота")
    
    # Показываем какое сегодня число по версии бота
    today_date = get_current_schedule_date()
    today_weekday = get_russian_weekday(datetime.now().weekday())
    logger.info(f"Сегодня: {today_weekday}, {today_date}")
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n"
        f"Сегодня: {today_weekday}, {today_date}\n"
        "Я бот для просмотра расписания занятий.\n"
        "Выберите действие:",
        reply_markup=get_main_keyboard()
    )
    
    return SELECTING_ACTION

# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info(f"Пользователь {user.first_name} отменил действие")
    await update.message.reply_text(
        'Действие отменено',
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# Основная функция
def main():
    # Замените 'YOUR_BOT_TOKEN' на токен вашего бота
    application = Application.builder().token(token=TOKEN).build()
    
    # ConversationHandler для управления состояниями
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            ],
            SELECTING_DAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Добавляем обработчики команд
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("today", show_today_schedule))
    application.add_handler(CommandHandler("week", show_week_schedule))
    application.add_handler(CommandHandler("help", help_command))
    
    # Запускаем бота
    print("Бот запущен...")
    print(f"Текущая дата в формате расписания: {get_current_schedule_date()}")
    application.run_polling()

if __name__ == '__main__':
    main()