import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "bfd-super-secret-key-2024-enterprise")
    DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

    # MongoDB
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB  = os.environ.get("MONGO_DB",  "BankingFraudDB")

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE      = False   # Set True when HTTPS
    SESSION_COOKIE_HTTPONLY    = True
    SESSION_COOKIE_SAMESITE    = "Lax"

    # Flask-Mail (Gmail SMTP)
    MAIL_SERVER        = "smtp.gmail.com"
    MAIL_PORT          = 587
    MAIL_USE_TLS       = True
    MAIL_USE_SSL       = False
    MAIL_USERNAME      = os.environ.get("MAIL_USERNAME", "bhavanimutagar7@gmail.com")
    MAIL_PASSWORD      = os.environ.get("MAIL_PASSWORD", "natqxjssmkwyfyxx")
    MAIL_DEFAULT_SENDER = ("BankGuard Security", os.environ.get("MAIL_USERNAME", "bhavanimutagar7@gmail.com"))

    # Model paths
    BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
    MODEL_DIR        = os.path.join(BASE_DIR, "training", "models")
    CLF_MODEL_PATH   = os.path.join(MODEL_DIR, "BestFraudClassificationModel.pkl")
    REG_MODEL_PATH   = os.path.join(MODEL_DIR, "BestRiskScorePredictionModel.pkl")
    PREPROCESSOR_PATH = os.path.join(MODEL_DIR, "FraudDetectionPreprocessor.pkl")
    METADATA_PATH    = os.path.join(MODEL_DIR, "model_metadata.json")

    # Banking
    DEFAULT_BALANCE       = 5000.0
    OTP_EXPIRY_MINUTES    = 5
    TXN_OTP_EXPIRY_SECONDS = 60
    HIGH_VALUE_TXN_LIMIT  = 100000.0
    MAX_FAILED_ATTEMPTS   = 5
    BASELINE_TXN_COUNT    = 3   # First N transactions skip fraud check

    # Admin
    ADMIN_EMAIL    = "bhavanimutagar7@gmail.com"
    ADMIN_PASSWORD = "Admin@123"

    # CSRF
    WTF_CSRF_ENABLED       = True
    WTF_CSRF_TIME_LIMIT    = 3600
