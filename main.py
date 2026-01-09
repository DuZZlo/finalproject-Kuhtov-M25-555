#!/usr/bin/env python3

from valutatrade_hub import setup_logging
from valutatrade_hub.cli.interface import main

if __name__ == "__main__":
    setup_logging()
    exit(main())