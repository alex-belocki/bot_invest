import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

WEBHOOK = False

curr_dir_path = os.path.abspath(os.path.dirname(__file__))
STATIC_FILES_DIR = os.path.join(curr_dir_path, 'adminka', 'static')

DEV_MODE = True

if DEV_MODE:
    DOMAIN_NAME = 'http://127.0.0.1:5000'
else:
    DOMAIN_NAME = 'https://ya.ru'

DB_URL = 'postgresql+psycopg2://{user}:{pw}@{url}/{db}'\
    .format(user=os.environ['POSTGRES_USER'],
            pw=os.environ['POSTGRES_PW'],
            url=os.environ['POSTGRES_URL'],
            db=os.environ['POSTGRES_DB'])
engine = create_engine(DB_URL, pool_size=10, max_overflow=20)
