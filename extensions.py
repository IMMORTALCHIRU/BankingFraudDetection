from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from pymongo import MongoClient
from config import Config

# Extensions
login_manager = LoginManager()
mail          = Mail()
csrf          = CSRFProtect()
mongo_client  = None
db            = None

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Init extensions
    login_manager.init_app(app)
    login_manager.login_view        = "auth.login"
    login_manager.login_message     = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    mail.init_app(app)
    csrf.init_app(app)

    # MongoDB
    global mongo_client, db
    mongo_client = MongoClient(app.config["MONGO_URI"])
    db           = mongo_client[app.config["MONGO_DB"]]

    # Ensure indexes
    _create_indexes(db)

    # Register blueprints
    from routes.auth         import auth_bp
    from routes.dashboard    import dashboard_bp
    from routes.transactions import transactions_bp
    from routes.admin        import admin_bp
    from routes.complaints   import complaints_bp
    from routes.profile      import profile_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(profile_bp)

    return app


def _create_indexes(database):
    database.users.create_index("email",          unique=True)
    database.users.create_index("account_number", unique=True)
    database.transactions.create_index("sender_id")
    database.transactions.create_index("timestamp")
    database.otp_verifications.create_index("email")
    database.otp_verifications.create_index("expires_at", expireAfterSeconds=0)
    database.fraud_alerts.create_index("user_id")
    database.notifications.create_index("user_id")
    database.login_history.create_index("user_id")


def get_db():
    return db
