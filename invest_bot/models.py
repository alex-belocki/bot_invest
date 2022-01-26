from datetime import datetime, timedelta

from sqlalchemy import (and_, BigInteger, Boolean, Column, Date, 
                        DateTime, ForeignKey, func,
                        Integer, Numeric, String, Table) 
from sqlalchemy.ext.declarative import declarative_base 
from sqlalchemy.orm import object_session, relationship
from telegram import (InlineKeyboardButton, 
                      InlineKeyboardMarkup, 
                      ReplyKeyboardMarkup)

from invest_bot.messages import sex_emoji_male, sex_emoji_female
from invest_bot.sql_queries import (raw_without_parnters_query,
                                    rate_partners_query,
                                    super_partners_count_query)

Base = declarative_base()


message_button = Table(
    "message_button",
    Base.metadata,
    Column("message_id", Integer, ForeignKey("messages.id")),
    Column("button_id", Integer, ForeignKey("buttons.id"))
)


class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    username = Column(String)
    date_start = Column(DateTime(), nullable=False)
    date_ref = Column(DateTime())

    # время регистрации последнего партнёра, по ссылке этого юзера
    last_partner_registered = Column(DateTime())
    sex = Column(String(6))  # male, female

    # отсюда выводятся ср-ва
    wallet = Column(Numeric(8, 2, asdecimal=False),
                    nullable=False,
                    default=0)

    # сюда приходят все пополнения баланса
    trade_balance = Column(Numeric(8, 2, asdecimal=False),
                           nullable=False,
                           default=0)

    # сюда приходят все % прибыли от торгового баланса
    accumulative_balance = Column(Numeric(8, 2, asdecimal=False),
                                  nullable=False,
                                  default=0)

    # сюда приходят все отчисления от партнёров
    partner_balance = Column(Numeric(8, 2, asdecimal=False),
                             nullable=False,
                             default=0)

    all_withdraws_custom = Column(Numeric(8, 2, asdecimal=False))
    all_top_ups_custom = Column(Numeric(8, 2, asdecimal=False))
    all_accumulative_balance_custom = Column(Numeric(8, 2, asdecimal=False))
    all_partner_balance_custom = Column(Numeric(8, 2, asdecimal=False))

    date_trade_balance_upd = Column(DateTime())
    program_registered_date = Column(DateTime())

    refferal_link = Column(String(10), nullable=False)
    program_id = Column(Integer, 
                        ForeignKey('programs.id'), 
                        nullable=False,
                        default=1)
    previous_program_id = Column(Integer, 
                                 ForeignKey('programs.id'))
    super_partner_id = Column(Integer, ForeignKey('users.user_id'))

    super_partner = relationship('User', 
                                 remote_side='User.user_id',
                                 backref='partners_list')
    program = relationship('Program', foreign_keys=[program_id])
    previous_program = relationship('Program', 
                                    foreign_keys=[previous_program_id])

    transactions_list = relationship('Transaction', 
                                     back_populates='user',
                                     cascade='all, delete')
    withdraws_list = relationship('Withdraw',
                                  back_populates='user',
                                  cascade='all, delete')
    top_ups_list = relationship('TopUp',
                                back_populates='user',
                                cascade='all, delete')

    @property
    def all_withdraws(self):
        if self.all_withdraws_custom:
            return self.all_withdraws_custom
        else:
            all_withdraws = object_session(self)\
                .query(func.sum(Withdraw.total_sum)).filter(
                    Withdraw.user_id == self.user_id
                ).first()[0]
            return all_withdraws or 0

    @property
    def all_top_ups(self):
        if self.all_top_ups_custom:
            return self.all_top_ups_custom
        else:
            all_top_ups = object_session(self)\
                .query(func.sum(TopUp.sum)).filter(
                and_(TopUp.status == 'done',
                     TopUp.user_id == self.user_id)
                ).first()[0]
            return all_top_ups or 0

    @property
    def accumulative_balance_all(self):
        if self.all_accumulative_balance_custom:
            return self.all_accumulative_balance_custom
        else:
            accumulative_balance_all = object_session(self)\
                .query(func.sum(Transaction.sum)).filter(
                    and_(Transaction.user_id == self.user_id,
                         Transaction.name == 'Daily accrual of profit',
                         Transaction.status == 'done')
                ).first()[0]
            return accumulative_balance_all or 0

    @property
    def partner_balance_all(self):
        if self.all_partner_balance_custom:
            return self.all_partner_balance_custom
        else:
            partner_balance_all = object_session(self)\
                .query(func.sum(Transaction.sum)).filter(
                    and_(Transaction.user_id == self.user_id,
                         Transaction.name == 'Accrual of partner remuneration',
                         Transaction.status == 'done')
                ).first()[0]
            return partner_balance_all or 0

    @property
    def percent_to_calc(self):
        '''
        Процент, который реально начисляется
        с учётом даты перехода на программу (п.8 из ТЗ)
        '''
        future = self.program_registered_date + timedelta(days=1)

        if datetime.now() < future:
            return self.previous_program.percent
        else:
            return self.program.percent

    @property
    def sex_emoji(self):
        settings = object_session(self)\
            .query(Settings)\
            .filter_by(name='Настройки')\
            .first()
        if self.sex == 'male':
            return settings.sex_emoji_male
        elif self.sex == 'female':
            return settings.sex_emoji_female

    @property
    def rate_investors(self):
        raw_sql = '''
            SELECT num_row
            FROM 
                (SELECT 
                    ROW_NUMBER() OVER(ORDER BY trade_balance DESC, date_trade_balance_upd) AS num_row,
                    user_id, 
                    first_name, 
                    trade_balance
                FROM 
                    users) AS tt
            WHERE user_id={}'''.format(self.user_id)
        rate = object_session(self).execute(raw_sql).first()
        if rate:
            return rate[0]

    @property
    def rate_partners(self) -> tuple:
        '''Возвращает кортеж (rate_p, partners_cnt) '''
        raw_sql = rate_partners_query.format(self.user_id)
        result = object_session(self).execute(raw_sql).first()

        if not result:
            sp_count = object_session(self)\
                .execute(super_partners_count_query)\
                .first()
            if sp_count:
                sp_count = sp_count[0]
            else:
                sp_count = 0  # число позиций в топе

            query = raw_without_parnters_query.format(user_id=self.user_id,
                                                      sp_count=sp_count)

            return object_session(self).execute(query).first()

        return result

    def __repr__(self):
        return f'<{self.user_id}-{self.first_name}>'


class Settings(Base):
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, default='Настройки')
    sex_emoji_male = Column(String, nullable=False, default=sex_emoji_male)
    sex_emoji_female = Column(String, nullable=False, default=sex_emoji_female)
    refferal_url = Column(String, nullable=False)
    support_url = Column(String, nullable=False)
    chat_url = Column(String, nullable=False)
    chat_id = Column(BigInteger)
    channel_url = Column(String, nullable=False)
    channel_id = Column(BigInteger)
    calc_min_amount = Column(Integer, nullable=False, default=1000)
    calc_max_amount = Column(Integer, nullable=False, default=1000000)
    withdrawal_min_amount = Column(Integer, nullable=False, default=1000)
    topup_min_amount = Column(Integer, nullable=False, default=1000)
    topup_reff_perc = Column(Integer, nullable=False, default=10)
    withdrawal_reff_perc = Column(Integer, nullable=False, default=5)

    def __repr__(self):
        return f'<{self.name}>'


class Program(Base):
    __tablename__ = 'programs'

    id = Column(Integer, primary_key=True)
    start_range = Column(Integer, nullable=False)
    end_range = Column(Integer)
    percent = Column(Numeric(2, 1, asdecimal=False),
                     nullable=False)

    def __repr__(self):
        return f'<{self.start_range}-{self.end_range} ({self.percent})>'


class Token(Base):
    __tablename__ = 'tokens'

    id = Column(Integer, primary_key=True)
    name = Column(String(6), nullable=False, default='Токены')
    telegram_token = Column(String, nullable=False)
    qiwi_token = Column(String, nullable=False)
    qiwi_comment = Column(String)
    qiwi_code = Column(String)


class SendMessageCampaign(Base):
    __tablename__ = 'send_message_campaign'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    send_to = Column(String)  # список user_id
    text = Column(String, nullable=False)
    preview = Column(Boolean, nullable=False, default=False)
    button_text = Column(String)
    button_url = Column(String)
    time = Column(DateTime(), nullable=False)
    users_amount = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default='Выполняется')
    files = Column(String)

    def __repr__(self):
        return f'<{self.name}>'


class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    slug = Column(String, nullable=False, unique=True)
    text = Column(String)
    image_path = Column(String)
    image_id = Column(String)  # telegram_id
    markup = Column(String)

    buttons_list = relationship('Button', 
                                back_populates='message',
                                secondary=message_button)

    def _get_keyboard_from_markup(self, 
                                  url_tuple=None, 
                                  inline=False, 
                                  payload=None,
                                  **kwargs):

        keyboard = list()
        rows_list = self.markup.format(**kwargs).split('\n')
        for row in rows_list:
            if row == '':
                continue
            id_list = row.split('|')
            new_id_list = list()
            for id in id_list:
                for button in self.buttons_list:
                    if int(id) == button.id:
                        if inline:
                            if url_tuple:
                                button_id, url = url_tuple
                                if button_id == button.id:
                                    ikb = InlineKeyboardButton(
                                        getattr(button, 'text'),
                                        url=url
                                        )
                                url_tuple = None
                            elif button.inline_url:
                                ikb = InlineKeyboardButton(
                                    getattr(button, 'text'),
                                    url=button.inline_url.format(**kwargs)
                                    )
                            elif button.callback_data:
                                ikb = InlineKeyboardButton(
                                    getattr(button, 'text').format(**kwargs),
                                    callback_data=button.callback_data\
                                    .format(payload=payload, **kwargs)
                                    )
                            new_id_list.append(ikb)
                        else:
                            new_id_list.append(
                                getattr(button, 'text').format(**kwargs)
                                )
                        break

            keyboard.append(new_id_list)

        return keyboard

    def keyboard(self,
                 payload: int = None,
                 url_tuple=None,
                 reply_markup=None,
                 **kwargs):

        # если передали кастомную клавиатуру
        if reply_markup:
            return reply_markup

        '''Из строки делаем разметку для ТГ '''
        inline = False
        if self.buttons_list:
            if self.buttons_list[0].type_ == 'inline':
                inline = True
        else:
            keyboard = [[]]
            return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        keyboard = self._get_keyboard_from_markup(inline=inline, **kwargs)

        if inline:
            return InlineKeyboardMarkup(keyboard)
        else: return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def __repr__(self):
        return f'<{self.slug}>'


class Button(Base):
    __tablename__ = 'buttons'

    id = Column(Integer, primary_key=True)
    slug = Column(String, nullable=False, unique=True)
    text = Column(String, nullable=False)
    type_ = Column(String(6), nullable=False, default='inline')
    callback_data = Column(String)
    inline_url = Column(String)
    func_name = Column(String)
    message_id = Column(Integer, ForeignKey('messages.id'))

    message = relationship('Message', 
                           back_populates='buttons_list', 
                           secondary=message_button)

    def __repr__(self):
        return f'[{self.id} - {self.text} ({self.type_})]'


class TopUp(Base):
    __tablename__ = 'top_up'

    id = Column(Integer, primary_key=True)
    sum = Column(Numeric(asdecimal=False), nullable=False)
    time = Column(DateTime(), nullable=False)
    url = Column(String, unique=True)
    status = Column(String(8), nullable=False, default='wait')

    # на эту сумму начислять проценты или нет
    include_in_perc_calc = Column(Boolean, nullable=False, default=False)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)

    user = relationship('User', back_populates='top_ups_list')
    transaction = relationship('Transaction', 
                               back_populates='top_up', 
                               uselist=False)


class Withdraw(Base):
    __tablename__ = 'withdraw'

    id = Column(Integer, primary_key=True)
    time = Column(DateTime(), nullable=False)
    sum = Column(Numeric(asdecimal=False), nullable=False)
    comission = Column(Numeric(4, 2, asdecimal=False), 
                       nullable=False, 
                       default=0)
    total_sum = Column(Numeric(asdecimal=False), nullable=False)
    payment_method = Column(String, nullable=False, default='QIWI')
    details = Column(String, nullable=False)
    is_paid = Column(Boolean, nullable=False, default=False)
    is_banned = Column(Boolean, nullable=False, default=False)
    status = Column(String(8), nullable=False, default='wait')
    final_tg_message_id = Column(Integer)  # чтобы можно было удалить из админки
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)

    user = relationship('User', back_populates='withdraws_list')


class Transaction(Base):
    __tablename__ = 'transaction'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sum = Column(Numeric(asdecimal=False))
    date = Column(DateTime(), nullable=False)
    status = Column(String, nullable=False, default='wait')
    top_up_id = Column(Integer, ForeignKey('top_up.id'))
    withdraw_id = Column(Integer, ForeignKey('withdraw.id'))
    user_id = Column(Integer, 
                     ForeignKey('users.user_id'), 
                     nullable=False)

    top_up = relationship('TopUp', back_populates='transaction')
    withdraw = relationship('Withdraw')
    user = relationship('User', back_populates='transactions_list')

# возможные статусы:
# Daily accrual of profit
# Accrual of partner remuneration  # Начисление партнерского вознаграждения
# Replenishment  # Пополнение
# Withdrawal  # Вывод
# Collect accumulative balance | Collect partner balance
# Invest from wallet to trade_balance


class Stat(Base):
    __tablename__ = 'stat'

    id = Column(Integer, primary_key=True)
    date = Column(Date(), nullable=False)
    new_users = Column(Integer, nullable=False, default=0)
    male = Column(Integer, nullable=False, default=0)
    female = Column(Integer, nullable=False, default=0)
    qiwi_bills_created = Column(Integer, nullable=False, default=0)
    qiwi_bills_paid = Column(Integer, nullable=False, default=0)
    qiwi_total_sum = Column(Numeric(asdecimal=False), nullable=False, default=0)
    confirm_button = Column(Integer, nullable=False, default=0)
    withdraws_wait = Column(Numeric(asdecimal=False), nullable=False, default=0)
    withdraws_paid = Column(Numeric(asdecimal=False), nullable=False, default=0)
    all_wallets_sum = Column(Numeric(asdecimal=False), 
                             nullable=False, 
                             default=0)
    all_trade_balance_sum = Column(Numeric(asdecimal=False), 
                                   nullable=False, 
                                   default=0)
    all_accumulative_balance_sum = Column(Numeric(asdecimal=False), 
                                          nullable=False, 
                                          default=0)
    all_partner_balance_sum = Column(Numeric(asdecimal=False), 
                                     nullable=False, 
                                     default=0)


