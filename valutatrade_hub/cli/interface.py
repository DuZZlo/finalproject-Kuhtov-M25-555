#!/usr/bin/env python3

import sys
import argparse
from typing import Optional

from valutatrade_hub.core.usecases import (
    SessionManager,
    UserManager,
    PortfolioManager,
    TradeManager,
    RateManager
)
from valutatrade_hub.core.exceptions import (
    InsufficientFundsError,
    CurrencyNotFoundError,
    ApiRequestError,
    AuthenticationError,
    PortfolioNotFoundError,
    ValidationError,
    RateUnavailableError,
    ValutaTradeError
)
from valutatrade_hub.core.currencies import CurrencyRegistry
from valutatrade_hub.infra.settings import SettingsLoader


class ValutaTradeCLI:
    
    def __init__(self):
        self.parser = self._create_parser()
        self._settings = SettingsLoader()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="valutatrade",
            description="ValutaTrade Hub - Платформа для отслеживания и симуляции торговли валютами",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="Используйте 'valutatrade <команда> --help' для получения справки по команде"
        )
        
        subparsers = parser.add_subparsers(
            dest="command",
            help="Доступные команды",
            required=True
        )
        
        # register
        register_parser = subparsers.add_parser(
            "register",
            help="Регистрация нового пользователя",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        register_parser.add_argument(
            "--username",
            type=str,
            required=True,
            help="Имя пользователя (уникальное)"
        )
        register_parser.add_argument(
            "--password",
            type=str,
            required=True,
            help="Пароль (минимум 4 символа)"
        )
        
        # login
        login_parser = subparsers.add_parser(
            "login",
            help="Вход в систему",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        login_parser.add_argument(
            "--username",
            type=str,
            required=True,
            help="Имя пользователя"
        )
        login_parser.add_argument(
            "--password",
            type=str,
            required=True,
            help="Пароль"
        )
        
        # show-portfolio
        portfolio_parser = subparsers.add_parser(
            "show-portfolio",
            help="Показать портфель",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        portfolio_parser.add_argument(
            "--base",
            type=str,
            default="USD",
            help="Базовая валюта для отображения"
        )
        
        # buy
        buy_parser = subparsers.add_parser(
            "buy",
            help="Купить валюту",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        buy_parser.add_argument(
            "--currency",
            type=str,
            required=True,
            help="Код покупаемой валюты (например, BTC)"
        )
        buy_parser.add_argument(
            "--amount",
            type=float,
            required=True,
            help="Количество покупаемой валюты (положительное число)"
        )
        
        # sell
        sell_parser = subparsers.add_parser(
            "sell",
            help="Продать валюту",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        sell_parser.add_argument(
            "--currency",
            type=str,
            required=True,
            help="Код продаваемой валюты"
        )
        sell_parser.add_argument(
            "--amount",
            type=float,
            required=True,
            help="Количество продаваемой валюты (положительное число)"
        )
        
        # get-rate
        rate_parser = subparsers.add_parser(
            "get-rate",
            help="Получить курс валюты",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        rate_parser.add_argument(
            "--from",
            dest="from_currency",
            type=str,
            required=True,
            help="Исходная валюта (например, USD)"
        )
        rate_parser.add_argument(
            "--to",
            dest="to_currency",
            type=str,
            required=True,
            help="Целевая валюта (например, BTC)"
        )
        
        # list-currencies
        list_parser = subparsers.add_parser(
            "list-currencies",
            help="Показать список поддерживаемых валют",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        
        # update-rates
        update_parser = subparsers.add_parser(
            "update-rates",
            help="Обновить курсы валют из внешних источников",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        update_parser.add_argument(
            "--source",
            type=str,
            choices=["coingecko", "exchangerate", "all"],
            default="all",
            help="Источник для обновления (coingecko, exchangerate или all)"
        )
        update_parser.add_argument(
            "--force",
            action="store_true",
            help="Принудительное обновление, даже если кеш актуален"
        )
        
        # show-rates
        show_rates_parser = subparsers.add_parser(
            "show-rates",
            help="Показать курсы валют из локального кеша",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description="""Показать курсы валют из локального кеша.
            Примеры:
            show-rates                    # Все курсы
            show-rates --currency BTC     # Только BTC
            show-rates --top 5            # Топ-5 по стоимости
            show-rates --base EUR         # Все курсы относительно EUR"""
        )
        show_rates_parser.add_argument(
            "--currency",
            type=str,
            help="Показать курс только для указанной валюты"
        )
        show_rates_parser.add_argument(
            "--top",
            type=int,
            help="Показать N самых дорогих криптовалют"
        )
        show_rates_parser.add_argument(
            "--base",
            type=str,
            default="USD",
            help="Базовая валюта для отображения"
        )
        show_rates_parser.add_argument(
            "--sort",
            type=str,
            choices=["name", "value", "change"],
            default="name",
            help="Сортировка результатов"
        )
        
        # start-parser
        start_parser = subparsers.add_parser(
            "start-parser",
            help="Запустить фоновый парсер курсов",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        start_parser.add_argument(
            "--interval",
            type=int,
            default=5,
            help="Интервал обновления в минутах"
        )
        
        # stop-parser
        subparsers.add_parser(
            "stop-parser",
            help="Остановить фоновый парсер курсов"
        )
        
        # parser-status
        subparsers.add_parser(
            "parser-status",
            help="Показать статус парсера курсов"
        )

        return parser
    
    def _check_login(self) -> bool:
        try:
            SessionManager.require_login()
            return True
        except AuthenticationError as e:
            print(f"Ошибка: {e}")
            return False
    
    def handle_register(self, args) -> int:
        try:
            success, message = UserManager.register(args.username, args.password)
            print(message)
            return 0 if success else 1
        except ValidationError as e:
            print(f"Ошибка валидации: {e}")
            return 1
        except Exception as e:
            print(f"Неизвестная ошибка: {e}")
            return 1
    
    def handle_login(self, args) -> int:
        try:
            success, message, user = UserManager.login(args.username, args.password)
            if success and user:
                SessionManager.set_current_user(user)
            print(message)
            return 0 if success else 1
        except AuthenticationError as e:
            print(f"Ошибка аутентификации: {e}")
            return 1
        except Exception as e:
            print(f"Неизвестная ошибка: {e}")
            return 1
    
    def handle_show_portfolio(self, args) -> int:
        if not self._check_login():
            return 1
        
        try:
            user = SessionManager.get_current_user()
            success, message, _ = PortfolioManager.show_portfolio(
                user.user_id, 
                args.base.upper()
            )
            print(message)
            return 0 if success else 1
        except CurrencyNotFoundError as e:
            print(f"Ошибка: {e}")
            print("\nДоступные валюты:")
            available_codes = CurrencyRegistry.get_all_codes()
            print("  " + ", ".join(available_codes))
            return 1
        except PortfolioNotFoundError as e:
            print(f"Ошибка: {e}")
            return 1
        except Exception as e:
            print(f"Неизвестная ошибка: {e}")
            return 1
    
    def handle_buy(self, args) -> int:
        if not self._check_login():
            return 1
        
        try:
            user = SessionManager.get_current_user()
            success, message = TradeManager.buy(user.user_id, args.currency.upper(), args.amount)
            print(message)
            return 0 if success else 1
        except CurrencyNotFoundError as e:
            print(f"Ошибка: {e}")
            print("\nДоступные валюты:")
            available_codes = CurrencyRegistry.get_all_codes()
            print("  " + ", ".join(available_codes))
            print("\nИспользуйте 'valutatrade list-currencies' для подробной информации.")
            return 1
        except ValidationError as e:
            print(f"Ошибка: {e}")
            return 1
        except InsufficientFundsError as e:
            print(f"Ошибка: {e}")
            return 1
        except RateUnavailableError as e:
            print(f"Ошибка: {e}")
            print("Повторите попытку позже или используйте другую валюту.")
            return 1
        except Exception as e:
            print(f"Неизвестная ошибка: {e}")
            return 1
    
    def handle_sell(self, args) -> int:
        if not self._check_login():
            return 1
        
        try:
            user = SessionManager.get_current_user()
            success, message = TradeManager.sell(user.user_id, args.currency.upper(), args.amount)
            print(message)
            return 0 if success else 1
        except CurrencyNotFoundError as e:
            print(f"Ошибка: {e}")
            print("\nДоступные валюты:")
            available_codes = CurrencyRegistry.get_all_codes()
            print("  " + ", ".join(available_codes))
            print("\nИспользуйте 'valutatrade list-currencies' для подробной информации.")
            return 1
        except ValidationError as e:
            print(f"Ошибка: {e}")
            return 1
        except InsufficientFundsError as e:
            print(f"Ошибка: {e}")
            return 1
        except RateUnavailableError as e:
            print(f"Ошибка: {e}")
            print("Повторите попытку позже или используйте другую валюту.")
            return 1
        except Exception as e:
            print(f"Неизвестная ошибка: {e}")
            return 1
    
    def handle_get_rate(self, args) -> int:
        try:
            from_currency = args.from_currency.upper()
            to_currency = args.to_currency.upper()
            
            success, message, _ = RateManager.get_rate(from_currency, to_currency)
            
            print(message)
            return 0 if success else 1
        except Exception as e:
            print(f"Неизвестная ошибка: {e}")
            return 1
    
    def handle_list_currencies(self, args) -> int:
        try:
            message = RateManager.list_supported_currencies()
            print(message)
            return 0
        except Exception as e:
            print(f"Ошибка: {e}")
            return 1

    def run(self, args=None) -> int:
        try:
            parsed_args = self.parser.parse_args(args)
            
            handlers = {
                "register": self.handle_register,
                "login": self.handle_login,
                "show-portfolio": self.handle_show_portfolio,
                "buy": self.handle_buy,
                "sell": self.handle_sell,
                "get-rate": self.handle_get_rate,
                "list-currencies": self.handle_list_currencies,
                "update-rates": self.handle_update_rates,
                "show-rates": self.handle_show_rates,
                "start-parser": self.handle_start_parser,
                "stop-parser": self.handle_stop_parser,
                "parser-status": self.handle_parser_status,
            }
            
            handler = handlers.get(parsed_args.command)
            if handler:
                return handler(parsed_args)
            else:
                print(f"Неизвестная команда: {parsed_args.command}")
                print("\nДоступные команды:")
                for cmd_name, cmd_parser in self.parser._subparsers._group_actions[0].choices.items():
                    print(f"  {cmd_name:20} {cmd_parser.description}")
                return 1
                
        except SystemExit:
            return 0
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
            return 1

    def handle_update_rates(self, args) -> int:
        try:
            from valutatrade_hub.parser_service.updater import RatesUpdater
            
            updater = RatesUpdater()
            
            if not args.force:
                cache_status = updater.storage.is_cache_valid()
                if cache_status:
                    print("Кеш курсов актуален. Используйте --force для принудительного обновления.")
                    data = updater.storage.load_current_rates()
                    if data:
                        last_refresh = data.get("last_refresh", "неизвестно")
                        rates_count = len(data.get("pairs", {}))
                        print(f"Последнее обновление: {last_refresh}")
                        print(f"Количество курсов: {rates_count}")
                    return 0
            
            source = None
            if args.source != "all":
                source = args.source
            
            print("Начало обновления курсов...")
            results = updater.update_rates(source=source)
            
            summary = updater.get_update_summary(results)
            print("\n" + summary)
            
            if results["status"] == "success":
                return 0
            else:
                return 1
                
        except ValueError as e:
            print(f"Ошибка: {e}")
            return 1
        except Exception as e:
            print(f"Неизвестная ошибка: {e}")
            return 1

    def handle_show_rates(self, args) -> int:
        try:
            from valutatrade_hub.parser_service.updater import RatesUpdater
            
            updater = RatesUpdater()
            
            cache_status = updater.check_rates_available()
            
            if not cache_status["available"] and cache_status["rates_count"] == 0:
                print("Локальный кеш курсов пуст.")
                print("Выполните 'valutatrade update-rates', чтобы загрузить данные.")
                return 1
            
            data = updater.storage.load_current_rates()
            if not data or "pairs" not in data:
                print("Ошибка: не удалось загрузить данные курсов")
                return 1
            
            pairs = data["pairs"]
            last_refresh = data.get("last_refresh", "неизвестно")
            source = data.get("source", "неизвестно")
            
            if args.currency:
                currency = args.currency.upper()
                filtered_pairs = {}
                
                for pair, info in pairs.items():
                    from_curr, to_curr = pair.split("_")
                    if from_curr == currency or to_curr == currency:
                        filtered_pairs[pair] = info
                
                if not filtered_pairs:
                    print(f"Курс для '{args.currency}' не найден в кеше.")
                    print(f"Доступные валюты: {', '.join(sorted(set([p.split('_')[0] for p in pairs.keys()])))}")
                    return 1
                
                pairs = filtered_pairs
            
            if args.base.upper() != "USD":
                usd_to_base_rate = updater.storage.get_rate("USD", args.base.upper())
                if usd_to_base_rate:
                    converted_pairs = {}
                    for pair, info in pairs.items():
                        from_curr, to_curr = pair.split("_")
                        if to_curr == "USD":
                            new_pair = f"{from_curr}_{args.base.upper()}"
                            converted_pairs[new_pair] = {
                                **info,
                                "rate": info["rate"] * usd_to_base_rate
                            }
                    pairs = converted_pairs
            
            sorted_items = list(pairs.items())
            
            if args.sort == "value":
                sorted_items.sort(key=lambda x: x[1]["rate"], reverse=True)
            elif args.sort == "name":
                sorted_items.sort(key=lambda x: x[0])
            
            if args.top:
                sorted_items = sorted_items[:args.top]
            
            print(f"Курсы из кеша (обновлено: {last_refresh}, источник: {source}):")
            print("=" * 60)
            
            for pair, info in sorted_items:
                from_curr, to_curr = pair.split("_")
                rate = info["rate"]
                updated_at = info.get("updated_at", "неизвестно")
                
                print(f"{pair:15} {rate:>15.8f}  ({updated_at})")
            
            print("=" * 60)
            print(f"Всего курсов: {len(sorted_items)}")
            
            if not cache_status["available"]:
                print("\nВнимание: кеш устарел!")
                print("Используйте 'valutatrade update-rates' для обновления данных.")
            
            return 0
            
        except Exception as e:
            print(f"Ошибка: {e}")
            return 1

    def handle_start_parser(self, args) -> int:
        try:
            from valutatrade_hub.parser_service.scheduler import RatesScheduler
            from valutatrade_hub.parser_service.config import ParserConfig
            
            config = ParserConfig()
            if args.interval > 0:
                config.UPDATE_INTERVAL_MINUTES = args.interval
            
            # Запускаем планировщик
            scheduler = RatesScheduler(config)
            scheduler.start(run_immediately=True)
            
            print(f"Парсер запущен с интервалом {args.interval} минут")
            print("Парсер работает в фоновом режиме.")
            print("Используйте 'valutatrade parser-status' для проверки состояния.")
            print("Используйте 'valutatrade stop-parser' для остановки.")
            
            self._parser_scheduler = scheduler
            
            return 0
            
        except Exception as e:
            print(f"Ошибка при запуске парсера: {e}")
            return 1

    def handle_stop_parser(self, args) -> int:
        try:
            if hasattr(self, '_parser_scheduler') and self._parser_scheduler:
                self._parser_scheduler.stop()
                print("Парсер остановлен")
                return 0
            else:
                print("Парсер не запущен")
                return 0
                
        except Exception as e:
            print(f"Ошибка при остановке парсера: {e}")
            return 1

    def handle_parser_status(self, args) -> int:
        try:
            from valutatrade_hub.parser_service.updater import RatesUpdater
            
            updater = RatesUpdater()
            
            cache_status = updater.check_rates_available()
            
            print("Статус парсера курсов:")
            print("=" * 50)
            
            print("\nКеш курсов:")
            if cache_status["available"]:
                print(f"  Статус: Актуален")
            else:
                print(f"  Статус: {cache_status['message']}")
            
            print(f"  Курсов: {cache_status['rates_count']}")
            print(f"  Последнее обновление: {cache_status['last_refresh'] or 'никогда'}")
            
            if hasattr(self, '_parser_scheduler') and self._parser_scheduler:
                stats = self._parser_scheduler.get_stats()
                print("\nФоновый парсер:")
                if stats["started"]:
                    print(f"  Статус: Запущен")
                    print(f"  Интервал: {stats['interval_minutes']} мин")
                    print(f"  Обновлений: {stats['update_count']}")
                    print(f"  Ошибок: {stats['error_count']}")
                    print(f"  Успешность: {stats['success_rate']:.1%}")
                    print(f"  Последнее: {stats['last_update']}")
                else:
                    print("  Статус: Остановлен")
            else:
                print("\nФоновый парсер:  Не запущен")
            
            print(f"\n💰 Отслеживаемые валюты:")
            print(f"  Фиатные: {', '.join(updater.config.FIAT_CURRENCIES)}")
            print(f"  Крипто: {', '.join(updater.config.CRYPTO_CURRENCIES)}")
            
            print("=" * 50)
            return 0
            
        except Exception as e:
            print(f"Ошибка при получении статуса: {e}")
            return 1

def main() -> int:
    cli = ValutaTradeCLI()
    return cli.run()

if __name__ == "__main__":
    sys.exit(main())