import logging
import re
import json
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
CHOOSING_CURRENCY, CHOOSING_AMOUNT, CHOOSING_TERM, CHOOSING_CAPITALIZATION, ADDING_DEPOSITS = range(5)

# Ставки по депозитам
RATES = {
    'KGS': { 3: 6.0, 6: 10.0, 12: 14.5, 24: 14.5 },
    'USD': { 3: 2.0, 6: 2.5, 12: 4.0, 24: 4.0 },
    'EUR': { 3: 0.6, 6: 1.2, 12: 1.5, 24: 1.3 }
}

CURRENCY_SYMBOLS = {
    'KGS': 'сом',
    'USD': '$',
    'EUR': '€'
}

# FAQ и ответы
FAQ = {
    'как рассчитываются проценты': """
📊 **Как рассчитываются проценты по депозиту:**

• **День открытия**: проценты НЕ начисляются
• **Ежедневный расчет**: (Баланс × Ставка) ÷ 360
• **Довклады**: проценты за день довклада начисляются на старый баланс, новый баланс используется со следующего дня
• **31-е число**: проценты НЕ начисляются
• **Февраль**: всегда считается как 30 дней
• **Последний месяц**: всегда 29 дней

**Пример**: Депозит 100,000 сом под 16.5% годовых
Ежедневный доход: 100,000 × 16.5% ÷ 360 = 45.83 сома
""",
    
    'какие есть валюты': f"""
💱 **Доступные валюты и ставки:**

**Сом (KGS):**
• 3 месяца: {RATES['KGS'][3]}%
• 6 месяцев: {RATES['KGS'][6]}%
• 12 месяцев: {RATES['KGS'][12]}%
• 24 месяца: {RATES['KGS'][24]}%
• 36 месяцев: {RATES['KGS'][36]}%

**Доллар (USD):**
• 3 месяца: {RATES['USD'][3]}%
• 6 месяцев: {RATES['USD'][6]}%
• 12 месяцев: {RATES['USD'][12]}%
• 24 месяца: {RATES['USD'][24]}%
• 36 месяцев: {RATES['USD'][36]}%

**Евро (EUR):**
• 3 месяца: {RATES['EUR'][3]}%
• 6 месяцев: {RATES['EUR'][6]}%
• 12 месяцев: {RATES['EUR'][12]}%
• 24 месяца: {RATES['EUR'][24]}%
• 36 месяцев: {RATES['EUR'][36]}%
""",
    
    'что такое капитализация': """
💡 **Капитализация процентов:**

Капитализация - это когда начисленные проценты добавляются к основной сумме депозита и в дальнейшем тоже приносят доход.

**Без капитализации:**
• Проценты выплачиваются ежемесячно
• Основная сумма остается неизменной

**С капитализацией:**
• Проценты добавляются к депозиту ежемесячно
• В следующем месяце проценты начисляются на увеличенную сумму
• Общий доход выше

**Пример**: 100,000 сом на 12 месяцев под 16.5%
• Без капитализации: 16,500 сом
• С капитализацией: 17,847 сом (+1,347 сом)
""",
    
    'можно ли довкладывать': """
✅ **Довклады (пополнения):**

Да, можно довкладывать средства в течение срока депозита!

**Правила довкладов:**
• Минимальная сумма: 1,000 сом / 100 USD / 100 EUR
• Проценты за день довклада начисляются на старый баланс
• Новый баланс учитывается со следующего дня
• При довкладе производится пересчет с последней выплаты

**Пример**: 
1 января: депозит 100,000 сом
15 января: довклад 50,000 сом
• 14 января: проценты на 100,000 сом
• 15 января: проценты на 100,000 сом (старый баланс)
• 16 января: проценты на 150,000 сом (новый баланс)
""",
    
    'как досрочно закрыть': """
⚠️ **Досрочное расторжение:**

Депозит можно закрыть досрочно, но с потерей процентов.

**Условия досрочного расторжения:**
• До 30 дней: 0% годовых
• 31-90 дней: 1% годовых
• 91-180 дней: 2% годовых
• Более 180 дней: 3% годовых

**Пример**: Депозит 100,000 сом под 16.5% закрыт через 60 дней
• По ставке депозита: 2,750 сом
• По ставке досрочного расторжения: 167 сом
• Потеря: 2,583 сом

💡 **Совет**: Лучше не закрывать досрочно, если это не критично!
""",
    
    'налоги': """
💰 **Налогообложение депозитов:**

**Физические лица:**
• Проценты по депозитам НЕ облагаются налогом
• Нет необходимости подавать декларацию

**Юридические лица:**
• Проценты облагаются налогом на прибыль
• Ставка: 10%

**Валютные депозиты:**
• Курсовые разницы могут облагаться налогом
• Уточните у налогового консультанта
""",
    
    'страхование': """
🛡️ **Страхование депозитов:**

Все депозиты автоматически застрахованы Агентством по страхованию вкладов (АСВ).

**Лимиты страхования:**
• Максимум: 700,000 сом на одного вкладчика
• Покрывает: сом, доллары, евро
• Срок выплаты: до 14 дней

**Что покрывается:**
• Основная сумма депозита
• Начисленные проценты
• Довклады

**Что НЕ покрывается:**
• Депозиты на предъявителя
• Депозиты в драгоценных металлах
• Депозиты в трастовом управлении
""",
    
    'сравнение': """
📈 **Сравнение вариантов депозита:**

**Пример**: 100,000 сом на 12 месяцев

**Без капитализации:**
• Проценты: 16,500 сом
• Итого: 116,500 сом

**С капитализацией:**
• Проценты: 17,847 сом
• Итого: 117,847 сом
• **Выгода**: +1,347 сом

**С довкладами (50,000 сом через 6 месяцев):**
• Проценты: 24,750 сом
• Итого: 174,750 сом

💡 **Вывод**: Капитализация и довклады значительно увеличивают доходность!
""",
    
    'советы': """
💡 **Советы по депозитам:**

**1. Выбирайте правильный срок:**
• Короткий срок (3-6 мес): гибкость, но низкие ставки
• Длинный срок (12-36 мес): высокие ставки, но привязка к банку

**2. Используйте капитализацию:**
• Всегда выгоднее для длинных депозитов
• Разница может быть 10-15% от дохода

**3. Планируйте довклады:**
• Регулярные довклады увеличивают доход
• Используйте зарплату или другие поступления

**4. Диверсифицируйте:**
• Разделите сумму на несколько депозитов
• Разные сроки = разная ликвидность

**5. Следите за ставками:**
• Банки могут менять ставки
• Рефинансирование может быть выгодно
"""
}

def format_number(num):
    """Форматирование чисел с разделителями"""
    if isinstance(num, (int, float)):
        return f"{num:,.2f}".replace(',', ' ').replace('.', ',')
    return str(num)

def currency_symbol(currency):
    """Получение символа валюты"""
    return CURRENCY_SYMBOLS.get(currency, currency)

def is_same_day(d1, d2):
    """Проверка, что две даты - один день"""
    return d1.year == d2.year and d1.month == d2.month and d1.day == d2.day

def calculate_deposit(currency, term, start_date, initial_amount, deposits=None, capitalization=False):
    """Расчет депозита"""
    if deposits is None:
        deposits = []
    
    rate = RATES[currency][term]
    open_day = start_date.day
    
    # Конечная дата
    end_date = start_date + timedelta(days=term * 30 - 1)  # 30 дней в месяце
    
    # Добавляем начальный депозит
    all_deposits = [{'date': start_date, 'amount': initial_amount, 'is_initial': True}] + deposits
    all_deposits.sort(key=lambda x: x['date'])
    
    total_interest = 0
    total_principal = sum(dep['amount'] for dep in all_deposits)
    
    interest_bearing_balance = 0
    deposit_index = 0
    monthly_interests = {}
    accumulated_interest = 0
    
    current_date = start_date
    
    while current_date <= end_date:
        # Обрабатываем довклады на текущий день
        while deposit_index < len(all_deposits) and is_same_day(all_deposits[deposit_index]['date'], current_date):
            interest_bearing_balance += all_deposits[deposit_index]['amount']
            deposit_index += 1
        
        # Расчет дневных процентов
        daily_interest = 0
        if not is_same_day(current_date, start_date):
            daily_interest = (interest_bearing_balance * rate) / (360 * 100)
        
        # 31-е число - проценты не начисляются
        effective_interest = 0 if current_date.day == 31 else daily_interest
        
        total_interest += effective_interest
        accumulated_interest += effective_interest
        
        # Учет по месяцам
        month_key = f"{current_date.year}-{current_date.month}"
        if month_key not in monthly_interests:
            monthly_interests[month_key] = 0
        monthly_interests[month_key] += effective_interest
        
        # Февраль - всегда 30 дней
        if current_date.month == 2:
            days_in_feb = 29 if current_date.year % 4 == 0 and (current_date.year % 100 != 0 or current_date.year % 400 == 0) else 28
            if current_date.day == days_in_feb:
                extra_days = 30 - days_in_feb
                if extra_days > 0:
                    extra_interest = extra_days * ((interest_bearing_balance * rate) / (360 * 100))
                    total_interest += extra_interest
                    accumulated_interest += extra_interest
                    monthly_interests[month_key] += extra_interest
        
        # Капитализация
        if capitalization:
            last_day_of_month = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            is_capitalization_day = (current_date.day == open_day) or (open_day > last_day_of_month.day and current_date.day == last_day_of_month.day)
            
            if is_capitalization_day and not is_same_day(current_date, start_date):
                interest_bearing_balance += accumulated_interest
                accumulated_interest = 0
        
        current_date += timedelta(days=1)
    
    total_amount = interest_bearing_balance + accumulated_interest if capitalization else total_principal + total_interest
    
    return {
        'total_interest': total_interest,
        'total_amount': total_amount,
        'monthly_interests': monthly_interests,
        'rate': rate,
        'total_principal': total_principal
    }

def parse_natural_language(text):
    """Парсинг естественного языка"""
    text = text.lower().strip()
    
    # Поиск валюты
    currency = None
    if any(word in text for word in ['сом', 'кгс', 'kgs']):
        currency = 'KGS'
    elif any(word in text for word in ['доллар', 'доллары', 'usd', '$']):
        currency = 'USD'
    elif any(word in text for word in ['евро', 'eur', '€']):
        currency = 'EUR'
    
    # Поиск суммы
    amount_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:тысяч|тыс|k|млн|миллион|сома?|доллара?|евро?)?', text)
    amount = None
    if amount_match:
        amount_str = amount_match.group(1).replace(',', '.')
        amount = float(amount_str)
        # Конвертация тысяч/миллионов
        if any(word in text for word in ['тысяч', 'тыс', 'k']):
            amount *= 1000
        elif any(word in text for word in ['млн', 'миллион']):
            amount *= 1000000
    
    # Поиск срока
    term = None
    if any(word in text for word in ['3', 'три', 'трех']):
        term = 3
    elif any(word in text for word in ['6', 'шесть', 'шести']):
        term = 6
    elif any(word in text for word in ['12', 'год', 'годовой', 'годовых']):
        term = 12
    elif any(word in text for word in ['24', 'два года', 'двухлетний']):
        term = 24
    elif any(word in text for word in ['36', 'три года', 'трехлетний']):
        term = 36
    
    # Поиск капитализации
    capitalization = any(word in text for word in ['капитализация', 'капитализировать', 'с капитализацией'])
    
    return {
        'currency': currency,
        'amount': amount,
        'term': term,
        'capitalization': capitalization
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_text = """
🏦 **Депозитный калькулятор Pro**

Привет! Я умный помощник для расчета депозитов.

**Что я умею:**
• 🧮 Точные расчеты по банковским правилам
• 💬 Понимаю естественный язык
• 📊 Детальная аналитика и сравнения
• 💡 Советы по оптимизации доходности
• 🔄 Поддержка довкладов и капитализации

**Выберите действие:**
"""
    
    keyboard = [
        [InlineKeyboardButton("🧮 Быстрый расчет", callback_data="quick_calc")],
        [InlineKeyboardButton("📋 Пошаговый расчет", callback_data="step_calc")],
        [InlineKeyboardButton("📊 Сравнить варианты", callback_data="compare")],
        [InlineKeyboardButton("❓ FAQ и советы", callback_data="faq")],
        [InlineKeyboardButton("📈 Ставки и условия", callback_data="rates")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    
    # Проверяем FAQ
    for question, answer in FAQ.items():
        if any(word in text.lower() for word in question.split()):
            await update.message.reply_text(answer, parse_mode='Markdown')
            return
    
    # Парсим естественный язык
    parsed = parse_natural_language(text)
    
    if parsed['amount'] and parsed['currency'] and parsed['term']:
        # Есть все данные для расчета
        start_date = date.today()
        result = calculate_deposit(
            currency=parsed['currency'],
            term=parsed['term'],
            start_date=start_date,
            initial_amount=parsed['amount'],
            capitalization=parsed['capitalization']
        )
        
        response = f"""
💰 **Расчет депозита**

**Параметры:**
• Сумма: {format_number(parsed['amount'])} {currency_symbol(parsed['currency'])}
• Срок: {parsed['term']} месяцев
• Ставка: {result['rate']}% годовых
• Капитализация: {'Да' if parsed['capitalization'] else 'Нет'}

**Результат:**
• Проценты: {format_number(result['total_interest'])} {currency_symbol(parsed['currency'])}
• Итого: {format_number(result['total_amount'])} {currency_symbol(parsed['currency'])}

**Детализация по месяцам:**
"""
        
        month_names = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", 
                      "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        
        for key, interest in sorted(result['monthly_interests'].items()):
            if interest > 0:
                year, month = key.split('-')
                month_name = month_names[int(month)]
                response += f"• {month_name} {year}: {format_number(interest)} {currency_symbol(parsed['currency'])}\n"
        
        # Добавляем советы
        if parsed['amount'] >= 100000 and parsed['currency'] == 'KGS':
            response += "\n💡 **Совет**: Рассмотрите капитализацию для увеличения дохода!"
        
        await update.message.reply_text(response, parse_mode='Markdown')
        
    elif any(word in text.lower() for word in ['ставки', 'проценты', 'условия']):
        await update.message.reply_text(FAQ['какие есть валюты'], parse_mode='Markdown')
        
    elif any(word in text.lower() for word in ['как', 'расчет', 'формула']):
        await update.message.reply_text(FAQ['как рассчитываются проценты'], parse_mode='Markdown')
        
    elif any(word in text.lower() for word in ['совет', 'рекомендация', 'лучше']):
        await update.message.reply_text(FAQ['советы'], parse_mode='Markdown')
        
    else:
        help_text = """
🤔 Не совсем понял ваш запрос. Попробуйте:

**Для расчета:**
• "Депозит 100 тысяч сом на год"
• "50 тысяч долларов на 6 месяцев с капитализацией"

**Для информации:**
• "Какие ставки?"
• "Как рассчитываются проценты?"
• "Что такое капитализация?"
• "Советы по депозитам"

Или используйте кнопки ниже 👇
"""
        keyboard = [
            [InlineKeyboardButton("🧮 Быстрый расчет", callback_data="quick_calc")],
            [InlineKeyboardButton("❓ FAQ", callback_data="faq")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(help_text, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "quick_calc":
        await query.edit_message_text(
            "🧮 **Быстрый расчет депозита**\n\n"
            "Отправьте параметры депозита в любом формате:\n\n"
            "**Примеры:**\n"
            "• 100 тысяч сом на год\n"
            "• 50 тысяч долларов на 6 месяцев\n"
            "• 10 тысяч евро на 2 года с капитализацией\n\n"
            "Или просто напишите сумму, валюту и срок!",
            parse_mode='Markdown'
        )
        
    elif query.data == "step_calc":
        keyboard = [
            [InlineKeyboardButton("🇰🇬 Сом (KGS)", callback_data="currency_KGS")],
            [InlineKeyboardButton("🇺🇸 Доллар (USD)", callback_data="currency_USD")],
            [InlineKeyboardButton("🇪🇺 Евро (EUR)", callback_data="currency_EUR")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📋 **Пошаговый расчет**\n\n"
            "Выберите валюту депозита:",
            reply_markup=reply_markup
        )
        
    elif query.data == "compare":
        await query.edit_message_text(
            "📊 **Сравнение вариантов депозита**\n\n"
            "Отправьте сумму для сравнения разных вариантов:\n\n"
            "**Пример:** 100 тысяч сом\n\n"
            "Я покажу сравнение:\n"
            "• Без капитализации\n"
            "• С капитализацией\n"
            "• С довкладами\n"
            "• Разные сроки",
            parse_mode='Markdown'
        )
        
    elif query.data == "faq":
        faq_text = """
❓ **FAQ и советы**

Выберите интересующий вопрос:

• Как рассчитываются проценты?
• Какие есть валюты и ставки?
• Что такое капитализация?
• Можно ли довкладывать?
• Как досрочно закрыть депозит?
• Налогообложение депозитов
• Страхование депозитов
• Сравнение вариантов
• Советы по депозитам

Просто напишите ваш вопрос! 👇
"""
        await query.edit_message_text(faq_text, parse_mode='Markdown')
        
    elif query.data == "rates":
        await query.edit_message_text(FAQ['какие есть валюты'], parse_mode='Markdown')
        
    elif query.data.startswith("currency_"):
        currency = query.data.split("_")[1]
        context.user_data['currency'] = currency
        
        keyboard = [
            [InlineKeyboardButton("3 месяца", callback_data=f"term_3")],
            [InlineKeyboardButton("6 месяцев", callback_data=f"term_6")],
            [InlineKeyboardButton("12 месяцев", callback_data=f"term_12")],
            [InlineKeyboardButton("24 месяца", callback_data=f"term_24")],
            [InlineKeyboardButton("36 месяцев", callback_data=f"term_36")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        rate = RATES[currency][12]  # Показываем ставку за год
        await query.edit_message_text(
            f"📋 **Выбрана валюта: {currency_symbol(currency)}**\n\n"
            f"Ставка за год: {rate}%\n\n"
            "Теперь выберите срок депозита:",
            reply_markup=reply_markup
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
🔧 **Справка по командам**

**Основные команды:**
• `/start` - запуск бота
• `/help` - эта справка
• `/rates` - текущие ставки
• `/faq` - часто задаваемые вопросы

**Примеры запросов:**
• "100 тысяч сом на год"
• "50 тысяч долларов с капитализацией"
• "Какие ставки по евро?"
• "Советы по депозитам"

**Особенности:**
• Понимаю естественный язык
• Учитываю банковские правила
• Показываю детализацию
• Даю персональные советы

Нужна помощь? Напишите ваш вопрос!
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def rates_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /rates"""
    await update.message.reply_text(FAQ['какие есть валюты'], parse_mode='Markdown')

async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /faq"""
    faq_text = """
❓ **Часто задаваемые вопросы**

Выберите интересующий вопрос:

• Как рассчитываются проценты?
• Какие есть валюты и ставки?
• Что такое капитализация?
• Можно ли довкладывать?
• Как досрочно закрыть депозит?
• Налогообложение депозитов
• Страхование депозитов
• Сравнение вариантов
• Советы по депозитам

Просто напишите ваш вопрос! 👇
"""
    await update.message.reply_text(faq_text, parse_mode='Markdown')

def main():
    """Основная функция"""
    # Получаем токен из переменных окружения
    TOKEN = os.getenv("BOT_TOKEN")
    
    if not TOKEN:
        print("❌ Ошибка: не найден токен бота!")
        print("Создайте файл .env с содержимым: BOT_TOKEN=your_token_here")
        return
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("rates", rates_command))
    application.add_handler(CommandHandler("faq", faq_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Запускаем бота
    print("🤖 Депозитный калькулятор Pro запущен!")
    print("📊 Ставки загружены")
    print("💬 Бот готов к работе")
    print("Нажмите Ctrl+C для остановки")
    
    application.run_polling()

if __name__ == '__main__':
    main() 