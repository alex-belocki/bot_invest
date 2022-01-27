from datetime import datetime, timedelta
import logging
import random

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import DATE
from telegram import ParseMode

from config import DEV_MODE, engine
from invest_bot.messages import (emoji_accumulative_balance,
                                 emoji_partner_balance,
                                 emoji_partners,
                                 emoji_trade_balance, 
                                 emoji_wallet, emoji_win)
from invest_bot.models import (Button, Message, Program, Settings, Token, 
                               TopUp, Transaction, User, Withdraw)
from invest_bot.sql_queries import (super_partners_count_query, 
                                    top_partners_list_query)


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.INFO,
    filename='log.log'
    )


def get_exp_date():
    future = datetime.now() + timedelta(seconds=910)
    return future.strftime('%Y-%m-%dT%H%M')


def get_button(session, slug, account_emoji=False):
    button = session.query(Button).filter_by(slug=slug).first()
    if account_emoji:
        settings = session.query(Settings).filter_by(name='Настройки').first()
        button.text = button.text.format(
            sex_emoji_male=settings.sex_emoji_male,
            sex_emoji_female=settings.sex_emoji_female
            )
    return button


def check_if_subscribed(update, context, session):
    query = update.callback_query
    if query:
        user_id = query.from_user.id
    else:
        user_id = update.message.from_user.id

    result = is_subscribed(user_id, context, session)
    if not result:
        if query:
            message = session\
                .query(Message)\
                .filter_by(slug='msg_subscribe_error')\
                .first()
            query.answer(message.text, show_alert=True)
        else:
            settings = session\
                .query(Settings)\
                .filter_by(name='Настройки')\
                .first()

            message = session\
                .query(Message)\
                .filter_by(slug='msg_subscribe_to_proceed')\
                .first()

            msg = send_text_msg(update, context,
                                slug='msg_check_if_subscribed',
                                session=session,
                                msg_subscribe_to_proceed=message.text,
                                chat_url=settings.chat_url,
                                channel_url=settings.channel_url)
            context.user_data['msg_id'] = msg.message_id

        return False

    return True


def send_text_msg(update=None, 
                  context=None, 
                  slug=None, 
                  session=None, 
                  chat_id=None,
                  bot=None,
                  disable_web_page_preview=True,
                  **kwargs):

    if update:
        query = update.callback_query
        if query:
            chat_id = query.message.chat_id
        else:
            chat_id = update.message.chat_id

    message = session.query(Message).filter_by(slug=slug).first()

    try:
        text = message\
            .text\
            .format(**kwargs)
    except Exception as ex:
        logging.info(f'Ошибка: {ex}')

    msg = None
    if context:
        msg = context.bot.send_message(
            chat_id=chat_id,
            text=text,
            disable_web_page_preview=disable_web_page_preview,
            reply_markup=message.keyboard(**kwargs),
            parse_mode=ParseMode.HTML
            )
    else:
        msg = bot.send_message(
            chat_id=chat_id,
            text=text,
            disable_web_page_preview=disable_web_page_preview,
            reply_markup=message.keyboard(**kwargs),
            parse_mode=ParseMode.HTML
            )

    return msg


def is_subscribed(user_id, context, session):
    '''Проверяет или подписан на чат и канал '''
    if DEV_MODE:
        return True

    settings = session.query(Settings).filter_by(name='Настройки').first()

    chat_id_list = [settings.chat_id, settings.channel_id]
    for chat_id in chat_id_list:
        member = context.bot.get_chat_member(chat_id=chat_id,
                                             user_id=user_id)

        if member.status not in ['administrator', 'creator', 'member']:
            return False

    return True


def num_fmt(num: float):
    fmt = '{:,}'.format(round(num, 2))\
        .replace(',', ' ')\
        .replace('.', ',')

    if fmt.endswith(',0'):
        fmt = fmt.replace(',0', '')
    return fmt


def perc_fmt(num: float):
    return str(num).replace('.', ',')


def generate_refferal_link():
    letter = 'qwertyuiopasdfghjklzxcvbnm'
    text = letter + letter.upper() + '0123456789'
    return ''.join(random.choices(text, k=10))


def get_top_investors_message_dict(session, user_id) -> dict:
    text = str()

    users_query = session\
        .query(User)\
        .order_by(desc(User.trade_balance), User.date_trade_balance_upd)\
        .limit(100)

    message_dict = dict()
    last_str = str()
    for count, user in enumerate(users_query, start=1):
        new_str_snipp = '\n'
        if count in [3, 10]:
            new_str_snipp += '\n'

        rate = str(count).zfill(2)
        user_balance = num_fmt(round(user.trade_balance))
        text += f'{rate}. {emoji_trade_balance} <b>{user_balance} ₽ '\
                f'{user.sex_emoji} ID:{user.user_id}</b>{new_str_snipp}'

        if user.user_id == user_id:
            last_str = f'{rate}. {emoji_trade_balance} <b>{user_balance} ₽ '\
                       f'{user.sex_emoji} ID:{user.user_id}</b>'

        if count <= 25:
            message_dict[1] = text.strip()
        elif 25 < count <= 50:
            message_dict[2] = text.strip()
        elif 50 < count <= 75:
            message_dict[3] = text.strip()
        elif 75 < count <= 100:
            message_dict[4] = text.strip()

        if count % 25 == 0:
            text = ''

    return message_dict, last_str, count


def get_top_partners_message_dict(session, user_id) -> dict:
    sp_count = session\
        .execute(super_partners_count_query)\
        .first()
    if sp_count:
        sp_count = sp_count[0]
    else:
        sp_count = 0  # число позиций в топе

    raw_query = top_partners_list_query.format(sp_count=sp_count)

    settings = session.query(Settings).filter_by(name='Настройки').first()

    text = str()
    message_dict = dict()
    last_str = str()
    for count, super_partner_id, partners_cnt, sex in \
            session.execute(raw_query):

        new_str_snipp = '\n'
        if count in [3, 10]:
            new_str_snipp += '\n'

        sex_emoji = settings.sex_emoji_male if sex == 'male' \
            else settings.sex_emoji_female

        rate = str(count).zfill(2)
        cnt = num_fmt(partners_cnt)
        text += f'{rate}. {emoji_partners} <b>{cnt} {sex_emoji} '\
                f'ID:{super_partner_id}</b>{new_str_snipp}'

        if super_partner_id == user_id:
            last_str = f'{rate}. {emoji_partners} <b>{cnt} {sex_emoji} '\
                       f'ID:{super_partner_id}</b>'

        if count <= 25:
            message_dict[1] = text.strip()
        elif 25 < count <= 50:
            message_dict[2] = text.strip()
        elif 50 < count <= 75:
            message_dict[3] = text.strip()
        elif 75 < count <= 100:
            message_dict[4] = text.strip()

        if count % 25 == 0:
            text = ''

    return message_dict, last_str, count


def calc_account_data(user, session):
    # Сумма, выплаченная за последний день
    date = datetime.now().date()
    last_day_sum = session.query(func.sum(Transaction.sum)).filter(
        and_(func.cast(Transaction.date, DATE) == date,
             Transaction.user_id == user.user_id,
             Transaction.name == 'Daily accrual of profit',
             Transaction.status == 'done')
        ).first()[0]
    if not last_day_sum:
        last_day_sum = 0

    # Сумма, выплаченная за последние 7 дней
    start_date = (datetime.now() - timedelta(days=7)).date()
    end_date = datetime.now().date()
    last_7_days_sum = session.query(func.sum(Transaction.sum)).filter(
        and_(func.cast(Transaction.date, DATE) >= start_date,
             func.cast(Transaction.date, DATE) <= end_date,
             Transaction.user_id == user.user_id,
             Transaction.name == 'Daily accrual of profit',
             Transaction.status == 'done')
        ).first()[0]
    if not last_7_days_sum:
        last_7_days_sum = 0

    # сумма, выплаченная за всё время
    all_sum = session.query(func.sum(Transaction.sum)).filter(
        and_(Transaction.user_id == user.user_id,
             Transaction.name == 'Daily accrual of profit',
             Transaction.status == 'done')
        ).first()[0]
    if not all_sum:
        all_sum = 0

    # сумма всех пополнений баланса
    all_top_up_sum = session.query(func.sum(TopUp.sum)).filter(
        and_(TopUp.status == 'done',
             TopUp.user_id == user.user_id)
        ).first()[0]
    if not all_top_up_sum:
        all_top_up_sum = 0

    # сумма всех выводов баланса
    all_withdraw_sum = session.query(func.sum(Withdraw.total_sum)).filter(
        Withdraw.user_id == user.user_id
        ).first()[0]
    if not all_withdraw_sum:
        all_withdraw_sum = 0

    join_date = user.date_ref.strftime('%d.%m.%Y')
    super_partner = f'ID:{user.super_partner_id}'

    kwargs = dict(sex_emoji=user.sex_emoji,
                  user_id=user.user_id,
                  percent=perc_fmt(user.program.percent),
                  wallet=num_fmt(user.wallet),
                  trade_balance=num_fmt(user.trade_balance),
                  rate_investors=num_fmt(user.rate_investors),
                  accumulative_balance=num_fmt(user.accumulative_balance),
                  partner_balance=num_fmt(user.partner_balance),
                  partners_cnt=num_fmt(user.rate_partners[-1]),
                  rate_partners=num_fmt(user.rate_partners[0]),
                  emoji_accumulative_balance=emoji_accumulative_balance,
                  emoji_partner_balance=emoji_partner_balance,
                  emoji_partners=emoji_partners,
                  emoji_trade_balance=emoji_trade_balance, 
                  emoji_wallet=emoji_wallet,
                  emoji_win=emoji_win,
                  last_day_sum=num_fmt(last_day_sum),
                  last_7_days_sum=num_fmt(last_7_days_sum),
                  all_sum=num_fmt(user.accumulative_balance_all),
                  all_top_up_sum=num_fmt(user.all_top_ups),
                  all_withdraw_sum=num_fmt(user.all_withdraws),
                  join_date=join_date,
                  super_partner=super_partner,
                  username=user.username or '')

    return kwargs


def calc_partners_data(user, session):
    # сумма, выплаченная на партнёрский баланс за последний день
    date = (datetime.now() - timedelta(days=1)).date()
    last_day_sum = session.query(func.sum(Transaction.sum)).filter(
        and_(func.cast(Transaction.date, DATE) == date,
             Transaction.name == 'Accrual of partner remuneration',
             Transaction.user_id == user.user_id,
             Transaction.status == 'done')
        ).first()[0]
    if not last_day_sum:
        last_day_sum = 0

    # сумма, выплаченная за последние 7 дней
    start_date = (datetime.now() - timedelta(days=8)).date()
    end_date = (datetime.now() - timedelta(days=1)).date()
    last_7_days_sum = session.query(func.sum(Transaction.sum)).filter(
        and_(func.cast(Transaction.date, DATE) >= start_date,
             func.cast(Transaction.date, DATE) <= end_date,
             Transaction.user_id == user.user_id,
             Transaction.name == 'Accrual of partner remuneration',
             Transaction.status == 'done')
        ).first()[0]
    if not last_7_days_sum:
        last_7_days_sum = 0

    if user.partners_list:
        text = ''
        for partner in user.partners_list:
            text += f'ID:{partner.user_id} '
    else:
        text = 'Партнёров пока нет 😕'

    kwargs = dict(partners_cnt=user.rate_partners[-1],
                  last_day_sum=num_fmt(last_day_sum),
                  last_7_days_sum=num_fmt(last_7_days_sum),
                  all_sum=num_fmt(user.partner_balance_all),
                  partners_snipp=text.strip())

    return kwargs


def get_user_program(session, sum):
    '''Возвращает программу в зависимости от суммы '''
    for program in session\
            .query(Program)\
            .order_by(Program.id):

        if round(sum) in range(program.start_range, 
                               program.end_range+1):

            return program
    return program


def accrue_partnership_reward(session, super_partner, amount, withdraw=False):
    '''Начисляет партнёрское вознаграждение '''
    settings = session.query(Settings).filter_by(name='Настройки').first()
    percent = settings.withdrawal_reff_perc if withdraw \
        else settings.topup_reff_perc

    reward = round(amount / 100 * percent, 2)
    super_partner.partner_balance = round(
        super_partner.partner_balance + reward, 2
        )
    tr = Transaction(name='Accrual of partner remuneration',
                     sum=reward,
                     date=datetime.now(),
                     status='done',
                     user_id=super_partner.user_id)
    session.add(tr)
    return reward


def get_token():
    Session = sessionmaker(bind=engine)
    session = Session()

    token = session\
        .query(Token)\
        .filter_by(name='Токены')\
        .first()
    session.close()
    return token.telegram_token
