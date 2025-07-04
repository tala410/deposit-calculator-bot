# Техническое задание: Интеграция калькулятора для прогнозирования доходности по существующим вкладам

## 1. Общее описание

Настоящий документ описывает требования к разработке и интеграции калькулятора для прогнозирования доходности по **существующим банковским вкладам клиента**.

**Цель:** Предоставить клиенту инструмент, который позволяет на основе данных его реального вклада рассчитать и спрогнозировать итоговую доходность с учетом гипотетических пополнений и **реинвестирования процентов**.

**Ключевая особенность:** Калькулятор использует **гибридный подход**.
1.  **Основа:** Начальные параметры вклада (сумма, ставка, срок и т.д.) загружаются из существующего API банка по реальному депозиту клиента.
2.  **Прогноз:** Пользователь может добавлять "фантазийные" данные — будущие пополнения, а также выбрать опцию для симуляции регулярного реинвестирования начисленных процентов.
3.  **Расчет:** Вся логика калькуляции, учитывающая и реальные, и гипотетические данные, реализуется на стороне клиента (front-end, JavaScript).

## 2. Интеграция с API банка

Для получения исходных данных по вкладам клиента будет использоваться существующий эндпоинт, описанный в документации.

### 2.1. Используемый эндпоинт: `GET /api/deposits`

*   **Метод:** `GET`
*   **Аутентификация:** Требуется (по `clientCode`).
*   **Описание:** Получает список всех активных депозитов клиента.
*   **Параметры:**
    *   `clientCode` (string, обязательный): Идентификатор клиента.
*   **Пример запроса:** `api/deposits?clientCode=008.158228`

### 2.2. Сценарий работы
1.  Приложение запрашивает у пользователя или из сессии `clientCode`.
2.  Приложение выполняет запрос `GET /api/deposits`.
3.  Пользователь выбирает из полученного списка депозит, для которого хочет сделать прогноз.
4.  Интерфейс калькулятора автоматически заполняется данными из ответа API.

### 2.3. Сопоставление полей (Mapping)

Поля из ответа `GET /api/deposits` должны быть сопоставлены с параметрами калькулятора следующим образом:

| Поле в ответе API (`deposits[n]`) | Параметр калькулятора                                |
| :--------------------------------- | :--------------------------------------------------- |
| `accBal`                           | `initialAmount` (Начальная/текущая сумма)            |
| `beginDate`                        | `startDate` (Дата открытия)                          |
| `period`                           | `term` (Срок в месяцах)                              |
| `percent`                          | `rate` (Процентная ставка)                           |
| `currency`                         | `currency` (Валюта)                                  |

## 3. Логика расчета на Front-End

Вся логика калькуляции реализуется в JavaScript на основе данных, полученных из API, и пользовательского ввода.

### 3.1. Входные параметры для расчета

Функция расчета должна принимать на вход следующие данные:

*   `initialAmount` (number): **Получено из API (`accBal`)**.
*   `startDate` (string): **Получено из API (`beginDate`)**.
*   `term` (number): **Получено из API (`period`)**.
*   `rate` (number): **Получено из API (`percent`)**.
*   `currency` (string): **Получено из API (`currency`)**.
*   `reinvestInterest` (boolean): **Вводится пользователем**. Флаг, указывающий, нужно ли симулировать реинвестирование процентов.
*   `additions` (array of objects): **Вводится пользователем**. Массив гипотетических пополнений, где каждый объект имеет вид `{ date: 'YYYY-MM-DD', amount: 1000 }`.

### 3.2. Алгоритм пошагового расчета

Расчет производится в цикле по дням, от `startDate` до `endDate`. **Этот алгоритм должен быть реализован в точности, как описано.**

1.  **Определение конечной даты:** `endDate` вычисляется как `startDate` + `term` (в месяцах) - 1 день.
2.  **Инициализация переменных:**
    *   `totalInterest = 0` (общие накопленные проценты).
    *   `interestBearingBalance = initialAmount` (сумма, на которую начисляются проценты).
    *   `accumulatedInterest = 0` (проценты, накопленные за расчетный период).
3.  **Цикл по дням:** Для каждого дня `currentDay` в периоде от `startDate` до `endDate`:
    1.  **Пропуск дня открытия:** Если `currentDay` совпадает с `startDate`, начисления не производятся.
    2.  **Расчет дневного процента:** `dailyInterest = (interestBearingBalance * rate) / 36000`.
    3.  **Правило "30 дней в месяце":** Если день месяца (`currentDay.getDate()`) равен 31, то `dailyInterest` за этот день принудительно обнуляется.
    4.  **Корректировка для февраля:** В последний день февраля (28 или 29) нужно доначислить проценты за недостающие до 30 дней (2 или 1 день соответственно).
    5.  **Суммирование процентов:** `totalInterest += dailyInterest`, `accumulatedInterest += dailyInterest`.
    6.  **Логика реинвестирования (если `reinvestInterest` = true):**
        *   Проверить, является ли `currentDay` днем выплаты процентов (число месяца совпадает с числом `startDate`, либо последний день месяца, если в текущем месяце такой даты нет).
        *   Если это день выплаты и не `startDate`, то сумма накопленных процентов (`accumulatedInterest`) добавляется к основному балансу: `interestBearingBalance += accumulatedInterest`.
        *   После этого `accumulatedInterest` обнуляется.
    7.  **Логика пополнений:**
        *   **Важно:** Этот шаг выполняется **после** начисления процентов за `currentDay`.
        *   Проверить, есть ли пополнение в `additions` с датой, равной `currentDay`.
        *   Если да, то `interestBearingBalance += addition.amount`.

### 3.3. Выходные данные (результат)

Функция расчета должна возвращать объект со следующей структурой:

```json
{
  "totalInterest": 18060.17, // Общая сумма начисленных процентов
  "finalAmount": 130060.17, // Итоговая сумма в конце срока (вложения + проценты)
  "monthlyDetails": [
    { "month": "Март 2025 г.", "interest": 1237.50 },
    { "month": "Апрель 2025 г.", "interest": 1413.50 }
    // ... и так далее для каждого месяца
  ]
}
```

## 4. Пример для тестирования

Разработчики должны использовать этот эталонный пример для проверки корректности реализации самого алгоритма расчета.

*   **Начальная сумма:** 100 000 KGS
*   **Дата открытия:** 03.03.2025
*   **Срок:** 12 мес.
*   **Ставка:** 16.50%
*   **Реинвестирование процентов:** `false`
*   **Пополнения:**
    *   09.04.2025: +4000
    *   12.05.2025: +4000
    *   09.06.2025: +4000
*   **Ожидаемый результат:**
    *   **Накопленные проценты:** 18 060.17 KGS
    *   **Сумма в конце срока:** 130 060.17 KGS
    *   **Разбивка по месяцам:**
        *   Март 2025 г.: 1 237.50
        *   Апрель 2025 г.: 1 413.50
        *   Май 2025 г.: 1 463.00
        *   ...и так далее. 