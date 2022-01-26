import ast
from datetime import datetime, timedelta
import logging
import os
import platform
import traceback

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import and_, func
from sqlalchemy.dialects.postgresql import DATE
from sqlalchemy.orm import sessionmaker
from telegram import (InlineKeyboardButton, 
                      InlineKeyboardMarkup, 
                      InputMediaDocument,
                      ParseMode)

from config import engine, STATIC_FILES_DIR, QIWI_SECRET_KEY
from invest_bot.messages import emoji_accumulative_balance
from invest_bot.models import (SendMessageCampaign, Settings, Stat, 
                               TopUp, Transaction, User, Withdraw)
from invest_bot.utils import (accrue_partnership_reward, 
                              get_user_program, num_fmt, 
                              send_text_msg)
from invest_bot.qiwi_api import get_payment_status


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level = logging.INFO,
    filename = 'log.log'
    )


if 'MANJARO' in platform.release():
    broker = 'redis://localhost:6379/0'
else:
    broker = f'redis://default:{os.environ.get("CELERY_PASSWORD")}@localhost:6379/0'

app = Celery('tasks', broker=broker)
app.conf.timezone = 'Europe/Moscow'


def check_program(session, user):
    '''
    Проставляет юзеру актуальную программу в 
    зависимости от суммы
    '''
    program = get_user_program(session, user.trade_balance)
    if program.id == user.program_id:
        return

    user.previous_program_id = user.program_id
    user.program_id = program.id
    user.program_registered_date = datetime.now()


def check_top_up_transaction(session):
    '''
    Проверяет или на эту сумму можно начислять 
    проценты (п.7 из ТЗ) 
    '''
    for top_up in session.query(TopUp).filter_by(include_in_perc_calc=False):
        future = top_up.time + timedelta(days=1)
        if datetime.now() > future:
            top_up.include_in_perc_calc = True


@app.task
def monitor():
    start_time = datetime.now()
    Session = sessionmaker(bind=engine)
    session = Session()

    check_top_up_transaction(session)

    for user in session.query(User):
        check_program(session, user)

    session.commit()
    session.close()

    end_time = datetime.now()
    logging.info(round((end_time - start_time).seconds))


@app.task
def accrual_of_passive_income():
    from invest_bot.mq_bot import mybot as tgbot

    Session = sessionmaker(bind=engine)
    session = Session()

    for user in session.query(User).filter(User.super_partner_id.isnot(None)):
        income = round(
            user.trade_balance / 100 * user.percent_to_calc, 2
            )
        user.accumulative_balance = round(user.accumulative_balance + income, 2)

        transaction = Transaction(sum=income,
                                  name='Daily accrual of profit',
                                  date=datetime.now(),
                                  status='done',
                                  user_id=user.user_id)
        session.add(transaction)

        try:
            send_text_msg(slug='msg_passive_income',
                          session=session,
                          emoji_accumulative_balance=emoji_accumulative_balance,
                          income=num_fmt(income),
                          chat_id=user.user_id,
                          bot=tgbot)
        except Exception:
            logging.info(str(traceback.format_exc()))
            # pass

    session.commit()
    session.close()


@app.task
def check_qiwi_payment():
    from invest_bot.mq_bot import mybot as tgbot

    Session = sessionmaker(bind=engine)
    session = Session()

    now = datetime.now()
    for top_up in session.query(TopUp).filter_by(status='wait'):
        # если не перешёл по ссылке, то через 15+ мин. ставим просрочку
        if now > top_up.time + timedelta(seconds=1000):
            top_up.status = 'EXPIRED_'
            continue

        result = get_payment_status(top_up.id, QIWI_SECRET_KEY)
        if not result:
            continue

        status, amount = result
        if status == 'PAID':
            top_up.user.trade_balance = round(
                top_up.user.trade_balance + float(amount),
                2)
            top_up.status = 'done'
            top_up.time = datetime.now()
            top_up.transaction.status = 'done'
            top_up.transaction.date = datetime.now()

            reward = accrue_partnership_reward(session, 
                                               top_up.user.super_partner, 
                                               float(amount))

            try:
                send_text_msg(slug='msg_wallet_replenish_notif_to_sp',
                              session=session,
                              chat_id=top_up.user.super_partner_id,
                              bot=tgbot,
                              partner_reward=int(reward),
                              partner_id=top_up.user_id,
                              sum=int(float(amount)))
            except Exception:
                logging.info(str(traceback.format_exc()))

            try:
                send_text_msg(slug='msg_replenish_success',
                              session=session,
                              chat_id=top_up.user_id,
                              bot=tgbot,
                              sum=int(float(amount)),
                              sex_emoji=top_up.user.sex_emoji)
            except Exception:
                logging.info(str(traceback.format_exc()))

        elif status in ['REJECTED', 'EXPIRED']:
            top_up.status = status
            top_up.transaction.status = status
            top_up.time = datetime.now()
            top_up.transaction.date = datetime.now()

    session.commit()
    session.close()


@app.task
def send_email_campaign(campaign_id):
    '''Рассылка из админки '''
    from invest_bot.mq_bot import mybot as tgbot

    Session = sessionmaker(bind=engine)
    session = Session()

    campaign = session\
        .query(SendMessageCampaign)\
        .filter_by(id=campaign_id)\
        .first()

    if campaign.send_to:
        user_ids = map(int, campaign.send_to.split())
        users = session.query(User).filter(User.user_id.in_(user_ids))
    else:
        users = session.query(User)

    keyboard = [[]]
    if campaign.button_text and campaign.button_url:
        keyboard = [
            [InlineKeyboardButton(campaign.button_text, 
                                  url=campaign.button_url)]
            ]

    files_list = ast.literal_eval(campaign.files)

    if not files_list:

        count = 0
        for user in users:
            try:
                tgbot.send_message(chat_id=user.user_id,
                                   text=campaign.text,
                                   reply_markup=InlineKeyboardMarkup(keyboard),
                                   disable_web_page_preview=campaign.preview,
                                   parse_mode=ParseMode.HTML)
                count += 1
            except Exception:
                logging.info(str(traceback.format_exc()))

    elif len(files_list) == 1:  # когда один файл
        file_id = ''
        path = os.path.join(STATIC_FILES_DIR, files_list[0])

        count = 0
        for user in users:
            try:
                msg = tgbot.send_document(chat_id=user.user_id,
                                          document=file_id or open(path, 'rb'),
                                          caption=campaign.text,
                                          reply_markup=InlineKeyboardMarkup(keyboard),
                                          parse_mode=ParseMode.HTML)
                file_id = msg.document.file_id
                count += 1
            except Exception:
                logging.info(str(traceback.format_exc()))

    elif len(files_list) > 1:  # когда несколько файлов
        path_list = [
            os.path.join(STATIC_FILES_DIR, file) for file in files_list]

        media_files = [
            InputMediaDocument(open(path, 'rb')) for path in path_list]

        media = []

        count = 0
        for user in users:
            try:
                tgbot.send_message(chat_id=user.user_id,
                                   text=campaign.text,
                                   parse_mode=ParseMode.HTML)
            except Exception:
                logging.info(str(traceback.format_exc()))

            try:
                msg_list = tgbot.send_media_group(chat_id=user.user_id,
                                                  media=media or media_files)
                media = [
                    InputMediaDocument(msg.document.file_id) for msg in msg_list
                    ]
                count += 1
            except Exception:
                logging.info(str(traceback.format_exc()))

    campaign.users_amount = count
    campaign.status = 'Завершена'

    session.commit()
    session.close()


@app.task
def update_stat():
    Session = sessionmaker(bind=engine)
    session = Session()

    date = (datetime.now() - timedelta(days=1)).date()

    stat = session.query(Stat).filter(
        func.cast(Stat.date, DATE) == date
        ).first()
    if stat:
        return

    new_users_count = session.query(func.count(User.user_id)).filter(
        func.cast(User.date_start, DATE) == date
        ).first()[0]

    male_count = session.query(func.count(User.user_id)).filter(
        and_(func.cast(User.date_ref, DATE) == date,
             User.sex == 'male')
        ).first()[0]

    female_count = session.query(func.count(User.user_id)).filter(
        and_(func.cast(User.date_ref, DATE) == date,
             User.sex == 'female')
        ).first()[0]

    top_up_count = session.query(func.count(TopUp.sum)).filter(
        func.cast(TopUp.time, DATE) == date
        ).first()[0]

    top_up_done = session.query(func.count(TopUp.sum)).filter(
        and_(func.cast(TopUp.time, DATE) == date,
             TopUp.status == 'done')
        ).first()[0]

    qiwi_sum = session.query(func.sum(TopUp.sum)).filter(
        and_(func.cast(TopUp.time, DATE) == date,
             TopUp.status == 'done')
        ).first()[0]

    withdraw_count = session.query(func.count(Withdraw.sum)).filter(
        func.cast(Withdraw.time, DATE) == date
        ).first()[0]

    withdraw_sum = session.query(func.sum(Withdraw.total_sum)).filter(
        func.cast(Withdraw.time, DATE) == date
        ).first()[0]

    withdraw_sum_done = session.query(func.sum(Withdraw.total_sum)).filter(
        and_(func.cast(Withdraw.time, DATE) == date,
             Withdraw.status == 'done')
        ).first()[0]

    wallet_sum = session.query(func.sum(User.wallet)).first()[0]

    trade_balance_sum = session.query(func.sum(User.trade_balance)).first()[0]

    accumulative_balance_sum = session\
        .query(func.sum(User.accumulative_balance))\
        .first()[0]

    partner_balance_sum = session.query(func.sum(User.partner_balance))\
        .first()[0]

    stat = Stat(date=date,
                new_users=new_users_count or 0,
                male=male_count or 0,
                female=female_count or 0,
                qiwi_bills_created=top_up_count or 0,
                qiwi_bills_paid=top_up_done or 0,
                qiwi_total_sum=qiwi_sum or 0,
                confirm_button=withdraw_count or 0,
                withdraws_wait=withdraw_sum or 0,
                withdraws_paid=withdraw_sum_done or 0,
                all_wallets_sum=wallet_sum or 0,
                all_trade_balance_sum=trade_balance_sum or 0,
                all_accumulative_balance_sum=accumulative_balance_sum or 0,
                all_partner_balance_sum=partner_balance_sum or 0)

    session.add(stat)
    session.commit()
    session.close()


@app.task
def send_withdraw_notif(withdraw_id):
    from invest_bot.mq_bot import mybot as tgbot

    Session = sessionmaker(bind=engine)
    session = Session()

    withdraw = session.query(Withdraw).filter_by(id=withdraw_id).first()

    kwargs = dict(full_sum=num_fmt(withdraw.total_sum),
                  comission=num_fmt(withdraw.comission),
                  sum=num_fmt(withdraw.sum),
                  method=withdraw.payment_method,
                  details=withdraw.details)

    send_text_msg(slug='msg_withdraw_final',
                  session=session,
                  chat_id=withdraw.user_id,
                  bot=tgbot,
                  sex_emoji=withdraw.user.sex_emoji,
                  **kwargs)

    withdraw.status = 'done'

    session.commit()
    session.close()


@app.task
def ban_member(user_id):
    from invest_bot.mq_bot import mybot as tgbot

    Session = sessionmaker(bind=engine)
    session = Session()

    settings = session.query(Settings).filter_by(name='Настройки').first()

    chat_list = [settings.chat_id, settings.channel_id]

    for chat_id in chat_list:
        try:
            tgbot.ban_chat_member(chat_id=chat_id,
                                  user_id=user_id)
        except Exception:
            pass


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):

    sender.add_periodic_task(30, monitor.s())
    sender.add_periodic_task(180, check_qiwi_payment.s())

    sender.add_periodic_task(
        crontab(hour=12, minute=00), 
        accrual_of_passive_income.s()
        )

    sender.add_periodic_task(
        crontab(hour=0, minute=1), 
        update_stat.s()
        )


    # sender.add_periodic_task(
    #     crontab(minute='*/1'), 
    #     get_1clancer_posts.s()
    #     )


# В маленьких проектах
# celery -A tasks worker -B --loglevel=INFO

# В больших проектах
# celery -A tasks beat

# Запуск celery worker server
# celery -A tasks worker --loglevel=INFO

