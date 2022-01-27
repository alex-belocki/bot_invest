from datetime import datetime, timedelta
import random

from dotenv import load_dotenv

from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker

load_dotenv()

from config import engine
from invest_bot.models import Base, Program, Settings, User
from invest_bot.utils import generate_refferal_link

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

program_items = [
    (0, 0, 99),
    (3.5, 100, 9999),
    (4, 10000, 24999),
    (4.5, 25000, 49999),
    (5, 50000, 99999),
    (5.5, 100000, 249999),
    (6, 250000, 499999),
    (6.5, 500000, 999999),
    (7, 1000000, 9999999)
]

for percent, start_range, end_range in program_items:
    program = session.query(Program).filter(
        and_(Program.start_range == start_range,
             Program.end_range == end_range)
        ).first()
    if not program:
        program = Program(start_range=start_range,
                          end_range=end_range,
                          percent=percent)
        session.add(program)
    else:
        program.percent = percent

settings = session\
    .query(Settings)\
    .filter_by(name='Настройки')\
    .first()

if not settings:
    settings = Settings(refferal_url='https://some-url.com',
                        support_url='https://another-url.com',
                        chat_url='https://t.me/chat-url-to-subscribe',
                        chat_id=-123456789,
                        channel_url='https://t.me/channel-url-to-subscribe',
                        channel_id=-987654321)
    session.add(settings)


for user_id in range(4, 100):
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        seconds_amount = random.randint(60, 6000)
        date_start = datetime.now() - timedelta(seconds=seconds_amount)
        date_ref = date_start + timedelta(seconds=random.randint(60, 300))
        date_trade_balance_upd = date_ref + timedelta(seconds=seconds_amount)
        user = User(
            first_name=f'user-{user_id}',
            username=f'user-{user_id}',
            date_start=date_start,
            date_ref=date_ref,
            sex=random.choice(['male', 'female']),
            wallet=random.randint(1000, 50000),
            trade_balance=random.randint(1000, 50000),
            accumulative_balance=random.randint(1000, 50000),
            partner_balance=random.randint(1000, 50000),
            date_trade_balance_upd=date_trade_balance_upd,
            refferal_link=generate_refferal_link(),
            super_partner_id=529133148)
        session.add(user)

session.commit()
