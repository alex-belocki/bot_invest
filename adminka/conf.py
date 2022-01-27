import os

from config import DEV_MODE


SECRET_KEY = 'dfkFFSd112df$$&jfd#@'

SQLALCHEMY_TRACK_MODIFICATIONS = False

if DEV_MODE:
    base_path = os.path.abspath(os.path.join(__file__, '../..', 'base.db'))
    DB_URL = f'sqlite:///{base_path}'
else:
    def get_env_variable(name):
        try:
            return os.environ[name]
        except KeyError:
            message = "Expected environment variable '{}' not set.".format(name)
            raise Exception(message)

    DB_URL = 'postgresql+psycopg2://{user}:{pw}@{url}/{db}'\
        .format(user=os.environ['POSTGRES_USER'],
                pw=os.environ['POSTGRES_PW'],
                url=os.environ['POSTGRES_URL'],
                db=os.environ['POSTGRES_DB'])

SQLALCHEMY_DATABASE_URI = DB_URL
