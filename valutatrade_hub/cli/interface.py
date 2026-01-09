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
from valutatrade_hub.core.utils import (
    get_exchange_rate,
    validate_currency,
    validate_amount,
    load_json
)


class ValutaTradeCLI:
    
    def __init__(self):
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="valutatrade",
            description="ValutaTrade Hub - Платформа для отслеживания и симуляции торговли валютами",
            epilog="Используйте 'valutatrade <команда> --help' для получения справки по команде"
        )
        
        subparsers = parser.add_subparsers(
            dest="command",
            help="Доступные команды",
            required=True
        )
        
        register_parser = subparsers.add_parser(
            "register",
            help="Регистрация нового пользователя"
        )
        register_parser.add_argument(
            "--username",
            type=str,
            required=True,
            help="Имя пользователя"
        )
        register_parser.add_argument(
            "--password",
            type=str,
            required=True,
            help="Пароль (минимум 4 символа)"
        )
        
        login_parser = subparsers.add_parser(
            "login",
            help="Вход в систему"
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
        
        portfolio_parser = subparsers.add_parser(
            "show-portfolio",
            help="Показать портфель"
        )
        portfolio_parser.add_argument(
            "--base",
            type=str,
            default="USD",
            help="Базовая валюта для отображения (по умолчанию: USD)"
        )
        
        buy_parser = subparsers.add_parser(
            "buy",
            help="Купить валюту"
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
            help="Количество покупаемой валюты"
        )
        
        sell_parser = subparsers.add_parser(
            "sell",
            help="Продать валюту"
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
            help="Количество продаваемой валюты"
        )
        
        rate_parser = subparsers.add_parser(
            "get-rate",
            help="Получить курс валюты"
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
        
        return parser
    
    def _check_login(self) -> bool:
        if not SessionManager.is_logged_in():
            print("Сначала выполните login")
            return False
        return True
    
    def handle_register(self, args) -> int:
        success, message = UserManager.register(args.username, args.password)
        print(message)
        return 0 if success else 1
    
    def handle_login(self, args) -> int:
        success, message, user = UserManager.login(args.username, args.password)
        if success and user:
            SessionManager.set_current_user(user)
        print(message)
        return 0 if success else 1
    
    def handle_show_portfolio(self, args) -> int:
        if not self._check_login():
            return 1
        
        user = SessionManager.get_current_user()
        
        success, message, _ = PortfolioManager.show_portfolio(
            user.user_id, 
            args.base.upper()
        )
        
        print(message)
        return 0 if success else 1
    
    def handle_buy(self, args) -> int:
        if not self._check_login():
            return 1
        
        user = SessionManager.get_current_user()
        success, message = TradeManager.buy(user.user_id, args.currency, args.amount)
        print(message)
        return 0 if success else 1
    
    def handle_sell(self, args) -> int:
        if not self._check_login():
            return 1
        
        user = SessionManager.get_current_user()
        success, message = TradeManager.sell(user.user_id, args.currency, args.amount)
        print(message)
        return 0 if success else 1
    
    def handle_get_rate(self, args) -> int:
        from_currency = args.from_currency.upper()
        to_currency = args.to_currency.upper()
        
        success, message, _ = RateManager.get_rate(from_currency, to_currency)
        
        print(message)
        return 0 if success else 1
    
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
            }
            
            handler = handlers.get(parsed_args.command)
            if handler:
                return handler(parsed_args)
            else:
                print(f"Неизвестная команда: {parsed_args.command}")
                return 1
                
        except SystemExit:
            return 0
        except Exception as e:
            print(f"Ошибка: {e}")
            return 1


def main() -> int:
    cli = ValutaTradeCLI()
    return cli.run()

if __name__ == "__main__":
    sys.exit(main())