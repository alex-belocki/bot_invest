from datetime import timedelta

from sqlalchemy.orm import sessionmaker
from telegram.ext import (CallbackQueryHandler, CommandHandler, 
                          ConversationHandler, Filters, 
                          MessageHandler)

from config import engine
import invest_bot.callbacks.calculator as calculator
import invest_bot.callbacks.callbacks as callbacks
import invest_bot.callbacks.show_account as show_account
import invest_bot.callbacks.partners as partners
import invest_bot.callbacks.search as search
import invest_bot.callbacks.top_investors as top_investors
import invest_bot.callbacks.top_partners as top_partners
import invest_bot.callbacks.wallet as wallet
from invest_bot.models import Button, Settings
from invest_bot.utils import get_button


def get_sorted_handlers_list(loc):
    keys_list = [key for key in list(loc.keys()) if key.startswith('h_')]
    sorted_keys = sorted(keys_list, key=lambda x: int(x.split('h_')[-1]))
    return [loc[key] for key in sorted_keys]


def get_menu_handlers_list(session):
    ''' 
    Список обработчиков, чтобы можно было досрочно 
    завершить диалог. Добавляется в ConversationHandler в начало списка
    '''
    slugs_list = ['btn_account', 'btn_wallet', 'btn_partners',
                  'btn_calc', 'btn_top', 'btn_search', 'btn_cancel']

    buttons_list = session.query(Button)\
        .filter(Button.slug.in_(slugs_list))

    handlers_list = list()
    for button in buttons_list:
        if button.slug == 'btn_account':
            settings = session\
                .query(Settings)\
                .filter_by(name='Настройки')\
                .first()
            callback = show_account.show_account
            text1 = button.text.format(sex_emoji=settings.sex_emoji_male)
            text2 = button.text.format(sex_emoji=settings.sex_emoji_female)
            button.text = text1 + '|' + text2
        elif button.slug == 'btn_wallet':
            callback = wallet.show_wallet
        elif button.slug == 'btn_partners':
            callback = partners.show_partners
        elif button.slug == 'btn_calc':
            callback = calculator.enter_sum_to_calc
        elif button.slug == 'btn_top':
            callback = top_investors.show_investors_top
        elif button.slug == 'btn_search':
            callback = search.show_search
        elif button.slug == 'btn_cancel':
            callback = wallet.wallet_cancel

        handlers_list.append(
            MessageHandler(Filters.regex(f'^({button.text})$'),
                           callback)
            )
    return handlers_list


def get_handlers_list():
    Session = sessionmaker(bind=engine)
    session = Session()

    settings = session.query(Settings).filter_by(name='Настройки').first()

    menu_handlers_list = get_menu_handlers_list(session)

    button = get_button(session, 'btn_calc')
    h_0 = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(f'^({button.text})$'), 
                           calculator.enter_sum_to_calc)
            ],
        states={
            '1': menu_handlers_list + [
                CallbackQueryHandler(calculator.enter_sum_to_calc, 
                                     pattern='^calculate_more$'),
                MessageHandler(Filters.text, calculator.get_sum)
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(Filters.all, callbacks.end_conversation)
            ]
        },
        fallbacks=[
            MessageHandler(Filters.all, callbacks.end_conversation)
        ],
        allow_reentry=True,
        conversation_timeout=timedelta(seconds=120)
        )

    button = get_button(session, 'btn_search')
    h_1 = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(f'^({button.text})$'), 
                           search.show_search)
            ],
        states={
            '1': menu_handlers_list + [
                MessageHandler(Filters.text, search.get_name)
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(Filters.all, callbacks.end_conversation)
            ]
        },
        fallbacks=[
            MessageHandler(Filters.all, callbacks.end_conversation)
        ],
        allow_reentry=True,
        conversation_timeout=timedelta(seconds=120)
        )

    h_2 = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(wallet.invest_start, pattern='^invest$')
            ],

        states={
            '1': menu_handlers_list + [
                MessageHandler(Filters.text, wallet.get_invest_sum)
            ]
        },
        fallbacks=[
            MessageHandler(Filters.all, callbacks.end_conversation)
        ]
        )

    button = get_button(session, 'btn_confirm')
    h_3 = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(wallet.withdraw_start, 
                                 pattern='^withdraw$')
            ],
    
        states={
            '1': menu_handlers_list + [
                MessageHandler(Filters.text, wallet.withdraw_get_sum)
            ],
            '2': menu_handlers_list + [
                MessageHandler(Filters.text, wallet.get_method)
            ],
            '3': menu_handlers_list + [
                MessageHandler(Filters.all, wallet.get_details)
            ],
            '4': menu_handlers_list + [
                MessageHandler(Filters.regex(f'^({button.text})$'), 
                               wallet.withdraw_request_accepted)
            ]
        },
        fallbacks=[]
        )

    btn_male_sex = get_button(session, 'btn_male_sex', account_emoji=True)
    btn_female_sex = get_button(session, 'btn_female_sex', account_emoji=True)
    h_4 = MessageHandler(
        Filters.regex(f'^({btn_male_sex.text}|{btn_female_sex.text})$'), 
        callbacks.get_sex
        )

    button = get_button(session, 'btn_top')
    h_6 = MessageHandler(Filters.regex(f'^({button.text})$'), 
                         top_investors.show_investors_top)

    h_7 = CallbackQueryHandler(top_investors.navigate_investors_top, 
                               pattern='^(top_inv_\d{1,5})$')

    h_8 = CallbackQueryHandler(top_partners.show_partners_top, 
                               pattern='top_partners')

    h_9 = CallbackQueryHandler(top_investors.show_investors_top, 
                               pattern='top_investors')

    h_10 = CallbackQueryHandler(top_partners.navigate_partners_top, 
                                pattern='^(top_part_\d{1,5})$')

    button = get_button(session, 'btn_partners')
    h_11 = MessageHandler(Filters.regex(f'^({button.text})$'), 
                          partners.show_partners)

    button = get_button(session, 'btn_account')
    h_12 = MessageHandler(
        Filters.regex(f'^({button.text.format(sex_emoji=settings.sex_emoji_male)}|{button.text.format(sex_emoji=settings.sex_emoji_female)})$'),
        show_account.show_account
        )

    h_13 = CallbackQueryHandler(show_account.partners_stat,
                                pattern='^partners$')

    h_14 = CallbackQueryHandler(show_account.show_a,
                                pattern='^a$')

    h_15 = CallbackQueryHandler(show_account.back_to_account, 
                                pattern='^back_to_account$')

    h_16 = CallbackQueryHandler(show_account.show_b,
                                pattern='^b$')

    h_17 = CallbackQueryHandler(show_account.show_b,
                                pattern='^renew_list$')

    h_18 = CallbackQueryHandler(show_account.show_c,
                                pattern='^c$')

    h_19 = CallbackQueryHandler(
        show_account.change_sex,
        pattern='^change_sex_(мужской|женский|МУЖСКОЙ|ЖЕНСКИЙ)$'
        )

    button = get_button(session, 'btn_wallet')
    h_20 = MessageHandler(Filters.regex(f'^({button.text})$'), 
                          wallet.show_wallet)

    h_21 = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(wallet.send_sum_start, pattern='other_sum'),
            CallbackQueryHandler(wallet.send_sum_start, pattern='^replenish$')
            ],
    
        states={
            '1': menu_handlers_list + [
                MessageHandler(Filters.text, wallet.get_sum)
            ]
        },
        fallbacks=[
            MessageHandler(Filters.all, callbacks.end_conversation)
        ]
        )

    h_23 = CallbackQueryHandler(search.show_search_partners, 
                                pattern='^partners_search_\d{1,15}$')

    h_24 = CallbackQueryHandler(search.back_to_account_search, 
                                pattern='^back_to_account_search_\d{1,15}$')

    h_25 = CallbackQueryHandler(wallet.collect_balance, 
                                pattern='^collect_(partner|accumulative)$')

    button = get_button(session, 'btn_cancel')
    h_26 = MessageHandler(Filters.regex(f'^({button.text})$'), 
                          wallet.wallet_cancel)

    button = get_button(session, 'btn_proceed')
    h_27 = CallbackQueryHandler(callbacks.get_user, 
                                pattern=f'^{button.callback_data}$')

    h_28 = CallbackQueryHandler(callbacks.proceed_check,
                                pattern='^proceed_check$')

    h_55 = CommandHandler('start', callbacks.start)
    h_56 = MessageHandler(Filters.regex('^/get_id$'), callbacks.get_my_id)
    h_57 = CommandHandler('invite', callbacks.invite)

    h_999 = MessageHandler(Filters.text, callbacks.end_conversation)

    loc = locals()

    session.close()
    return get_sorted_handlers_list(loc)
