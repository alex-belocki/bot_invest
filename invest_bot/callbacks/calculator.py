from sqlalchemy.orm import sessionmaker

from config import engine
from invest_bot.models import Settings
from invest_bot.utils import (check_if_subscribed, 
                              get_user_program, 
                              num_fmt, perc_fmt, send_text_msg)


def enter_sum_to_calc(update, context):
    query = update.callback_query
    if query:
        chat_id = query.from_user.id
    else:
        chat_id = update.message.from_user.id

    Session = sessionmaker(bind=engine)
    session = Session()

    result = check_if_subscribed(update, context, session)
    if not result:
        return

    if context.user_data.get('is_conv') and context.user_data.get('msg_id'):
        try:
            context.bot.delete_message(
                chat_id=chat_id,
                message_id=context.user_data.get('msg_id')
                )
        except Exception:
            pass

    send_text_msg(update, context,
                  slug='msg_calc',
                  session=session)

    context.user_data['is_conv'] = True
    return '1'


def get_sum(update, context):
    Session = sessionmaker(bind=engine)
    session = Session()

    text = update.message.text
    if not (text.isdigit() and int(text) > 0):
        send_text_msg(update, context,
                      slug='msg_calc_error',
                      session=session)
        return '1'

    sum = int(text)

    settings = session.query(Settings).filter_by(name='Настройки').first()
    if sum < settings.calc_min_amount:
        send_text_msg(update, context,
                      slug='msg_calc_sum_error',
                      session=session)
        return '1'

    elif sum > settings.calc_max_amount:
        send_text_msg(update, context,
                      slug='msg_calc_big_sum',
                      session=session)
        return '1'

    program = get_user_program(session, sum)

    one_day_profit = sum/100*program.percent
    one_month_profit = one_day_profit * 31
    one_year_profit = one_day_profit * 365

    kwargs = dict(sum=num_fmt(sum),
                  percent=perc_fmt(program.percent),
                  one_day_profit=num_fmt(one_day_profit),
                  one_month_profit=num_fmt(one_month_profit),
                  one_year_profit=num_fmt(one_year_profit))

    msg = send_text_msg(update, context,
                        slug='msg_calc_ok',
                        session=session,
                        **kwargs)
    context.user_data['msg_id'] = msg.message_id

    return '1'
