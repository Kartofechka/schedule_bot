import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import json
import time
from threading import Thread
from datetime import datetime
import asyncio
import locale
import subprocess
import sys
import os

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
SELECTING_ACTION, VIEWING_SCHEDULE, SELECTING_DAY, SELECTING_WEEK = range(4)

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
def find_today_schedule(schedule_data, week_type='current_week'):
    today_date = get_current_schedule_date()
    today_weekday = get_russian_weekday(datetime.now().weekday())
    
    logger.info(f"Ищем расписание для: {today_weekday} ({today_date}) в неделе: {week_type}")
    
    if week_type not in schedule_data:
        return None
    
    week_data = schedule_data[week_type]
    
    # Сначала ищем по точной дате
    for day in week_data['days']:
        if day['date'] == today_date:
            logger.info(f"Найдено по дате: {day['day_name']} ({day['date']})")
            return day
    
    # Если не нашли по дате, ищем по дню недели
    for day in week_data['days']:
        if day['day_name'] == today_weekday:
            logger.info(f"Найдено по дню недели: {day['day_name']} ({day['date']})")
            return day
    
    # Если сегодня воскресенье, ищем понедельник следующей недели
    if today_weekday == 'Воскресенье':
        if week_type == 'current_week':
            # В воскресенье показываем понедельник следующей недели
            next_week_data = schedule_data.get('next_week')
            if next_week_data:
                for day in next_week_data['days']:
                    if day['day_name'] == 'Понедельник':
                        logger.info(f"Воскресенье - найдено расписание на понедельник след. недели: {day['day_name']} ({day['date']})")
                        return day
    
    logger.info("Расписание на сегодня не найдено")
    return None

# Главная клавиатура
def get_main_keyboard():
    keyboard = [
        ['📅 Расписание на сегодня', '📋 Текущая неделя'],
        ['📆 Следующая неделя', '🗓️ Выбрать день'],
        ['🔄 Обновить расписание', '❓ Помощь']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Клавиатура для выбора недели
def get_week_keyboard():
    keyboard = [
        ['📅 Текущая неделя', '📆 Следующая неделя'],
        ['🔙 Назад']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Клавиатура для выбора дней
def get_days_keyboard(schedule_data, week_type='current_week'):
    keyboard = []
    if week_type in schedule_data:
        for day in schedule_data[week_type]['days']:
            keyboard.append([f"{day['day_name']} ({day['date']})"])
    keyboard.append(['🔙 Назад'])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def run_schedule_parser_sync():
    """Синхронная версия запуска парсера"""
    try:
        # Пробуем разные имена файлов парсера
        possible_parser_files = [
            "schedule_parser.py",
            "schedule.py", 
            "parser.py"
        ]
        
        parser_script = None
        for script in possible_parser_files:
            if os.path.exists(script):
                parser_script = script
                break
        
        if not parser_script:
            return False, "Файл парсера не найден. Проверьте наличие schedule_parser.py, schedule.py или parser.py"
        
        print(f"Запускаем парсер: {parser_script}")
        
        # Запускаем парсер синхронно
        result = subprocess.run(
            [sys.executable, parser_script],
            capture_output=True,
            text=True,
            timeout=120,  # 2 минуты таймаут
            encoding='utf-8',
            errors='ignore'
        )
        
        print(f"Парсер завершился с кодом: {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        if result.stderr:
            print(f"STDERR: {result.stderr}")
        
        if result.returncode == 0:
            success_message = "Расписание успешно обновлено! 🎉"
            if result.stdout:
                # Извлекаем только важную информацию из лога
                lines = result.stdout.split('\n')
                important_lines = [line for line in lines if '✅' in line or '❌' in line or '📊' in line]
                if important_lines:
                    success_message += f"\n\nДетали:\n" + "\n".join(important_lines[-5:])  # Последние 5 важных строк
            return True, success_message
        else:
            error_details = result.stderr if result.stderr else result.stdout
            if not error_details:
                error_details = "Неизвестная ошибка (парсер завершился с ошибкой)"
            
            # Упрощаем сообщение об ошибке
            if "Chrome" in error_details or "driver" in error_details:
                error_summary = "Ошибка браузера. Проверьте установку Chrome и ChromeDriver."
            elif "timeout" in error_details.lower():
                error_summary = "Таймаут операции. Сайт может быть перегружен."
            else:
                error_summary = error_details[:300] + "..." if len(error_details) > 300 else error_details
            
            return False, f"Ошибка при обновлении расписания:\n{error_summary}"
            
    except subprocess.TimeoutExpired:
        print("Таймаут при обновлении расписания")
        return False, "Таймаут при обновлении расписания (процесс занял слишком много времени)"
    except Exception as e:
        print(f"Исключение при запуске парсера: {str(e)}")
        return False, f"Ошибка при запуске парсера: {str(e)}"

# Обновление расписания - ИСПРАВЛЕННАЯ ВЕРСИЯ
async def update_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info(f"Пользователь {user.first_name} запустил обновление расписания")
    
    # Отправляем сообщение о начале обновления
    status_message = await update.message.reply_text(
        "🔄 Запускаю обновление расписания...\n"
        "Это может занять несколько минут...\n"
        "⏳ Пожалуйста, подождите...",
        reply_markup=get_main_keyboard()
    )
    
    try:
        # Запускаем парсер
        success, result_message = run_schedule_parser_sync()
        
        # Вместо редактирования сообщения отправляем новое
        if success:
            await update.message.reply_text(
                f"✅ {result_message}\n"
                f"Расписание успешно обновлено! 🎉\n"
                f"Теперь вы можете просмотреть актуальное расписание.",
                reply_markup=get_main_keyboard()
            )
        else:
            await update.message.reply_text(
                f"❌ {result_message}\n"
                f"Попробуйте позже или проверьте настройки парсера.",
                reply_markup=get_main_keyboard()
            )
    
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в update_schedule: {str(e)}")
        await update.message.reply_text(
            f"❌ Произошла непредвиденная ошибка:\n{str(e)[:500]}\n"
            f"Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )
    
    return SELECTING_ACTION

# Показать расписание на сегодня
async def show_today_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    schedule_data = load_schedule()
    if not schedule_data:
        await update.message.reply_text(
            "❌ Расписание не найдено\n"
            "Используйте кнопку '🔄 Обновить расписание' для получения актуальных данных",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    # Определяем какая неделя сейчас
    today_weekday = datetime.now().weekday()
    week_type = 'current_week'
    
    # Если сегодня воскресенье, показываем следующую неделю
    if today_weekday == 6:  # Воскресенье
        week_type = 'next_week'
    
    today_schedule = find_today_schedule(schedule_data, week_type)
    today_date = get_current_schedule_date()
    today_weekday_name = get_russian_weekday(today_weekday)
    
    week_label = "текущей" if week_type == 'current_week' else "следующей"
    
    if not today_schedule or not today_schedule['lessons']:
        await update.message.reply_text(
            f"📅 На сегодня ({today_weekday_name}, {today_date}) занятий нет 🎉\n(данные из {week_label} недели)",
            reply_markup=get_main_keyboard()
        )
    else:
        message = f"📅 Расписание на сегодня ({today_weekday_name}, {today_date}):\n(данные из {week_label} недели)\n\n"
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

# Показать расписание на текущую неделю
async def show_current_week_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    schedule_data = load_schedule()
    if not schedule_data or 'current_week' not in schedule_data:
        await update.message.reply_text(
            "❌ Расписание на текущую неделю не найдено\n"
            "Используйте кнопку '🔄 Обновить расписание' для получения актуальных данных",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    week_data = schedule_data['current_week']
    message = "📋 Расписание на текущую неделю:\n\n"
    
    for day in week_data['days']:
        message += f"📅 {day['day_name']} ({day['date']}):\n"
        
        if not day['lessons']:
            message += "   🎉 Нет занятий\n\n"
        else:
            for i, lesson in enumerate(day['lessons'], 1):
                message += f"   {i}. ⏰ {lesson['time_range']}\n"
                message += f"      📚 {lesson['subject']}\n"
                message += f"      👨‍🏫 {lesson['teacher']}\n"
                message += f"      🏫 {lesson['room']} | {lesson['type']}\n\n"
    
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

# Показать расписание на следующую неделю
async def show_next_week_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    schedule_data = load_schedule()
    if not schedule_data or 'next_week' not in schedule_data:
        await update.message.reply_text(
            "❌ Расписание на следующую неделю не найдено\n"
            "Используйте кнопку '🔄 Обновить расписание' для получения актуальных данных",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    week_data = schedule_data['next_week']
    message = "📆 Расписание на следующую неделю:\n\n"
    
    for day in week_data['days']:
        message += f"📅 {day['day_name']} ({day['date']}):\n"
        
        if not day['lessons']:
            message += "   🎉 Нет занятий\n\n"
        else:
            for i, lesson in enumerate(day['lessons'], 1):
                message += f"   {i}. ⏰ {lesson['time_range']}\n"
                message += f"      📚 {lesson['subject']}\n"
                message += f"      👨‍🏫 {lesson['teacher']}\n"
                message += f"      🏫 {lesson['room']} | {lesson['type']}\n\n"
    
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

# Выбор недели для просмотра расписания по дням
async def select_week_for_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    schedule_data = load_schedule()
    if not schedule_data:
        await update.message.reply_text(
            "❌ Расписание не найдено\n"
            "Используйте кнопку '🔄 Обновить расписание' для получения актуальных данных",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    await update.message.reply_text(
        "Выберите неделю для просмотра расписания по дням:",
        reply_markup=get_week_keyboard()
    )
    
    return SELECTING_WEEK

# Выбор дня для просмотра расписания
async def select_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    schedule_data = load_schedule()
    if not schedule_data:
        await update.message.reply_text(
            "❌ Расписание не найдено\n"
            "Используйте кнопку '🔄 Обновить расписание' для получения актуальных данных",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    week_type = context.user_data.get('selected_week', 'current_week')
    
    await update.message.reply_text(
        f"Выберите день для просмотра расписания ({'текущая' if week_type == 'current_week' else 'следующая'} неделя):",
        reply_markup=get_days_keyboard(schedule_data, week_type)
    )
    
    return SELECTING_DAY

# Показать расписание для выбранного дня
async def show_day_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    schedule_data = load_schedule()
    if not schedule_data:
        await update.message.reply_text(
            "❌ Расписание не найдено\n"
            "Используйте кнопку '🔄 Обновить расписание' для получения актуальных данных",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    selected_day = update.message.text
    week_type = context.user_data.get('selected_week', 'current_week')
    
    if week_type not in schedule_data:
        await update.message.reply_text(
            "❌ Данные недели не найдены",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    week_data = schedule_data[week_type]
    
    # Ищем выбранный день
    target_day = None
    for day in week_data['days']:
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
    
    week_label = "текущей" if week_type == 'current_week' else "следующей"
    message = f"📅 {target_day['day_name']} ({target_day['date']})\n({week_label} неделя):\n\n"
    
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

📅 **Расписание на сегодня** - показать занятия на сегодня (автоматически выбирает неделю)
📋 **Текущая неделя** - показать всё расписание текущей недели
📆 **Следующая неделя** - показать расписание следующей недели
🗓️ **Выбрать день** - выбрать конкретный день из любой недели
🔄 **Обновить расписание** - запустить парсер для получения актуального расписания

⚡ **Быстрые команды:**
/start - запустить бота
/today - расписание на сегодня  
/current_week - текущая неделя
/next_week - следующая неделя
/update_schedule - обновить расписание
/help - показать эту справку
    """
    
    await update.message.reply_text(
        help_text, 
        reply_markup=get_main_keyboard()
    )
    return SELECTING_ACTION

# Обработка текстовых сообщений в состоянии SELECTING_ACTION
async def handle_message_selecting_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    
    if text == '📅 Расписание на сегодня':
        return await show_today_schedule(update, context)
    elif text == '📋 Текущая неделя':
        return await show_current_week_schedule(update, context)
    elif text == '📆 Следующая неделя':
        return await show_next_week_schedule(update, context)
    elif text == '🗓️ Выбрать день':
        return await select_week_for_days(update, context)
    elif text == '🔄 Обновить расписание':
        return await update_schedule(update, context)
    elif text == '❓ Помощь':
        return await help_command(update, context)
    elif text == '🔙 Назад':
        return await start(update, context)
    else:
        await update.message.reply_text(
            "Не понимаю команду 😕\nИспользуйте кнопки меню или /help",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION

# Обработка текстовых сообщений в состоянии SELECTING_WEEK
async def handle_message_selecting_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    
    if text == '📅 Текущая неделя':
        context.user_data['selected_week'] = 'current_week'
        return await select_day(update, context)
    elif text == '📆 Следующая неделя':
        context.user_data['selected_week'] = 'next_week'
        return await select_day(update, context)
    elif text == '🔙 Назад':
        return await start(update, context)
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите неделю из предложенных вариантов:",
            reply_markup=get_week_keyboard()
        )
        return SELECTING_WEEK

# Обработка текстовых сообщений в состоянии SELECTING_DAY
async def handle_message_selecting_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    
    if text == '🔙 Назад':
        return await select_week_for_days(update, context)
    else:
        # Проверяем, не выбрал ли пользователь день из списка
        schedule_data = load_schedule()
        if schedule_data:
            week_type = context.user_data.get('selected_week', 'current_week')
            if week_type in schedule_data:
                for day in schedule_data[week_type]['days']:
                    day_str = f"{day['day_name']} ({day['date']})"
                    if text == day_str:
                        return await show_day_schedule(update, context)
        
        await update.message.reply_text(
            "Пожалуйста, выберите день из предложенных вариантов:",
            reply_markup=get_days_keyboard(schedule_data, context.user_data.get('selected_week', 'current_week'))
        )
        return SELECTING_DAY

# Команда /start - ВЫНЕСЕНА ИЗ ConversationHandler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info(f"Пользователь {user.first_name} запустил бота")
    
    # Очищаем данные пользователя при перезапуске
    context.user_data.clear()
    
    # Показываем какое сегодня число по версии бота
    today_date = get_current_schedule_date()
    today_weekday = get_russian_weekday(datetime.now().weekday())
    logger.info(f"Сегодня: {today_weekday}, {today_date}")
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n"
        f"Сегодня: {today_weekday}, {today_date}\n"
        "Я бот для просмотра расписания занятий группы 201/2.\n\n"
        "Выберите действие:",
        reply_markup=get_main_keyboard()
    )
    
    return SELECTING_ACTION

# Команда /today
async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await show_today_schedule(update, context)

# Команда /current_week
async def current_week_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await show_current_week_schedule(update, context)

# Команда /next_week
async def next_week_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await show_next_week_schedule(update, context)

# Команда /update_schedule
async def update_schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await update_schedule(update, context)

# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info(f"Пользователь {user.first_name} отменил действие")
    await update.message.reply_text(
        'Действие отменено',
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# Основная функция - ИСПРАВЛЕННАЯ ВЕРСИЯ
def main():
    application = Application.builder().token(token=TOKEN).build()
    
    # ОБРАТИТЕ ВНИМАНИЕ: CommandHandler('start', start) добавлен ДО ConversationHandler
    # Это гарантирует, что команда /start будет обработана правильно
    
    # Сначала добавляем все CommandHandler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("current_week", current_week_command))
    application.add_handler(CommandHandler("next_week", next_week_command))
    application.add_handler(CommandHandler("update_schedule", update_schedule_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Затем добавляем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[],  # Теперь пусто, так как команды обрабатываются выше
        states={
            SELECTING_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_selecting_action)
            ],
            SELECTING_WEEK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_selecting_week)
            ],
            SELECTING_DAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_selecting_day)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    
    # Запускаем бота
    print("Бот запущен...")
    print(f"Текущая дата в формате расписания: {get_current_schedule_date()}")
    application.run_polling()

if __name__ == '__main__':
    main()
