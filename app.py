from flask import Flask, render_template, redirect, url_for, g
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from pymongo import MongoClient
from config import Config

# ──────────────────────────────────────────────
# Global extension singletons
# ──────────────────────────────────────────────
login_manager = LoginManager()
mail          = Mail()
csrf          = CSRFProtect()


def get_db():
    """Get the MongoDB database connection from app context."""
    from flask import current_app
    if 'db' not in g:
        try:
            client = MongoClient(current_app.config["MONGO_URI"], serverSelectionTimeoutMS=5000)
            g.db = client[current_app.config["MONGO_DB"]]
            # Test the connection
            client.admin.command('ping')
        except Exception as e:
            current_app.logger.error(f"✗ MongoDB connection failed: {e}")
            raise RuntimeError(f"Database connection failed: {e}")
    return g.db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── Flask-Login ────────────────────────────
    login_manager.init_app(app)
    login_manager.login_view              = "auth.login"
    login_manager.login_message           = "Please log in to access this page."
    login_manager.login_message_category  = "warning"

    # ── Flask-Mail ────────────────────────────
    mail.init_app(app)

    # ── CSRF ──────────────────────────────────
    csrf.init_app(app)

    # ── MongoDB ───────────────────────────────
    try:
        client = MongoClient(app.config["MONGO_URI"], serverSelectionTimeoutMS=5000)
        db = client[app.config["MONGO_DB"]]
        # Test the connection
        client.admin.command('ping')
        app.logger.info(f"✓ Connected to MongoDB: {app.config['MONGO_DB']}")
        _create_indexes(db)
    except Exception as e:
        app.logger.error(f"✗ MongoDB connection failed: {e}")
        raise

    # ── Blueprints ────────────────────────────
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

    # ── Root route ────────────────────────────
    @app.route("/")
    def index():
        return render_template("home.html")

    # ── Error handlers ────────────────────────
    @app.errorhandler(404)
    def page_not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("errors/500.html"), 500

    return app


def _create_indexes(database):
    try:
        database.users.create_index("email",          unique=True)
        database.users.create_index("account_number", unique=True)
        database.transactions.create_index("sender_id")
        database.transactions.create_index("timestamp")
        database.fraud_alerts.create_index("user_id")
        database.notifications.create_index("user_id")
        database.login_history.create_index("user_id")
    except Exception:
        pass   # indexes already exist


# ──────────────────────────────────────────────
# User loader for Flask-Login
# ──────────────────────────────────────────────
from flask_login import UserMixin
from bson import ObjectId


class User(UserMixin):
    """Thin wrapper around MongoDB user document for Flask-Login."""

    def __init__(self, user_doc):
        self._doc = user_doc

    def get_id(self):
        return str(self._doc["_id"])

    # Expose document fields as attributes
    def __getattr__(self, name):
        try:
            return self._doc[name]
        except KeyError:
            raise AttributeError(name)

    @property
    def is_admin(self):
        return self._doc.get("is_admin", False)

    @property
    def is_active(self):
        return self._doc.get("account_status", "Active") == "Active"


@login_manager.user_loader
def load_user(user_id):
    try:
        db = get_db()
        doc = db.users.find_one({"_id": ObjectId(user_id)})
        if doc:
            return User(doc)
        return None
    except RuntimeError:
        # Database not initialized
        return None


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
