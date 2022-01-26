from getpass import getpass

from werkzeug.security import generate_password_hash

from flaskapp import app, db, AdminModel


db.create_all(app=app)

password = getpass('Введите пароль админа: ')
password = generate_password_hash(password, method='sha256')

with app.app_context():
    admin = AdminModel.query.filter_by(username='admin').first()
    if not admin:
        admin = AdminModel(username='admin',
                           password=password)
        db.session.add(admin)

    db.session.commit()
