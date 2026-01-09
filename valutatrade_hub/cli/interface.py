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
        except CurrencyNotFoundError as e:
            print(f"Ошибка: {e}")
            print("\nИспользуйте 'valutatrade list-currencies' для просмотра доступных валют.")
            return 1
        except ApiRequestError as e:
            print(f"Ошибка API: {e}")
            print("Повторите попытку позже или проверьте подключение к сети.")
            return 1
        except RateUnavailableError as e:
            print(f"Ошибка: {e}")
            return 1
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


def main() -> int:
    cli = ValutaTradeCLI()
    return cli.run()

if __name__ == "__main__":
    sys.exit(main())