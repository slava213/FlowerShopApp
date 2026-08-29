"""
Окремий процес для Telegram-бота.

Запускати НЕЗАЛЕЖНО від Flask-застосунку (окремим systemd-сервісом),
щоб бот працював і тоді, коли веб-сайт піднятий через Gunicorn
(де if __name__ == '__main__' у main.py не виконується).

Приклад запуску вручну:
    source venv/bin/activate
    python bot_runner.py
"""
import logging

from main import bot

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info('Запуск Telegram-бота (polling)...')
    bot.infinity_polling(
        allowed_updates=['message', 'callback_query'],
        timeout=30,
        long_polling_timeout=20,
    )