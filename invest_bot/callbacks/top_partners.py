from sqlalchemy.orm import sessionmaker

from config import engine
from invest_bot.kb import top_info_ikb
from invest_bot.models import Message
from invest_bot.utils import get_top_partners_message_dict


def show_partners_top(update, context):
    query = update.callback_query
    if query:
        user_id = query.from_user.id
    else:
        user_id = update.message.from_user.id

    Session = sessionmaker(bind=engine)
    session = Session()

    partners_list, last_str, items_count \
        = get_top_partners_message_dict(session, user_id)

    message = session\
        .query(Message)\
        .filter_by(slug='msg_top_partners')\
        .first()

    text = message.text.format(partners_list=partners_list[1],
                               user_rate=last_str)

    context.bot.edit_message_text(chat_id=user_id,
                                  message_id=context.user_data['msg_id'],
                                  text=text,
                                  reply_markup=top_info_ikb(
                                    items_count, partners=True))

    context.user_data['from_partners'] = True


def navigate_partners_top(update, context):
    '''Обрабатывает нажатие навигационного меню '''
    query = update.callback_query
    user_id = query.from_user.id
    screen_num = int(query.data.split('_')[-1])

    Session = sessionmaker(bind=engine)
    session = Session()

    partners_list, last_str, items_count \
        = get_top_partners_message_dict(session, user_id)

    message = session\
        .query(Message)\
        .filter_by(slug='msg_top_partners')\
        .first()

    text = message.text.format(partners_list=partners_list[screen_num],
                               user_rate=last_str)

    context.bot.edit_message_text(chat_id=query.message.chat_id,
                                  message_id=context.user_data['msg_id'],
                                  text=text,
                                  reply_markup=top_info_ikb(
                                    items_count,
                                    partners=True, 
                                    screen_num=screen_num)
                                  )
