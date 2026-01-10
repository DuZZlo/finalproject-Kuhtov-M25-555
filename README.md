# finalproject_Kuhtov_M25-555

# ValutaTrade Hub - Платформа для отслеживания и симуляции торговли валютами

## Описание проекта

**ValutaTrade Hub** — это консольное приложение для симуляции торговли валютами, реализованное как полноценный Python-пакет. Платформа позволяет пользователям регистрироваться, управлять виртуальными портфелями фиатных и криптовалют, совершать сделки по покупке/продаже и отслеживать актуальные курсы в реальном времени.

Проект демонстрирует современные подходы к разработке на Python:
- Управление проектом с помощью Poetry
- Качество кода с использованием Ruff (PEP8)
- ООП-архитектура с разделением ответственности
- Обработка исключений и использование декораторов
- Микросервисная архитектура (Core Service + Parser Service)


## Установка и настройка

### Предварительные требования

- Python 3.10 или выше
- Poetry

### Установка

1. Клонируйте репозиторий:
    ```bash
    git clone https://github.com/DuZZlo/finalproject-Kuhtov-M25-555.git
    cd finalproject-Kuhtov-M25-555

2. Установите зависимости:
    make install

### Запуск

    make project

Основные CLI команды
Регистрация и аутентификация:
    # Регистрация нового пользователя
    valutatrade register --username alice --password secret123

    # Вход в систему
    valutatrade login --username alice --password secret123

Управление портфелем
    # Показать портфель (в USD)
    valutatrade show-portfolio

    # Показать портфель в другой валюте
    valutatrade show-portfolio --base EUR

    # Купить валюту
    valutatrade buy --currency BTC --amount 0.01

    # Продать валюту
    valutatrade sell --currency BTC --amount 0.005

Работа с курсами валют
    # Получить курс одной валюты к другой
    valutatrade get-rate --from USD --to BTC
    valutatrade get-rate --from EUR --to JPY

    # Показать список поддерживаемых валют
    valutatrade list-currencies

    # Показать курсы из кэша
    valutatrade show-rates
    valutatrade show-rates --currency BTC
    valutatrade show-rates --top 5 --sort value

Управление Parser Service
    # Обновить курсы вручную
    valutatrade update-rates

    # Обновить только криптовалюты
    valutatrade update-rates --source coingecko

    # Обновить только фиатные валюты
    valutatrade update-rates --source exchangerate

    # Запустить фоновый парсер
    valutatrade start-parser --interval 10

    # Проверить статус парсера
    valutatrade parser-status

    # Остановить парсер
    valutatrade stop-parser

Кэширование курсов и TTL

  Как работает кэширование:
    1. Parser Service получает курсы от внешних API:
       - CoinGecko для криптовалют
       - ExchangeRate-API для фиатных валют

    2. Курсы сохраняются в data/rates.json:
    {
        "last_refresh": "2024-01-20T10:30:00",
        "source": "ParserService",
        "pairs": {
            "BTC_USD": {
            "rate": 89754.0,
            "updated_at": "2024-01-20T10:30:00",
            "source": "CoinGecko"
            },
            "EUR_USD": {
            "rate": 1.0876,
            "updated_at": "2024-01-20T10:30:00",
            "source": "ExchangeRate-API"
            }
        }
    }

    3. Core Service использует этот файл как кэш.

Настройка TTL (Time To Live)
  TTL настраивается в pyproject.toml:

    [tool.valutatrade]
    rates_ttl_seconds = 300  # 5 минут (по умолчанию)

Когда кэш устаревает:

    -При операции показывается предупреждение
    -Рекомендуется выполнить update-rates
    -Можно использовать --force для принудительного обновления

Ручное управление кэшем
    # Проверить состояние кэша
    valutatrade parser-status

    # Очистить кэш (файл будет пересоздан при следующем обновлении)
    rm data/rates.json

    # Принудительное обновление (игнорируя TTL)
    valutatrade update-rates --force

Настройка API ключей
  Для работы Parser Service требуется API ключ от ExchangeRate-API:

    1. Установите переменную окружения на текущую сессию
    export EXCHANGERATE_API_KEY="Ключ"

    2. Запустите обновление курсов
    poetry run valutatrade update-rates

Для удобства ввода команд в Makefile добавлены алиасы
  Помощь по алиасам можно посмотреть с помощью make aliases:

    aliases:
        make vt [command]        - Основная команда (valutatrade)
        make register            - Регистрация пользователя
        make login               - Вход в систему
        make logout              - Выход из системы
        make whoami              - Текущий пользователь
        make portfolio           - Показать портфель
        make buy                 - Купить валюту
        make sell                - Продать валюту
        make rate                - Получить курс
        make update-rates        - Обновить курсы
        make show-rates          - Показать курсы
        make list-currencies     - Список валют
        make start-parser        - Запустить парсер
        make stop-parser         - Остановить парсер
        make parser-status       - Статус парсера
    
    В случае передачи аргументов использовать "--" 
    Пример: make login -- --username xxxx --password xxxx
      или использовать poetry run valutatrade login --username xxxx --password xxxx