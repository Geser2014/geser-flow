"""
Точка входа Geser Flow.
"""

import sys
import os

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import App


def main():
    application = App()
    application.run()


if __name__ == "__main__":
    main()
