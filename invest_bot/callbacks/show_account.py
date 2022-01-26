from datetime import datetime, timedelta

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import sessionmaker
from telegram.ext import ConversationHandler

from config import engine
from invest_bot.messages import emoji_wallet
from invest_bot.models import Message, Settings, Transaction, User
from invest_bot.utils import (check_if_subscribed,
                              calc_account_data, 
                              calc_partners_data, 
                              num_fmt, send_text_msg)


def show_account(update, context):
    user_id = update.message.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    result = check_if_subscribed(update, context, session)
    if not result:
        return

    user = session.query(User).filter_by(user_id=user_id).first()

    kwargs = calc_account_data(user, session)

    msg = send_text_msg(update, context,
                        slug='msg_account',
                        session=session,
                        **kwargs)
    context.user_data['msg_id'] = msg.message_id

    if context.user_data.get('is_conv'):
        context.user_data['is_conv'] = False
        return ConversationHandler.END


def back_to_account(update, context):
    '''Когда нажал <<< Профиль '''
    query = update.callback_query
    user_id = query.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=user_id).first()

    kwargs = calc_account_data(user, session)

    message = session.query(Message).filter_by(slug='msg_account').first()
    text = message.text.format(**kwargs)

    context.bot.edit_message_text(chat_id=user_id,
                                  message_id=context.user_data['msg_id'],
                                  text=text,
                                  reply_markup=message.keyboard())


def partners_stat(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    user = session\
        .query(User)\
        .filter_by(user_id=user_id)\
        .first()

    kwargs = calc_partners_data(user, session)

    message = session\
        .query(Message)\
        .filter_by(slug='msg_account_partners')\
        .first()

    text = message.text.format(**kwargs)

    context.bot.edit_message_text(chat_id=user_id,
                                  message_id=context.user_data['msg_id'],
                                  text=text,
                                  reply_markup=message.keyboard())


def show_a(update, context):
    query = update.callback_query
    chat_id = query.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=chat_id).first()
    message = session.query(Message).filter_by(slug='msg_a').first()
    text = message.text.format(trade_balance=num_fmt(user.trade_balance),
                               percent=num_fmt(user.program.percent))

    context.bot.edit_message_text(chat_id=chat_id,
                                  message_id=context.user_data['msg_id'],
                                  text=text,
                                  reply_markup=message.keyboard())


def show_b(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    trans_query = session.query(Transaction).filter(
        or_(
            and_(Transaction.name == 'Replenishment',
                 Transaction.status == 'done'),
            Transaction.name == 'Withdrawal')
        ).order_by(desc(Transaction.date)).limit(5)

    trans_snipp = ''
    for tr in trans_query:
        name_snipp = '➕ ПОПОЛНЕНИЕ' if tr.name == 'Replenishment' \
            else '➖ ВЫПЛАТА'
        dt_str = tr.date.strftime('%H:%M:%S')
        sum = num_fmt(tr.sum)
        trans_snipp += f'{name_snipp} - {dt_str}\n'\
                       f'{emoji_wallet} {sum} ₽ - ID:{tr.user_id}\n\n'

    message = session.query(Message).filter_by(slug='msg_b').first()
    text = message.text.format(trans_snipp=trans_snipp)

    context.bot.edit_message_text(chat_id=user_id,
                                  message_id=context.user_data['msg_id'],
                                  text=text,
                                  reply_markup=message.keyboard())


def show_c(update, context):
    query = update.callback_query
    user_id = query.from_user.id

    Session = sessionmaker(bind=engine)
    session = Session()

    # всего пользователей, нажавших Мужской/Женский
    users_cnt = session.query(func.count(User.sex))\
        .filter(User.sex.in_(['male', 'female'])).first()[0]
    if not users_cnt:
        users_cnt = 0

    # за последние 24 часа кол-во нажавших М/Ж
    start_date = datetime.now() - timedelta(days=1)
    new_users_cnt = session.query(func.count(User.sex)).filter(
        and_(User.sex.in_(['male', 'female']),
             User.date_ref >= start_date)
        ).first()[0]
    if not new_users_cnt:
        new_users_cnt = 0

    settings = session.query(Settings).filter_by(name='Настройки').first()
    user = session.query(User).filter_by(user_id=user_id).first()
    sex = 'мужской'.upper() if user.sex == 'male' else 'женский'.upper()

    message = session.query(Message).filter_by(slug='msg_settings').first()
    text = message.text.format(users_cnt=users_cnt,
                               new_users_cnt=new_users_cnt)

    context.bot.edit_message_text(
        chat_id=user_id,
        message_id=context.user_data['msg_id'],
        text=text,
        reply_markup=message.keyboard(sex=sex,
                                      support_url=settings.support_url)
        )


def change_sex(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    old_sex = query.data.split('_')[-1]
    new_sex = 'female' if old_sex == 'мужской'.upper() else 'male'

    Session = sessionmaker(bind=engine)
    session = Session()

    settings = session.query(Settings).filter_by(name='Настройки').first()
    user = session.query(User).filter_by(user_id=user_id).first()
    user.sex = new_sex
    session.commit()

    sex = 'мужской'.upper() if user.sex == 'male' else 'женский'.upper()

    message = session.query(Message).filter_by(slug='msg_settings').first()
    context.bot.edit_message_reply_markup(
        chat_id=user_id,
        message_id=context.user_data['msg_id'],
        reply_markup=message.keyboard(sex=sex,
                                      support_url=settings.support_url)
        )

    send_text_msg(update, context,
                  slug='msg_tmp',
                  session=session,
                  sex_emoji=user.sex_emoji)

