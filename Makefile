install:
	poetry install

lint:
	poetry run ruff check .

build:
	poetry build

package-install:
	python3 -m pip install dist/*.whl

publish:
	poetry publish --dry-run

# Короткие алиасы для команд
vt:
	@poetry run valutatrade $(filter-out $@,$(MAKECMDGOALS))

register:
	@poetry run valutatrade register $(filter-out $@,$(MAKECMDGOALS))

login:
	@poetry run valutatrade login $(filter-out $@,$(MAKECMDGOALS))

logout:
	@poetry run valutatrade logout

whoami:
	@poetry run valutatrade whoami

portfolio:
	@poetry run valutatrade show-portfolio $(filter-out $@,$(MAKECMDGOALS))

buy:
	@poetry run valutatrade buy $(filter-out $@,$(MAKECMDGOALS))

sell:
	@poetry run valutatrade sell $(filter-out $@,$(MAKECMDGOALS))

rate:
	@poetry run valutatrade get-rate $(filter-out $@,$(MAKECMDGOALS))

update-rates:
	@poetry run valutatrade update-rates $(filter-out $@,$(MAKECMDGOALS))

show-rates:
	@poetry run valutatrade show-rates $(filter-out $@,$(MAKECMDGOALS))

list-currencies:
	@poetry run valutatrade list-currencies

start-parser:
	@poetry run valutatrade start-parser $(filter-out $@,$(MAKECMDGOALS))

stop-parser:
	@poetry run valutatrade stop-parser

parser-status:
	@poetry run valutatrade parser-status

deposit:
	@poetry run valutatrade deposit $(filter-out $@,$(MAKECMDGOALS))

withdraw:
	@poetry run valutatrade withdraw $(filter-out $@,$(MAKECMDGOALS))

balance:
	@poetry run valutatrade balance

transfer:
	@poetry run valutatrade transfer $(filter-out $@,$(MAKECMDGOALS))

create-wallet:
	@poetry run valutatrade create-wallet $(filter-out $@,$(MAKECMDGOALS))

# Помощь по алиасам
aliases:
	@echo "Доступные короткие команды:"
	@echo "  make vt [command]        - Основная команда (valutatrade)"
	@echo "  make register            - Регистрация пользователя"
	@echo "  make login               - Вход в систему"
	@echo "  make logout              - Выход из системы"
	@echo "  make whoami              - Текущий пользователь"
	@echo "  make portfolio           - Показать портфель"
	@echo "  make buy                 - Купить валюту"
	@echo "  make sell                - Продать валюту"
	@echo "  make rate                - Получить курс"
	@echo "  make update-rates        - Обновить курсы"
	@echo "  make show-rates          - Показать курсы"
	@echo "  make list-currencies     - Список валют"
	@echo "  make start-parser        - Запустить парсер"
	@echo "  make stop-parser         - Остановить парсер"
	@echo "  make parser-status       - Статус парсера"
	@echo "  make deposit		      - Пополнить баланс"
	@echo "  make withdraw		      - Вывод средств"
	@echo "  make balance		      - Просмотр баланса"
	@echo "  make transfer		      - Перевод средств между кошельками"
	@echo "  make create-wallet		  - Создать кошелек"

.NOTPARALLEL: