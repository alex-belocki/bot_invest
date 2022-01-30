# bot_invest
🏆 MILLIONER GAME — tool for making money. Users invite other users and receive affiliate rewards from all their deposits and withdrawals

Stack:

- sqlalchemy
- celery
- redis
- python-telegram-bot
- flask-admin

## Installation
1. Clone repository:
```
git clone git@github.com:alex-belocki/bot_invest.git
```
2. Set up a virtual environment for the admin panel:
```
cd bot_invest/adminka/
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt 
```
3. Launch admin panel: 
```
flask run
```
4. Create a virtual environment for the bot. At the root of the `bot_invest/` directory, run:
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt 
```
5. Launch bot: 
```
python bot_invest.py
```

## Some features

- To get access to the main functionality of the bot, you need to go to it using the referral link. To get it, enter the command `/invite`, click on the invite link and then press START again.

- Distribution and withdrawal approval only work when Celery is running.
