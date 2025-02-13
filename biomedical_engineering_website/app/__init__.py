from flask import Flask
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from .models import db  # Import db here, after it's initialized in models.py
from .models import User
from .models import *  # Import User model
from .routes import bp

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key_here'  # Replace with a strong, random key
    app.config['WTF_CSRF_ENABLED'] = True  # CSRF protection is enabled by default in Flask-WTF
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'mssql+pyodbc://DESKTOP-5E21SBF\\SQLEXPRESS/bmdb'
        '?driver=ODBC+Driver+17+for+SQL+Server'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions with the app
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    
    login_manager.login_view = "main.login"  # Ensure 'main' blueprint for login

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))  # Fetch the user by ID

    with app.app_context():
        db.create_all()  # Ensure tables are created in the SQL Server database

    from .routes import bp
    app.register_blueprint(bp)  # Register the 'main' blueprint

    return app
