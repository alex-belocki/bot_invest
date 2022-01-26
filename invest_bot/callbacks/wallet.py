from datetime import datetime
import re

from sqlalchemy.orm import sessionmaker
from telegram.ext import ConversationHandler

from config import engine
from invest_bot.models import (Message, Settings, Token, 
                               TopUp, Transaction, User, Withdraw)
from invest_bot.qiwi_api import get_payment_url
from invest_bot.utils import (accrue_partnership_reward, 
                              check_if_subscribed,
                              get_button, num_fmt, 
                              send_text_msg)


def show_wallet(update, context):
    user_id = update.message.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    result = check_if_subscribed(update, context, session)
    if not result:
        return

    user = session.query(User).filter_by(user_id=user_id).first()
    kwargs = dict(wallet=num_fmt(user.wallet),
                  trade_balance=num_fmt(user.trade_balance),
                  percent=num_fmt(user.program.percent),
                  accumulative_balance=num_fmt(user.accumulative_balance),
                  partner_balance=num_fmt(user.partner_balance))

    msg = send_text_msg(update, context,
                        slug='msg_wallet',
                        session=session,
                        **kwargs)
    context.user_data['msg_id'] = msg.message_id

    if context.user_data.get('is_conv'):
        context.user_data['is_conv'] = False
        return ConversationHandler.END


def send_sum_start(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=user_id).first()

    if context.user_data.get('msg_id'):
        try:
            context.bot.delete_message(chat_id=user_id,
                                       message_id=context.user_data['msg_id'])
        except Exception:
            pass

    msg = send_text_msg(update, context,
                        slug='msg_replenish_send_sum',
                        session=session,
                        trade_balance=num_fmt(user.trade_balance))
    context.user_data['msg_id'] = msg.message_id
    context.user_data['is_conv'] = True
    return '1'


def get_sum(update, context):
    user_id = update.message.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    settings = session.query(Settings).filter_by(name='Настройки').first()
    user = session.query(User).filter_by(user_id=user_id).first()

    text = update.message.text
    if not (text.isdigit() and int(text) > 0):
        msg = send_text_msg(update, context,
                            slug='msg_replenish_format_error',
                            session=session,
                            trade_balance=num_fmt(user.trade_balance))
        context.user_data['msg_id'] = msg.message_id
        return '1'

    sum = int(text)

    if sum < settings.topup_min_amount:
        msg = send_text_msg(update, context,
                            slug='msg_replenish_sum_error',
                            session=session,
                            trade_balance=num_fmt(user.trade_balance))
        context.user_data['msg_id'] = msg.message_id
        return '1'

    top_up = TopUp(sum=sum,
                   time=datetime.now(),
                   user_id=user_id)
    session.add(top_up)
    session.flush()

    transaction = Transaction(name='Replenishment',
                              sum=sum,
                              date=datetime.now(),
                              top_up_id=top_up.id,
                              user_id=user_id)
    session.add(transaction)
    session.commit()

    token = session.query(Token).filter_by(name='Токены').first()

    payment_url = get_payment_url(top_up.id, sum, token.qiwi_comment, 
                                  token.qiwi_token, token.qiwi_code)

    msg = send_text_msg(update, context,
                        slug='msg_replenish_invoice_ready',
                        session=session,
                        sum=num_fmt(sum),
                        payment_url=payment_url)

    context.user_data['msg_id'] = msg.message_id
    context.user_data['is_conv'] = False
    return ConversationHandler.END


def collect_balance(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    balance_type = query.data.split('_')[-1]

    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=user_id).first()

    alert = session.query(Message)\
        .filter_by(slug='msg_alert_not_enough_money').first()

    acc_balance = 0
    partner_balance = 0
    if balance_type == 'accumulative':
        if user.accumulative_balance == 0:
            query.answer(alert.text, show_alert=True)
            return

        acc_balance = user.accumulative_balance
        user.accumulative_balance -= user.accumulative_balance
        user.wallet = round(user.wallet + acc_balance, 2)

    elif balance_type == 'partner':
        if user.partner_balance == 0:
            query.answer(alert.text, show_alert=True)
            return

        partner_balance = user.partner_balance
        user.partner_balance -= user.partner_balance
        user.wallet = round(user.wallet + partner_balance, 2)

    sum = acc_balance if balance_type == 'accumulative' else partner_balance
    tr = Transaction(name=f'Collect {balance_type} balance',
                     sum=sum,
                     date=datetime.now(),
                     status='done',
                     user_id=user_id)
    session.add(tr)
    session.commit()

    kwargs = dict(wallet=num_fmt(user.wallet),
                  trade_balance=num_fmt(user.trade_balance),
                  percent=num_fmt(user.program.percent),
                  accumulative_balance=num_fmt(user.accumulative_balance),
                  partner_balance=num_fmt(user.partner_balance))

    message = session.query(Message).filter_by(slug='msg_wallet').first()
    text = message.text.format(**kwargs)

    context.bot.edit_message_text(chat_id=user_id,
                                  message_id=context.user_data['msg_id'],
                                  text=text,
                                  reply_markup=message.keyboard())


def wallet_cancel(update, context):
    '''Если нажал Отменить '''
    user_id = update.message.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=user_id).first()

    # сообщение с главным меню
    send_text_msg(update, context,
                  slug='msg_action_canceled',
                  session=session,
                  sex_emoji=user.sex_emoji)

    kwargs = dict(wallet=num_fmt(user.wallet),
                  trade_balance=num_fmt(user.trade_balance),
                  percent=num_fmt(user.program.percent),
                  accumulative_balance=num_fmt(user.accumulative_balance),
                  partner_balance=num_fmt(user.partner_balance))

    msg = send_text_msg(update, context,
                        slug='msg_wallet',
                        session=session,
                        **kwargs)
    context.user_data['msg_id'] = msg.message_id

    if context.user_data.get('is_conv'):
        context.user_data['is_conv'] = False
        return ConversationHandler.END


def invest_start(update, context):
    query = update.callback_query
    user_id = query.from_user.id

    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=user_id).first()
    kwargs = dict(wallet=num_fmt(user.wallet),
                  trade_balance=num_fmt(user.trade_balance))

    context.bot.delete_message(chat_id=user_id,
                               message_id=context.user_data['msg_id'])

    send_text_msg(update, context,
                  slug='msg_invest',
                  session=session,
                  **kwargs)

    context.user_data['is_conv'] = True
    return '1'


def get_invest_sum(update, context):
    user_id = update.message.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=user_id).first()

    text = update.message.text
    if not (text.isdigit() and int(text) > 0):
        kwargs = dict(wallet=num_fmt(user.wallet),
                      trade_balance=num_fmt(user.trade_balance))

        msg = send_text_msg(update, context,
                            slug='msg_invest_format_error',
                            session=session,
                            **kwargs)
        context.user_data['msg_id'] = msg.message_id
        return '1'

    sum = int(text)

    if sum > user.wallet:
        msg = send_text_msg(update, context,
                            slug='msg_invest_balance_error',
                            session=session,
                            wallet=num_fmt(user.wallet))
        context.user_data['msg_id'] = msg.message_id
        return '1'

    user.wallet = round(user.wallet - sum, 2)
    user.trade_balance = round(user.trade_balance + sum, 2)

    tr = Transaction(name='Invest from wallet to trade_balance',
                     sum=sum,
                     date=datetime.now(),
                     status='done',
                     user_id=user_id)
    session.add(tr)
    session.commit()

    # сообщение с главным меню
    send_text_msg(update, context,
                  slug='msg_invest_success',
                  session=session,
                  sex_emoji=user.sex_emoji)

    kwargs = dict(wallet=num_fmt(user.wallet),
                  trade_balance=num_fmt(user.trade_balance),
                  percent=num_fmt(user.program.percent),
                  accumulative_balance=num_fmt(user.accumulative_balance),
                  partner_balance=num_fmt(user.partner_balance))

    msg = send_text_msg(update, context,
                        slug='msg_wallet',
                        session=session,
                        **kwargs)
    context.user_data['msg_id'] = msg.message_id

    context.user_data['is_conv'] = False
    return ConversationHandler.END


def withdraw_start(update, context):
    query = update.callback_query
    user_id = query.from_user.id

    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=user_id).first()

    context.bot.delete_message(chat_id=user_id,
                               message_id=context.user_data['msg_id'])

    msg = send_text_msg(update, context,
                        slug='msg_withdraw',
                        session=session,
                        wallet=num_fmt(user.wallet))
    context.user_data['msg_id'] = msg.message_id

    context.user_data['is_conv'] = True
    return '1'


def withdraw_get_sum(update, context):
    user_id = update.message.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=user_id).first()

    text = update.message.text
    if not (text.isdigit() and int(text) > 0):
        msg = send_text_msg(update, context,
                            slug='msg_withdraw_format_error',
                            session=session,
                            wallet=num_fmt(user.wallet))
        context.user_data['msg_id'] = msg.message_id
        return '1'

    full_sum = int(text)

    settings = session.query(Settings).filter_by(name='Настройки').first()

    if full_sum < settings.withdrawal_min_amount:
        msg = send_text_msg(update, context,
                            slug='msg_withdraw_not_enough_sum',
                            session=session,
                            wallet=num_fmt(user.wallet))
        context.user_data['msg_id'] = msg.message_id
        return '1'
    elif full_sum > user.wallet:
        msg = send_text_msg(update, context,
                            slug='msg_withdraw_big_sum',
                            session=session,
                            wallet=num_fmt(user.wallet))
        context.user_data['msg_id'] = msg.message_id
        return '1'

    comission = round(full_sum * 0.02 + 50)
    sum = round(full_sum * 0.98 - 50)

    context.user_data['full_sum'] = full_sum
    context.user_data['sum'] = sum
    context.user_data['comission'] = comission

    kwargs = dict(wallet=num_fmt(user.wallet),
                  full_sum=num_fmt(full_sum),
                  comission=num_fmt(comission),
                  sum=num_fmt(sum))

    send_text_msg(update, context,
                  slug='msg_withdraw_sum_ok',
                  session=session,
                  **kwargs)

    return '2'


def get_method(update, context):
    user_id = update.message.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=user_id).first()

    card_button = get_button(session, 'btn_card')
    qiwi_button = get_button(session, 'btn_qiwi')

    full_sum = context.user_data['full_sum']
    sum = context.user_data['sum']
    comission = context.user_data['comission']

    kwargs = dict(wallet=num_fmt(user.wallet),
                  full_sum=num_fmt(full_sum),
                  sum=num_fmt(sum),
                  comission=num_fmt(comission))

    text = update.message.text
    if text not in [card_button.text, qiwi_button.text]:
        send_text_msg(update, context,
                      slug='msg_withdraw_method_error',
                      session=session,
                      **kwargs)
        return '2'

    if text == card_button.text:  # если выбрал карту
        method = card_button.text
        context.user_data['method'] = method

        send_text_msg(update, context,
                      slug='msg_withdraw_card',
                      session=session,
                      **kwargs)
        return '3'
    elif text == qiwi_button.text:  # если выбрал киви
        method = qiwi_button.text
        context.user_data['method'] = method
        context.user_data['sum'] = full_sum
        context.user_data['comission'] = 0

        send_text_msg(update, context,
                      slug='msg_withdraw_qiwi',
                      session=session,
                      **kwargs)
        return '3'


def get_details(update, context):
    user_id = update.message.from_user.id
    text = update.message.text
    method = context.user_data['method']

    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=user_id).first()

    full_sum = context.user_data['full_sum']
    sum = context.user_data['sum']
    comission = context.user_data['comission']

    kwargs = dict(wallet=num_fmt(user.wallet),
                  full_sum=num_fmt(full_sum),
                  sum=num_fmt(sum),
                  comission=num_fmt(comission))

    card_button = get_button(session, 'btn_card')
    qiwi_button = get_button(session, 'btn_qiwi')

    if method == card_button.text:
        pattern = '^([0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4})$'
        result = re.search(pattern, text)
        if not result:
            send_text_msg(update, context,
                          slug='msg_withdraw_card_error',
                          session=session,
                          **kwargs)
            return '3'

    elif method == qiwi_button.text:
        pattern = '^(7\d{10})$'
        result = re.search(pattern, text)
        if not result:
            send_text_msg(update, context,
                          slug='msg_withdraw_qiwi_error',
                          session=session,
                          **kwargs)
            return '3'

    details = result.group(0)
    context.user_data['details'] = details

    kwargs.update(dict(method=method, details=details))

    send_text_msg(update, context,
                  slug='msg_withdraw_method_ok',
                  session=session,
                  **kwargs)
    return '4'


def withdraw_request_accepted(update, context):
    user_id = update.message.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    full_sum = context.user_data['full_sum']
    sum = context.user_data['sum']
    comission = context.user_data['comission']
    method = context.user_data['method']
    details = context.user_data['details']

    user = session.query(User).filter_by(user_id=user_id).first()
    user.wallet = round(user.wallet - full_sum, 2)

    kwargs = dict(full_sum=num_fmt(full_sum),
                  sum=num_fmt(sum),
                  comission=num_fmt(comission),
                  method=method,
                  details=details)

    msg = send_text_msg(update, context,
                        slug='msg_withdraw_request_accepted',
                        session=session,
                        sex_emoji=user.sex_emoji,
                        **kwargs)

    payment_method = 'QIWI' if 'QIWI' in method else 'CARD'
    withdraw = Withdraw(time=datetime.now(),
                        sum=sum,
                        comission=comission,
                        total_sum=full_sum,
                        payment_method=payment_method,
                        details=details,
                        final_tg_message_id=msg.message_id,
                        user_id=user_id)
    session.add(withdraw)
    session.flush()

    tr = Transaction(name='Withdrawal',
                     sum=full_sum,
                     date=datetime.now(),
                     withdraw_id=withdraw.id,
                     user_id=user_id)
    session.add(tr)

    reward = accrue_partnership_reward(session, 
                                       user.super_partner, 
                                       full_sum, 
                                       withdraw=True)

    try:
        send_text_msg(context=context,
                      slug='msg_wallet_withdraw_notif_to_sp',
                      session=session,
                      chat_id=user.super_partner_id,
                      partner_reward=num_fmt(reward),
                      partner_id=user_id,
                      full_sum=num_fmt(full_sum))
    except Exception:
        pass

    session.commit()

    context.user_data['is_conv'] = False
    return ConversationHandler.END


