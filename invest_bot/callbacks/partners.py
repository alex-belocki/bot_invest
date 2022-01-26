from sqlalchemy.orm import sessionmaker
from telegram.ext import ConversationHandler

from config import engine
from invest_bot.models import Settings, User
from invest_bot.utils import check_if_subscribed, send_text_msg


def show_partners(update, context):
    user_id = update.message.from_user.id
    Session = sessionmaker(bind=engine)
    session = Session()

    result = check_if_subscribed(update, context, session)
    if not result:
        return

    user = session\
        .query(User)\
        .filter_by(user_id=user_id)\
        .first()
    refferal_url = f'https://t.me/{context.bot.username}?start={user.refferal_link}'

    settings = session.query(Settings).filter_by(name='Настройки').first()

    send_text_msg(update, context,
                  slug='msg_partners',
                  session=session,
                  refferal_url=refferal_url,
                  short_refferal_url=refferal_url.replace('https://', ''),
                  reff_url=settings.refferal_url,
                  disable_web_page_preview=False)

    if context.user_data.get('is_conv'):
        context.user_data['is_conv'] = False
        return ConversationHandler.END
