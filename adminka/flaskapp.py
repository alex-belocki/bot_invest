import os
import sys
parent_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.dirname(parent_dir))

import logging

from dotenv import load_dotenv
from flask import Flask, render_template, request
from flask_admin import Admin
from flask_login import current_user, LoginManager

from admin_views import *
from db import db


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.INFO,
    filename='log.log'
    )

load_dotenv()

app = Flask(__name__)

app.config.from_pyfile('conf.py')
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin.login'

admin = Admin(
    template_mode='bootstrap3', 
    name='Админка', 
    index_view=MyHomeView()
    )
admin.init_app(app)
admin.add_view(UserView(User, db.session, name='Пользователи'))
admin.add_view(SettingsView(Settings, db.session, 'Настройки'))
admin.add_view(TokenView(Token, db.session, 'Токены'))
admin.add_view(CampaignView(SendMessageCampaign, db.session, name='Рассылка'))
admin.add_view(MessageView(Message, db.session, name='Тексты'))
admin.add_view(ButtonView(Button, db.session, name='Кнопки'))
admin.add_view(TopUpView(TopUp, db.session, name='Платежи'))
admin.add_view(WithdrawView(Withdraw, db.session, name='Выплаты'))
admin.add_view(TransactionView(Transaction, db.session))
admin.add_view(StatView(Stat, db.session, name='Статистика'))
admin.add_view(AdminView(AdminModel, db.session, name='Админ'))

admin.add_link(LoginMenuLink(name='Логин', category='', url='/admin/login'))
admin.add_link(LogoutMenuLink(name='Выход', category='', url='/admin/logout'))


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('admin.index'))
    return redirect(url_for('admin.login'))


@login_manager.user_loader
def load_user(user_id):
    return AdminModel.query.get(user_id)


if __name__ == '__main__':
    app.run(host='0.0.0.0')
