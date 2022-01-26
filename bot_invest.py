import ast
import logging
import os
import pytz
import sys
from threading import Thread

from telegram import ParseMode
from telegram.ext import (CommandHandler, Defaults, ExtBot, 
                          Filters, Updater)
from telegram.utils.request import Request

from config import WEBHOOK
from invest_bot.handlers import get_handlers_list
from invest_bot.messages import *
from invest_bot.utils import get_token

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.INFO,
    filename='log.log'
    )

aps_logger = logging.getLogger('apscheduler')
aps_logger.setLevel(logging.WARNING)

defaults = Defaults(
    tzinfo=pytz.timezone('Europe/Moscow'),
    parse_mode=ParseMode.HTML,
    disable_web_page_preview=True
    )
request = Request(con_pool_size=8)
ext_bot = ExtBot(token=get_token(), 
                 defaults=defaults, 
                 request=request)
mybot = Updater(bot=ext_bot)


def stop_and_restart():
    mybot.stop()
    os.execl(sys.executable, sys.executable, *sys.argv)


def restart(update, context):
    update.message.reply_text('Bot is restarting...')
    Thread(target=stop_and_restart).start()


def main():
    logging.info('Бот запускается.')
    dp = mybot.dispatcher

    TG_ADMIN_LIST = ast.literal_eval(os.environ['TG_ADMIN_LIST'])

    dp.add_handler(
        CommandHandler(
            'r', restart, filters=Filters.user(TG_ADMIN_LIST)
            )
        )

    handlers_list = get_handlers_list()

    for handler in handlers_list:
        dp.add_handler(handler)

    if WEBHOOK:
        webhook_domain = 'https://some-url.com'
        PORT = 5004

        mybot.start_webhook(listen='127.0.0.1',
                            port=PORT,
                            url_path=get_token(),
                            webhook_url=f'{webhook_domain}/{get_token()}')

        mybot.bot.set_webhook(f'{webhook_domain}/{get_token()}')
    else:
        mybot.start_polling()

    mybot.idle()


if __name__ == '__main__':
    main()
