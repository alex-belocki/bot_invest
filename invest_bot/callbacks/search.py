import re

from sqlalchemy.orm import sessionmaker
from telegram.ext import ConversationHandler

from config import engine
from invest_bot.models import Message, User
from invest_bot.utils import (calc_account_data, 
                              calc_partners_data,  
                              check_if_subscribed,
                              send_text_msg)


def show_search(update, context):
    Session = sessionmaker(bind=engine)
    session = Session()

    result = check_if_subscribed(update, context, session)
    if not result:
        return

    send_text_msg(update, context,
                  slug='msg_search',
                  session=session)

    context.user_data['is_conv'] = True
    return '1'


def get_name(update, context):
    text = update.message.text
    search_user_id = None
    search_username = None

    # проверяем или айди
    result = re.search('^((ID:)?\s?\d{1,15})$', text)
    if result:
        search_user_id = result.group(0).replace('ID:', '').strip()

    # проверяем или юзернейм
    result = re.search('^((https://)?(t.me/)?[a-zA-Z0-9_-]{5,32})$', text)
    if result:
        search_username = result\
            .group(0)\
            .replace('https://', '')\
            .replace('t.me/', '')

    Session = sessionmaker(bind=engine)
    session = Session()

    if search_user_id:
        user = session\
            .query(User)\
            .filter_by(user_id=search_user_id)\
            .first()
    elif search_username:
        user = session\
            .query(User)\
            .filter_by(username=search_username)\
            .first()
    else:
        send_text_msg(update, context,
                      slug='msg_search_error',
                      session=session)
        return '1'

    if not user:
        send_text_msg(update, context,
                      slug='msg_search_failed',
                      session=session)
        return '1'

    kwargs = calc_account_data(user, session)

    msg = send_text_msg(update, context,
                        slug='msg_search_ok',
                        session=session,
                        search_user_id=user.user_id,
                        **kwargs)
    context.user_data['msg_id'] = msg.message_id

    context.user_data['is_conv'] = False
    return ConversationHandler.END


def show_search_partners(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    search_user_id = int(query.data.split('_')[-1])
    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=search_user_id).first()

    kwargs = calc_partners_data(user, session)

    message = session\
        .query(Message)\
        .filter_by(slug='msg_search_partners')\
        .first()

    text = message.text.format(**kwargs)

    context.bot.edit_message_text(chat_id=user_id,
                                  message_id=context.user_data['msg_id'],
                                  text=text,
                                  reply_markup=message.keyboard(
                                    search_user_id=search_user_id))


def back_to_account_search(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    search_user_id = int(query.data.split('_')[-1])

    Session = sessionmaker(bind=engine)
    session = Session()

    user = session.query(User).filter_by(user_id=search_user_id).first()

    kwargs = calc_account_data(user, session)

    message = session.query(Message).filter_by(slug='msg_search_ok').first()
    text = message.text.format(**kwargs)

    context.bot.edit_message_text(chat_id=user_id,
                                  message_id=context.user_data['msg_id'],
                                  text=text,
                                  reply_markup=message.keyboard(
                                    search_user_id=search_user_id))
