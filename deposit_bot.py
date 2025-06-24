import logging
import re
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import json
from config import BOT_TOKEN

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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

**Доллар (USD):**
• 3 месяца: {RATES['USD'][3]}%
• 6 месяцев: {RATES['USD'][6]}%
• 12 месяцев: {RATES['USD'][12]}%
• 24 месяца: {RATES['USD'][24]}%

**Евро (EUR):**
• 3 месяца: {RATES['EUR'][3]}%
• 6 месяцев: {RATES['EUR'][6]}%
• 12 месяцев: {RATES['EUR'][12]}%
• 24 месяца: {RATES['EUR'][24]}%
""",
    
    'что такое капитализация': """
💡 **Капитализация процентов:**

Капитализация - это когда начисленные проценты добавляются к основной сумме депозита и в дальнейшем тоже приносят доход.

**Без капитализации:**
• Проценты выплачиваются ежемесячно
• Основная сумма остается неизменной

**С капитализацией:**
• Проценты можно довкладывать вручную ежемесячно
• При довкладе процентов они добавляются к депозиту
• В следующем месяце проценты начисляются на увеличенную сумму
• Общий доход выше при регулярных довкладах

**Пример**: 100,000 сом на 12 месяцев под 14.5%
• Без капитализации: 14,500 сом
• С ежемесячными довкладами процентов: ~15,600 сом (+1,100 сом)

💡 **Важно**: Капитализация происходит только при ручном довкладе процентов!
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
        'rate': rate
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
🏦 **Депозитный калькулятор**

Привет! Я помогу рассчитать доходность по депозиту.

**Что я умею:**
• Рассчитывать проценты по депозитам
• Учитывать довклады и капитализацию
• Отвечать на вопросы о депозитах
• Показывать детализацию по месяцам

**Примеры запросов:**
• "Рассчитай депозит 100 тысяч сом на год"
• "Сколько будет с капитализацией?"
• "Какие ставки по долларам?"
• "Как рассчитываются проценты?"

Начните с расчета или задайте вопрос! 👇
"""
    
    keyboard = [
        [InlineKeyboardButton("💰 Рассчитать депозит", callback_data="calculate")],
        [InlineKeyboardButton("❓ FAQ", callback_data="faq")],
        [InlineKeyboardButton("📊 Ставки", callback_data="rates")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text.lower()
    
    # Сначала парсим естественный язык для расчета
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
        
        await update.message.reply_text(response, parse_mode='Markdown')
        return
    
    # Потом проверяем конкретные вопросы
    if any(phrase in text for phrase in ['как рассчитываются', 'как считается', 'формула расчета']):
        await update.message.reply_text(FAQ['как рассчитываются проценты'], parse_mode='Markdown')
        return
        
    elif any(word in text for word in ['ставки', 'условия', 'тарифы']) and 'как' not in text:
        await update.message.reply_text(FAQ['какие есть валюты'], parse_mode='Markdown')
        return
        
    # Проверяем FAQ в последнюю очередь
    for question, answer in FAQ.items():
        if any(word in text for word in question.split()):
            await update.message.reply_text(answer, parse_mode='Markdown')
            return
    
    # Если ничего не подошло
    help_text = """
🤔 Не совсем понял ваш запрос. Попробуйте:

**Для расчета:**
• "1000 сом на год"
• "50 тысяч долларов на 6 месяцев"
• "10 тысяч евро на 2 года с капитализацией"

**Для информации:**
• "Какие ставки?"
• "Как рассчитываются проценты?"
• "Что такое капитализация?"
• "Можно ли довкладывать?"

Или используйте кнопки ниже 👇
"""
    keyboard = [
        [InlineKeyboardButton("💰 Рассчитать", callback_data="calculate")],
        [InlineKeyboardButton("❓ FAQ", callback_data="faq")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(help_text, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "calculate":
        await query.edit_message_text(
            "💰 **Расчет депозита**\n\n"
            "Отправьте параметры депозита в любом формате:\n\n"
            "**Примеры:**\n"
            "• 100 тысяч сом на год\n"
            "• 50 тысяч долларов на 6 месяцев\n"
            "• 10 тысяч евро на 2 года с капитализацией\n\n"
            "Или просто напишите сумму, валюту и срок!",
            parse_mode='Markdown'
        )
        
    elif query.data == "faq":
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

Просто напишите ваш вопрос! 👇
"""
        await query.edit_message_text(faq_text, parse_mode='Markdown')
        
    elif query.data == "rates":
        await query.edit_message_text(FAQ['какие есть валюты'], parse_mode='Markdown')

def main():
    """Основная функция"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Запускаем бота
    print("🤖 Бот запущен! Нажмите Ctrl+C для остановки.")
    application.run_polling()

if __name__ == '__main__':
    main() 