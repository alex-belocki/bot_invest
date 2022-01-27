from datetime import datetime, timedelta
import os
import platform
import sys

from flask import flash, redirect, url_for
from flask_admin import AdminIndexView, expose
from flask_admin.babel import gettext
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import ImageUploadField
from flask_admin.menu import MenuLink
from flask_login import current_user, login_user, logout_user
from wtforms import TextAreaField
from werkzeug.security import generate_password_hash
from sqlalchemy import and_, func
from sqlalchemy.dialects.postgresql import DATE

parent_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.dirname(parent_dir))

from adminka.forms import LoginForm, MultipleFileUploadField
from adminka.models import AdminModel
from adminka.utils import FilterPaidPayments
from invest_bot.models import *
from invest_bot.tasks import (ban_member, send_email_campaign, 
                              send_withdraw_notif)
from db import db
from config import DEV_MODE, STATIC_FILES_DIR


class MyHomeView(AdminIndexView):

    @expose('/')
    def index(self):
        if current_user.is_authenticated:
            return self.render('admin/index.html')
        else:
            return redirect(url_for('admin.login'))

    @expose('/login')
    def login(self):
        if current_user.is_authenticated:
            return redirect(url_for('admin.index'))

        title = 'Авторизация'
        login_form = LoginForm()
        return self.render('login.html', page_title=title, form=login_form)

    @expose('/process-login', methods=['POST'])
    def process_login(self):
        form = LoginForm()
        if form.validate_on_submit():
            user = AdminModel.query\
                .filter_by(username=form.username.data).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                flash('Вы вошли на сайт')
                return redirect(url_for('admin.index'))

        flash('Неправильное имя пользователя или пароль')
        return redirect(url_for('admin.login'))

    @expose('/logout')
    def logout(self):
        logout_user()
        flash('Вы успешно разлогинились')
        return redirect(url_for('admin.login'))

    def is_visible(self):
        return False


class UserView(ModelView):
    column_display_pk = True
    column_exclude_list = ('date_trade_balance_upd', 
                           'program', 'previous_program', 
                           'first_name', 'last_partner_registered',
                           'program_registered_date', 'all_withdraws_custom',
                           'all_top_ups_custom', 
                           'all_accumulative_balance_custom', 
                           'all_partner_balance_custom')

    form_excluded_columns = ('date_trade_balance_upd', 'partners_list',
                             'program', 'previous_program', 'first_name',
                             'transactions_list', 'withdraws_list',
                             'top_ups_list')

    column_searchable_list = ('user_id',)
    column_filters = ('super_partner_id', 'date_ref', 'sex')
    column_default_sort = ('date_start', True)
    column_labels = dict(user_id='ID',
                         username='username',
                         date_start='start',
                         date_ref='data',
                         super_partner_id='ID рефера',
                         sex='пол',
                         wallet='кошелёк',
                         trade_balance='торговый баланс',
                         accumulative_balance='накопительный баланс',
                         partner_balance='партнёрский баланс',
                         )

    def render(self, template, **kwargs):
        if template == 'admin/model/list.html':
            list_columns = [
                ('all_top_ups', '+ пополнено'),
                ('all_withdraws', '- выведено'),
                ('reff_count', 'кол-во рефералов'),
                ('partners_l', 'ID рефералов'),
                ('accumulative_balance_today', 'нак.бал.сегодня'),
                ('accumulative_balance_week', 'нак.бал.неделя'),
                ('accumulative_balance_all', 'нак.бал.всё время'),
                ('partner_balance_today', 'п.б. сегодня'),
                ('partner_balance_week', 'п.б.неделя'),
                ('partner_balance_all', 'п.б.всё время')
                ]

            for item in list_columns:
                if item not in kwargs['list_columns']:
                    kwargs['list_columns'].append(item)

            for model in kwargs['data']:
                reff_count = model.rate_partners[-1]
                model.reff_count = reff_count or 0

                # список айди партнёров
                partners_query = self.session.query(User.user_id).filter(
                    User.super_partner_id == model.user_id
                    )
                partners_list = [str(user_id[0]) for user_id in partners_query]
                model.partners_l = ' '.join(partners_list) or ''

                ACTION = 'Daily accrual of profit'

                # Сумма, выплаченная за сегодня
                date = datetime.now().date()
                accumulative_balance_today = self.session\
                    .query(func.sum(Transaction.sum)).filter(
                        and_(func.cast(Transaction.date, DATE) == date,
                             Transaction.user_id == model.user_id,
                             Transaction.name == ACTION,
                             Transaction.status == 'done')
                    ).first()[0]
                model.accumulative_balance_today = accumulative_balance_today or 0

                # Сумма, выплаченная за последние 7 дней
                start_date = (datetime.now() - timedelta(days=7)).date()
                end_date = datetime.now().date()
                accumulative_balance_week = self.session\
                    .query(func.sum(Transaction.sum)).filter(
                        and_(func.cast(Transaction.date, DATE) >= start_date,
                             func.cast(Transaction.date, DATE) <= end_date,
                             Transaction.user_id == model.user_id,
                             Transaction.name == ACTION,
                             Transaction.status == 'done')
                    ).first()[0]
                model.accumulative_balance_week = accumulative_balance_week or 0

                ACTION = 'Accrual of partner remuneration'

                # Сумма партнёрского баланса, выплаченная за сегодня
                date = datetime.now().date()
                partner_balance_today = self.session\
                    .query(func.sum(Transaction.sum)).filter(
                        and_(func.cast(Transaction.date, DATE) == date,
                             Transaction.user_id == model.user_id,
                             Transaction.name == ACTION,
                             Transaction.status == 'done')
                    ).first()[0]
                model.partner_balance_today = partner_balance_today or 0

                # Сумма партнёрского возн., выплаченная за последние 7 дней
                start_date = (datetime.now() - timedelta(days=7)).date()
                end_date = datetime.now().date()
                partner_balance_week = self.session\
                    .query(func.sum(Transaction.sum)).filter(
                        and_(func.cast(Transaction.date, DATE) >= start_date,
                             func.cast(Transaction.date, DATE) <= end_date,
                             Transaction.user_id == model.user_id,
                             Transaction.name == ACTION,
                             Transaction.status == 'done')
                    ).first()[0]
                model.partner_balance_week = partner_balance_week or 0

        return super(UserView, self).render(template, **kwargs)


class SettingsView(ModelView):
    can_delete = False
    can_create = False
    column_exclude_list = ('name', 'chat_id', 'chat_url',
                           'channel_url', 'channel_id')
    form_excluded_columns = ('name',)
    column_labels = dict(sex_emoji_male='Эмодзи мужской',
                         sex_emoji_female='Эмодзи женский',
                         refferal_url='РЕФЕРАЛКА',
                         support_url='ПОДДЕРЖКА',
                         chat_url='Ссылка на чат',
                         channel_url='Ссылка на канал',
                         calc_min_amount='Мин. сумма в Калькулятор',
                         calc_max_amount='Макс. сумма в Калькулятор',
                         withdrawal_min_amount='Мин. сумма вывода средств',
                         topup_min_amount='Мин. сумма пополнения баланса',
                         topup_reff_perc='Реф. % за пополнение',
                         withdrawal_reff_perc='Реф. % за вывод')


class TokenView(ModelView):
    can_delete = False
    can_create = False
    column_exclude_list = ('name',)
    form_excluded_columns = ('name',)
    column_labels = dict(telegram_token='Telegram Bot Token',
                         qiwi_token='Qiwi Token',
                         qiwi_comment='Qiwi комментарий',
                         qiwi_code='Qiwi код темы')

    def _qiwi_token_formatter(view, context, model, name):
        return f'{model.qiwi_token[:4]}********{model.qiwi_token[-4:]}'

    column_formatters = {
        'qiwi_token': _qiwi_token_formatter
    }


class CampaignView(ModelView):
    create_modal = True

    if not DEV_MODE:
        can_edit = False
        can_delete = False

    column_display_pk = True
    column_default_sort = ('time', True)
    column_list = ('id', 'name', 'users_amount', 'time', 'status')
    create_modal_template = 'admin/campaign/create-modal.html'

    column_labels = dict(name='Название',
                         users_amount='Кол-во пользователей',
                         time='Время',
                         status='Статус',
                         send_to='Кому',
                         text='Текст',
                         preview='Предпросмотр',
                         button_text='Текст кнопки',
                         button_url='Текст ссылки')

    form_excluded_columns = ('files_list', 'status', 
                             'users_amount', 'time')
    form_overrides = dict(text=TextAreaField,
                          files=MultipleFileUploadField)

    form_widget_args = dict(text=dict(rows=8))

    form_args = dict(files=dict(label='Файлы',
                                base_path=STATIC_FILES_DIR,
                                relative_path='files/'))

    def on_model_change(self, form, model, is_created):
        model.time = datetime.now()

    def after_model_change(self, form, model, is_created):
        send_email_campaign.delay(model.id)


class MessageView(ModelView):
    can_delete = False
    can_create = False

    form_overrides = dict(text=TextAreaField,
                          markup=TextAreaField)

    form_widget_args = dict(text=dict(rows=8),
                            markup=dict(rows=4))
    form_columns = ('slug', 'text', 'buttons_list', 'markup')
    column_exclude_list = ('image_id', 'image_path')
    column_searchable_list = ('slug', 'text')
    column_default_sort = ('id', True)

    column_labels = dict(text='Текст',
                         buttons_list='Кнопки',
                         markup='Разметка')

    def on_form_prefill(self, form, id, **kwargs):
        form.slug.render_kw = {'readonly': True}

    def is_accessible(self):
        return current_user.is_authenticated


class ButtonView(ModelView):
    can_delete = False
    can_create = False
    column_default_sort = ('id', True)
    column_exclude_list = ('callback_data',)
    form_excluded_columns = ('callback_data',)
    column_searchable_list = ('slug',)

    column_labels = dict(message='Сообщение',
                         text='Текст',
                         type_='Тип',
                         callback_data='Колбек данные',
                         inline_url='Инлайн ссылка')

    form_choices = dict(type_=[
        ('inline', 'inline'),
        ('reply', 'reply')
        ])

    def on_model_change(self, form, model, is_created):
        if model.text == '﻿➡﻿ Перейти на канал' or \
                model.text == '🆕﻿﻿Новостной канал':
            settings = db.session\
                .query(Settings)\
                .filter_by(name='Настройки')\
                .first()
            model.inline_url = settings.channel_url

    def on_form_prefill(self, form, id, **kwargs):
        form.slug.render_kw = {'readonly': True}

    def is_accessible(self):
        return current_user.is_authenticated


class TopUpView(ModelView):
    column_display_pk = True
    column_default_sort = ('time', True)
    column_exclude_list = ('include_in_perc_calc', 'url')
    form_excluded_columns = ('include_in_perc_calc', 'transaction', 'url')
    column_searchable_list = ('user_id',)

    column_filters = [
        FilterPaidPayments(
            TopUp.status, 'Статус платежа', options=(('done', 'Оплаченные'),)
        )
    ]


class WithdrawView(ModelView):
    column_default_sort = ('time', True)
    column_exclude_list = ('final_tg_message_id', 'status')
    column_editable_list = ('is_paid', 'is_banned')
    form_excluded_columns = ('final_tg_message_id', 'status')
    column_labels = dict(user_id='ID',
                         time='время',
                         sum='сумма',
                         comission='комиссия',
                         total_sum='итого',
                         payment_method='способ',
                         details='реквизиты',
                         is_paid='выплачено',
                         is_banned='БАН',
                         user='пользователь')

    def update_model(self, form, model):
        try:

            if form.is_paid:
                old_is_paid = model.is_paid
                new_is_paid = form.is_paid.data

            if form.is_banned:
                old_is_banned = model.is_banned
                new_is_banned = form.is_banned.data

            form.populate_obj(model)
            self._on_model_change(form, model, False)
            self.session.commit()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(gettext('Failed to update record. %(error)s', error=str(ex)), 'error')
            self.session.rollback()

            return False
        else:

            if form.is_paid:
                if new_is_paid != old_is_paid and new_is_paid is True:
                    send_withdraw_notif.delay(model.id)

            if form.is_banned:
                if new_is_banned != old_is_banned and new_is_banned is True:
                    ban_member.delay(model.user_id)

            self.after_model_change(form, model, False)

        return True


class TransactionView(ModelView):
    column_default_sort = ('date', True)
    column_filters = ('user_id', 'name')

    def is_visible(self):
        return False


class StatView(ModelView):
    can_edit = False
    can_delete = False
    can_create = False
    list_template = 'admin/stat/list.html'
    column_labels = dict(date='Дата',
                         new_users='Новых юзеров',
                         male='Муж.',
                         female='Жен.',
                         qiwi_bills_created='Сформировано счетов QIWI',
                         qiwi_bills_paid='Оплачено счетов QIWI',
                         qiwi_total_sum='Выручка по счетам QIWI',
                         confirm_button='Кнопка "Подтвердить"',
                         withdraws_wait='Сумма всех заявок на вывод',
                         withdraws_paid='Выплачено',
                         all_wallets_sum='Кошелёк',
                         all_trade_balance_sum='Торговый баланс',
                         all_accumulative_balance_sum='Накопительный баланс',
                         all_partner_balance_sum='Партнёрский баланс')

    def render(self, template, **kwargs):
        date = datetime.now().date()

        new_users_count = self.session.query(func.count(User.user_id)).filter(
            func.cast(User.date_start, DATE) == date
            ).first()[0]
        if not new_users_count:
            new_users_count = 0

        male_count = self.session.query(func.count(User.user_id)).filter(
            and_(func.cast(User.date_ref, DATE) == date,
                 User.sex == 'male')
            ).first()[0]
        if not male_count:
            male_count = 0

        female_count = self.session.query(func.count(User.user_id)).filter(
            and_(func.cast(User.date_ref, DATE) == date,
                 User.sex == 'female')
            ).first()[0]
        if not female_count:
            female_count = 0

        top_up_count = self.session.query(func.count(TopUp.sum)).filter(
            func.cast(TopUp.time, DATE) == date
            ).first()[0]
        if not top_up_count:
            top_up_count = 0

        top_up_done = self.session.query(func.count(TopUp.sum)).filter(
            and_(func.cast(TopUp.time, DATE) == date,
                 TopUp.status == 'done')
            ).first()[0]
        if not top_up_done:
            top_up_done = 0

        qiwi_sum = self.session.query(func.sum(TopUp.sum)).filter(
            and_(func.cast(TopUp.time, DATE) == date,
                 TopUp.status == 'done')
            ).first()[0]
        if not qiwi_sum:
            qiwi_sum = 0

        withdraw_count = self.session.query(func.count(Withdraw.sum)).filter(
            func.cast(Withdraw.time, DATE) == date
            ).first()[0]
        if not withdraw_count:
            withdraw_count = 0

        withdraw_sum = self.session.query(func.sum(Withdraw.total_sum)).filter(
            func.cast(Withdraw.time, DATE) == date
            ).first()[0]
        if not withdraw_sum:
            withdraw_sum = 0

        withdraw_sum_done = self.session.query(func.sum(Withdraw.total_sum))\
            .filter(
            and_(func.cast(Withdraw.time, DATE) == date,
                 Withdraw.status == 'done')
            ).first()[0]
        if not withdraw_sum_done:
            withdraw_sum_done = 0

        wallet_sum = self.session.query(func.sum(User.wallet)).first()[0]
        if not wallet_sum:
            wallet_sum = 0

        trade_balance_sum = self.session.query(func.sum(User.trade_balance))\
            .first()[0]
        if not trade_balance_sum:
            trade_balance_sum = 0

        accumulative_balance_sum = self.session\
            .query(func.sum(User.accumulative_balance))\
            .first()[0]
        if not accumulative_balance_sum:
            accumulative_balance_sum = 0

        partner_balance_sum = self.session\
            .query(func.sum(User.partner_balance))\
            .first()[0]
        if not partner_balance_sum:
            partner_balance_sum = 0

        rows_list = [
            (stat.date, stat.new_users, stat.male, stat.female,
             stat.qiwi_bills_created, stat.qiwi_bills_paid,
             stat.qiwi_total_sum, stat.confirm_button, 
             stat.withdraws_wait, stat.withdraws_paid,
             stat.all_wallets_sum, stat.all_trade_balance_sum,
             stat.all_accumulative_balance_sum,
             stat.all_partner_balance_sum) for stat in kwargs['data']
            ]

        live_row = (date, new_users_count, male_count, 
                    female_count, top_up_count, top_up_done,
                    qiwi_sum, withdraw_count, withdraw_sum,
                    withdraw_sum_done, wallet_sum, trade_balance_sum,
                    accumulative_balance_sum, partner_balance_sum)

        rows_list.insert(0, live_row)

        total_row = [
            sum(col_list) for col_list in zip(*rows_list) if \
            isinstance(col_list[0], (int, float))
            ] 

        total_row.insert(0, 'ВСЕГО')
        kwargs['live_row'] = live_row
        kwargs['total_row'] = total_row
        return super(StatView, self).render(template, **kwargs)


class AdminView(ModelView):
    can_delete = False
    can_create = False
    can_edit = True
    column_exclude_list = ('password')

    def on_model_change(self, form, model, is_created):
        model.password = generate_password_hash(
            model.password, method='sha256')

    def is_accessible(self):
        return current_user.is_authenticated


class LoginMenuLink(MenuLink):

    def is_accessible(self):
        return not current_user.is_authenticated


class LogoutMenuLink(MenuLink):
    def is_accessible(self):
        return current_user.is_authenticated
