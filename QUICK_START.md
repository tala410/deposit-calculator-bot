# 🚀 Быстрый запуск Telegram бота

## 1. Создание бота (2 минуты)

1. Откройте Telegram
2. Найдите [@BotFather](https://t.me/botfather)
3. Отправьте `/newbot`
4. Введите имя бота (например: "Депозитный калькулятор")
5. Введите username (например: "deposit_calc_bot")
6. **Скопируйте токен** - он выглядит как `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

## 2. Установка (1 минута)

```bash
# Установите Python 3.8+ если еще не установлен
pip install -r requirements.txt
```

## 3. Настройка (30 секунд)

1. Создайте файл `.env` в папке проекта
2. Добавьте в него:
```
BOT_TOKEN=ваш_токен_здесь
```

## 4. Запуск (10 секунд)

```bash
python deposit_bot.py
```

## 5. Тестирование

1. Найдите вашего бота в Telegram по username
2. Отправьте `/start`
3. Попробуйте: "100 тысяч сом на год"

## ✅ Готово!

Бот работает! Теперь можно:
- Рассчитывать депозиты
- Задавать вопросы
- Получать советы

## 🔧 Для продакшена

### Heroku (бесплатно):
```bash
heroku create your-bot-name
git push heroku main
```

### Railway (бесплатно):
1. Подключите GitHub
2. Добавьте переменную `BOT_TOKEN`
3. Готово!

### VPS:
```bash
nohup python3 deposit_bot.py > bot.log 2>&1 &
```

## 🆘 Проблемы?

- **Бот не отвечает**: проверьте токен
- **Ошибки**: убедитесь что Python 3.8+
- **Не работает**: проверьте логи в консоли

## 📞 Поддержка

Создайте Issue в репозитории или напишите в Telegram! 