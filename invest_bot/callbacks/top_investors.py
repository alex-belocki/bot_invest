from sqlalchemy.orm import sessionmaker
from telegram.ext import ConversationHandler

from config import engine
from invest_bot.kb import top_info_ikb
from invest_bot.models import Message
from invest_bot.utils import (check_if_subscribed,
                              get_top_investors_message_dict, 
                              send_text_msg)


def show_investors_top(update, context):
    query = update.callback_query
    if query:
        user_id = query.from_user.id
    else:
        user_id = update.message.from_user.id

    Session = sessionmaker(bind=engine)
    session = Session()

    result = check_if_subscribed(update, context, session)
    if not result:
        return

    investors_list, last_str, items_count \
        = get_top_investors_message_dict(session, user_id)

    # если переходит сюда из меню ТОП партнёров
    if context.user_data.get('from_partners'):
        message = session\
            .query(Message)\
            .filter_by(slug='msg_top_investors')\
            .first()
        text = message.text.format(investors_list=investors_list[1],
                                   user_rate=last_str)
        context.bot.edit_message_text(chat_id=user_id,
                                      message_id=context.user_data['msg_id'],
                                      text=text,
                                      reply_markup=top_info_ikb(items_count, 
                                                                investors=True))
        del context.user_data['from_partners']
    else:
        msg = send_text_msg(update, context,
                            slug='msg_top_investors',
                            session=session,
                            investors_list=investors_list[1],
                            user_rate=last_str,
                            reply_markup=top_info_ikb(items_count, 
                                                      investors=True))
        context.user_data['msg_id'] = msg.message_id

    if context.user_data.get('is_conv'):
        context.user_data['is_conv'] = False
        return ConversationHandler.END


def navigate_investors_top(update, context):
    '''Обрабатывает нажатие навигационного меню '''
    query = update.callback_query
    user_id = query.from_user.id
    screen_num = int(query.data.split('_')[-1])

    Session = sessionmaker(bind=engine)
    session = Session()

    investors_list, last_str, items_count \
        = get_top_investors_message_dict(session, user_id)

    message = session\
        .query(Message)\
        .filter_by(slug='msg_top_investors')\
        .first()

    text = message.text.format(investors_list=investors_list[screen_num],
                               user_rate=last_str)

    context.bot.edit_message_text(chat_id=query.message.chat_id,
                                  message_id=context.user_data['msg_id'],
                                  text=text,
                                  reply_markup=top_info_ikb(
                                    items_count, 
                                    investors=True, 
                                    screen_num=screen_num)
                                  )
