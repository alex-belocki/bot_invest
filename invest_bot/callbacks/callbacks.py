from datetime import datetime
import logging

from sqlalchemy.orm import sessionmaker
from telegram.ext import ConversationHandler

from config import engine
from invest_bot.models import Settings, User
from invest_bot.utils import (check_if_subscribed,
                              generate_refferal_link, 
                              send_text_msg)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level = logging.INFO,
    filename = 'log.log'
    )


def start(update, context):
    user_id = update.message.from_user.id
    first_name = update.message.from_user.first_name
    username = update.message.from_user.username

    super_partner_link = update.message.text.split()[-1]
    context.user_data['super_partner_link'] = super_partner_link

    Session = sessionmaker(bind=engine)
    session = Session()

    settings = session.query(Settings).filter_by(name='Настройки').first()

    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        user = User(user_id=user_id,
                    first_name=first_name,
                    username=username,
                    date_start=datetime.now(),
                    program_id=1,
                    program_registered_date=datetime.now(),
                    refferal_link=generate_refferal_link())
        session.add(user)
        session.commit()
    else:
        if user.super_partner_id:
            send_text_msg(update, context,
                          slug='msg_main_menu',
                          session=session,
                          sex_emoji=user.sex_emoji)
            return

    msg = send_text_msg(update,
                        context,
                        slug='msg_subscribe_to_proceed',
                        session=session,
                        chat_url=settings.chat_url,
                        channel_url=settings.channel_url)
    context.user_data['msg_id'] = msg.message_id

    if context.user_data.get('is_conv'):
        context.user_data['is_conv'] = False
        return ConversationHandler.END


def get_my_id(update, context):
    if update.channel_post:
        channel_id = update.channel_post.chat.id
        update.channel_post.reply_text(f'ID канала: {channel_id}')
        logging.info(f'ID канала: {channel_id}')

    elif update.message:
        user_id = update.message.from_user.id
        update.message.reply_text(f'Ваш user_id: {str(user_id)}')
        logging.info(f'User_id клиента: {str(user_id)}')
        chat_id = update.message.chat.id
        update.message.reply_text(f'Chat_id: {chat_id}')
        logging.info(f'Chat_id: {chat_id}')


def get_user(update, context):
    query = update.callback_query
    if query:
        chat_id = query.message.chat_id
    else:
        chat_id = update.message.chat_id

    Session = sessionmaker(bind=engine)
    session = Session()

    result = check_if_subscribed(update, context, session)
    if not result:
        return

    try:
        context.bot.delete_message(chat_id=chat_id,
                                   message_id=context.user_data['msg_id'])
    except Exception:
        pass

    # проверяем партнёрскую ссылку
    super_partner_link = context.user_data['super_partner_link']
    super_partner = session\
        .query(User)\
        .filter_by(refferal_link=super_partner_link)\
        .first()

    if not super_partner:
        send_text_msg(update, context,
                      slug='msg_invite_only',
                      session=session,
                      disable_web_page_preview=False)
        return

    settings = session.query(Settings).filter_by(name='Настройки').first()

    # Записываем в пользователя недостающие данные
    user = session.query(User).filter_by(user_id=chat_id).first()
    user.super_partner_id = super_partner.user_id
    super_partner.last_partner_registered = datetime.now()
    session.commit()

    send_text_msg(update, context,
                  slug='msg_enter_sex',
                  session=session,
                  sex_emoji_male=settings.sex_emoji_male,
                  sex_emoji_female=settings.sex_emoji_female)

    # оправляем уведомление супер-партнёру
    send_text_msg(context=context,
                  slug='msg_new_partner_notif_to_sp',
                  session=session,
                  chat_id=super_partner.user_id,
                  partner_id=chat_id)


def get_sex(update, context):
    user_id = update.message.from_user.id
    text = update.message.text
    Session = sessionmaker(bind=engine)
    session = Session()

    settings = session.query(Settings).filter_by(name='Настройки').first()
    user = session.query(User).filter_by(user_id=user_id).first()

    sex = 'male'
    if settings.sex_emoji_male in text:
        sex = 'male'
    elif settings.sex_emoji_female in text:
        sex = 'female'

    user.sex = sex
    user.date_ref = datetime.now()
    session.commit()

    send_text_msg(update, context,
                  slug='msg_welcome',
                  session=session,
                  sex_emoji=user.sex_emoji,
                  disable_web_page_preview=False)


def proceed_check(update, context):
    query = update.callback_query
    Session = sessionmaker(bind=engine)
    session = Session()

    result = check_if_subscribed(update, context, session)
    if not result:
        return

    try:
        context.bot.delete_message(chat_id=query.message.chat_id,
                                   message_id=context.user_data['msg_id'])
    except Exception:
        pass


def invite(update, context):
    '''Получить ссылку на регистрацию в боте '''
    Session = sessionmaker(bind=engine)
    session = Session()

    user = session\
        .query(User)\
        .filter_by(user_id=2)\
        .first()

    refferal_url = f'https://t.me/{context.bot.username}?'\
                   f'start={user.refferal_link}'
    update.message.reply_text(f'Ваша пригласительная ссылка: {refferal_url}')


def end_conversation(update, context):
    return ConversationHandler.END
