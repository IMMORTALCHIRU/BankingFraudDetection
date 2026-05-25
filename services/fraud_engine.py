"""Fraud Detection Engine — wraps the trained ML models for live inference."""

import os
import json
import pickle
import joblib
import numpy as np
import pandas as pd
from datetime import datetime

from config import Config

# ──────────────────────────────────────────────
# Preprocessor class for unpickling
# ──────────────────────────────────────────────
class FraudDetectionPreprocessor:
    """Holds all preprocessing components (encoders, scaler, etc.)."""
    def __init__(self):
        self.encoders = {}
        self.scaler = None
        self.fraud_label_encoder = None


# ──────────────────────────────────────────────
# Module-level singletons (loaded once)
# ──────────────────────────────────────────────
_clf_model   = None
_reg_model   = None
_preprocessor = None
_metadata    = None
_time_classes = None   # sorted list of all "HH:MM" strings seen in training

FEATURE_COLS = [
    "transaction_time",
    "transaction_amount",
    "avg_transaction_30d",
    "transaction_frequency_10min",
    "current_location",
    "previous_location",
    "account_balance",
    "transaction_type",
    "account_age_days",
    "failed_login_attempts",
    "login_hour",
    "transactions_today",
]

CITIES = [
    "Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Chennai",
    "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow",
    "Kochi", "Surat", "Patna", "Noida", "Chandigarh",
    "Hubballi", "Belagavi", "Vijayapura", "Dharwad", "Mysuru",
    "Udupi", "Manipal", "Shimoga", "Karwar", "Gulbarga",
    "Raichur", "Bellary", "Bidar", "Bagalkot", "Hassan", "Chitradurga",
]

TRANSACTION_TYPES = ["Transfer", "Withdrawal", "Deposit"]


def load_models():
    """Load (or reload) all persisted artefacts."""
    global _clf_model, _reg_model, _preprocessor, _metadata, _time_classes

    _clf_model    = joblib.load(Config.CLF_MODEL_PATH)
    _reg_model    = joblib.load(Config.REG_MODEL_PATH)
    
    # Load preprocessor, handling the class reference from training notebook
    try:
        _preprocessor = joblib.load(Config.PREPROCESSOR_PATH)
    except AttributeError as e:
        # If the class can't be found, temporarily add it to __main__
        import sys
        import __main__
        __main__.FraudDetectionPreprocessor = FraudDetectionPreprocessor
        try:
            _preprocessor = joblib.load(Config.PREPROCESSOR_PATH)
        finally:
            # Clean up
            if hasattr(__main__, 'FraudDetectionPreprocessor'):
                delattr(__main__, 'FraudDetectionPreprocessor')

    with open(Config.METADATA_PATH) as f:
        _metadata = json.load(f)

    # Build sorted time classes from the transaction_time encoder
    _time_classes = sorted(_preprocessor.encoders["transaction_time"].classes_)

    return True


def _safe_time_encode(time_str: str) -> int:
    """Encode a 'HH:MM' string, falling back to nearest known value."""
    enc = _preprocessor.encoders["transaction_time"]
    classes = list(enc.classes_)
    if time_str in classes:
        return int(enc.transform([time_str])[0])
    # Find nearest time by numeric minute value
    try:
        h, m = map(int, time_str.split(":"))
        target_min = h * 60 + m
        best = min(classes, key=lambda t: abs(int(t.split(":")[0]) * 60 + int(t.split(":")[1]) - target_min))
        return int(enc.transform([best])[0])
    except Exception:
        return int(enc.transform([classes[0]])[0])   # absolute fallback


def _safe_cat_encode(col: str, value: str) -> int:
    """Encode a categorical value safely, defaulting to index 0 on unknown."""
    enc = _preprocessor.encoders[col]
    classes = list(enc.classes_)
    if value in classes:
        return int(enc.transform([value])[0])
    return 0   # default for unseen city / type


def predict_transaction(transaction_data: dict) -> dict:
    """
    Run fraud classification + risk-score regression.

    Parameters
    ----------
    transaction_data : dict with keys matching FEATURE_COLS
        (risk_score may be omitted — it is a regression target, not an input)

    Returns
    -------
    dict:
        fraud_prediction   : "Fraud" | "Normal"
        fraud_probability  : float (0-1)
        confidence         : float (%)
        predicted_risk_score : float
        is_suspicious      : bool
        risk_level         : "Low" | "Medium" | "High" | "Critical"
    """
    global _clf_model, _reg_model, _preprocessor

    if _clf_model is None:
        load_models()

    try:
        # ── Build a properly ordered feature row ──
        row = {}

        # Categorical features (safe encode)
        row["transaction_time"] = _safe_time_encode(
            transaction_data.get("transaction_time", "12:00")
        )
        row["current_location"] = _safe_cat_encode(
            "current_location",
            transaction_data.get("current_location", "Bengaluru")
        )
        row["previous_location"] = _safe_cat_encode(
            "previous_location",
            transaction_data.get("previous_location", "Bengaluru")
        )
        row["transaction_type"] = _safe_cat_encode(
            "transaction_type",
            transaction_data.get("transaction_type", "Transfer")
        )

        # Numeric features
        row["transaction_amount"]          = float(transaction_data.get("transaction_amount", 0))
        row["avg_transaction_30d"]         = float(transaction_data.get("avg_transaction_30d", 5000))
        row["transaction_frequency_10min"] = int(transaction_data.get("transaction_frequency_10min", 1))
        row["account_balance"]             = float(transaction_data.get("account_balance", 5000))
        row["account_age_days"]            = int(transaction_data.get("account_age_days", 365))
        row["failed_login_attempts"]       = int(transaction_data.get("failed_login_attempts", 0))
        row["login_hour"]                  = int(transaction_data.get("login_hour", 12))
        row["transactions_today"]          = int(transaction_data.get("transactions_today", 1))

        # ── Build DataFrame in the exact column order seen during training ──
        df_input = pd.DataFrame([row], columns=FEATURE_COLS)

        # ── Scale ─────────────────────────────────────────────────────────
        X_scaled = _preprocessor.scaler.transform(df_input)

        # ── Classification ────────────────────────────────────────────────
        pred_encoded  = _clf_model.predict(X_scaled)[0]
        proba         = _clf_model.predict_proba(X_scaled)[0]
        fraud_label   = _preprocessor.fraud_label_encoder.inverse_transform([pred_encoded])[0]
        fraud_proba   = float(proba[list(_preprocessor.fraud_label_encoder.classes_).index("Fraud")])
        confidence    = float(max(proba) * 100)

        # ── Regression ────────────────────────────────────────────────────
        risk_score = float(_reg_model.predict(X_scaled)[0])
        risk_score = max(0.0, min(100.0, risk_score))

        # ── Risk level label ──────────────────────────────────────────────
        if risk_score >= 80:
            risk_level = "Critical"
        elif risk_score >= 60:
            risk_level = "High"
        elif risk_score >= 35:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        is_suspicious = (fraud_label == "Fraud") or (risk_score >= 60)

        return {
            "status":               "success",
            "fraud_prediction":     fraud_label,
            "fraud_probability":    fraud_proba,
            "confidence":           confidence,
            "predicted_risk_score": risk_score,
            "is_suspicious":        is_suspicious,
            "risk_level":           risk_level,
        }

    except Exception as exc:
        return {
            "status":               "error",
            "message":              str(exc),
            "fraud_prediction":     "Normal",
            "fraud_probability":    0.0,
            "confidence":           50.0,
            "predicted_risk_score": 0.0,
            "is_suspicious":        False,
            "risk_level":           "Low",
        }


def get_model_metadata() -> dict:
    global _metadata
    if _metadata is None:
        try:
            with open(Config.METADATA_PATH) as f:
                _metadata = json.load(f)
        except Exception:
            return {}
    return _metadata
