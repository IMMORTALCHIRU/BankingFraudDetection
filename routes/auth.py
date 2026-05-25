"""Authentication blueprint — register, OTP verify, login, logout, password reset."""

import re
import random
import string
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, session, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId

from app import get_db, User
from services import otp_service, email_service
from config import Config

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_account_number() -> str:
    db = get_db()
    while True:
        acc = "BFD" + "".join(random.choices(string.digits, k=9))
        if not db.users.find_one({"account_number": acc}):
            return acc


def _get_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "0.0.0.0")


def _get_browser():
    return request.headers.get("User-Agent", "Unknown")[:150]


def _get_location(ip: str = None) -> str:
    """Get location from IP address with multiple fallback services."""
    import urllib.request
    import json
    
    if not ip:
        ip = _get_ip()
    
    # For local/private IPs, try to get public IP first
    if ip.startswith(("127.", "192.168.", "10.", "172.")):
        try:
            # Try to get public IP from ipify
            response = urllib.request.urlopen("https://api.ipify.org?format=json", timeout=2)
            data = json.loads(response.read().decode())
            public_ip = data.get("ip")
            if public_ip:
                ip = public_ip
        except:
            pass
    
    # Try primary geolocation service (ip-api.com)
    try:
        url = f"https://ip-api.com/json/{ip}?fields=city,country"
        response = urllib.request.urlopen(url, timeout=3)
        data = json.loads(response.read().decode())
        if data.get("status") == "success":
            city = data.get("city", "")
            country = data.get("country", "")
            if city and country:
                return f"{city}, {country}"
            elif country:
                return country
        return "Unknown"
    except:
        pass
    
    # Fallback to secondary service (ipinfo.io)
    try:
        url = f"https://ipinfo.io/{ip}/json"
        response = urllib.request.urlopen(url, timeout=3)
        data = json.loads(response.read().decode())
        city = data.get("city", "")
        country = data.get("country", "")
        if city and country:
            return f"{city}, {country}"
        elif country:
            return country
        return "Unknown"
    except:
        pass
    
    # Fallback to tertiary service (geoip-db.com)
    try:
        url = f"https://geolocation-db.com/json/{ip}"
        response = urllib.request.urlopen(url, timeout=3)
        data = json.loads(response.read().decode())
        city = data.get("city", "")
        country_name = data.get("country_name", "")
        if city and country_name:
            return f"{city}, {country_name}"
        elif country_name:
            return country_name
        return "Unknown"
    except:
        pass
    
    return "Unknown"


# ── Register ─────────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        db = get_db()
        full_name    = request.form.get("full_name", "").strip()
        email        = request.form.get("email", "").strip().lower()
        phone        = request.form.get("phone", "").strip()
        address      = request.form.get("address", "").strip()
        dob          = request.form.get("dob", "").strip()
        gender       = request.form.get("gender", "").strip()
        password     = request.form.get("password", "")
        confirm_pass = request.form.get("confirm_password", "")
        city         = request.form.get("city", "Bengaluru").strip()

        # ── Validations ──────────────────────────────────────────────────
        errors = []
        if not all([full_name, email, phone, address, dob, gender, password]):
            errors.append("All fields are required.")
        if password != confirm_pass:
            errors.append("Passwords do not match.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if not re.match(r"^[6-9]\d{9}$", phone):
            errors.append("Enter a valid 10-digit Indian mobile number.")
        if not re.match(r"^[\w.+\-]+@[\w\-]+\.[a-z]{2,}$", email):
            errors.append("Enter a valid email address.")

        # Duplicate check
        if db.users.find_one({"email": email}):
            errors.append("Email is already registered.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", form_data=request.form)

        # ── Create user document (unverified) ────────────────────────────
        acc_number = _generate_account_number()
        user_doc = {
            "full_name":       full_name,
            "email":           email,
            "phone":           phone,
            "address":         address,
            "dob":             dob,
            "gender":          gender,
            "city":            city,
            "password_hash":   generate_password_hash(password),
            "account_number":  acc_number,
            "balance":         Config.DEFAULT_BALANCE,
            "account_status":  "Unverified",
            "fraud_score":     0,
            "is_admin":        False,
            "failed_attempts": 0,
            "is_locked":       False,
            "created_at":      datetime.utcnow(),
            "last_login":      None,
        }
        result = db.users.insert_one(user_doc)

        # ── Send OTP ────────────────────────────────────────────────────
        otp = otp_service.generate_otp()
        otp_service.store_otp(db, email, otp, "registration")
        email_service.send_registration_otp(full_name, email, otp, _get_ip())

        session["pending_verify_email"] = email
        flash("Registration successful! Check your email for the OTP.", "success")
        return redirect(url_for("auth.verify_otp"))

    return render_template("auth/register.html", form_data={})


# ── Verify OTP ───────────────────────────────────────────────────────────────

@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email = session.get("pending_verify_email")
    if not email:
        return redirect(url_for("auth.register"))

    if request.method == "POST":
        db  = get_db()
        otp = request.form.get("otp", "").strip()

        result = otp_service.verify_otp(db, email, otp, "registration")
        if result["valid"]:
            db.users.update_one(
                {"email": email},
                {"$set": {"account_status": "Active", "verified_at": datetime.utcnow()}}
            )
            session.pop("pending_verify_email", None)
            flash("Account verified successfully! Please log in.", "success")
            return redirect(url_for("auth.login"))
        else:
            flash(result["reason"], "danger")

    return render_template("auth/verify_otp.html", email=email)


@auth_bp.route("/resend-otp")
def resend_otp():
    email = session.get("pending_verify_email")
    if not email:
        return redirect(url_for("auth.register"))
    db   = get_db()
    user = db.users.find_one({"email": email})
    if user:
        otp = otp_service.generate_otp()
        otp_service.store_otp(db, email, otp, "registration")
        email_service.send_registration_otp(user["full_name"], email, otp, _get_ip())
        flash("A new OTP has been sent to your email.", "info")
    return redirect(url_for("auth.verify_otp"))


# ── Login ────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        db       = get_db()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember_me") == "on"

        user_doc = db.users.find_one({"email": email})

        # ── Admin shortcut ───────────────────────────────────────────────
        if email == Config.ADMIN_EMAIL and password == Config.ADMIN_PASSWORD:
            if not user_doc:
                # Auto-create admin account
                user_doc = {
                    "full_name":       "BankGuard Admin",
                    "email":           Config.ADMIN_EMAIL,
                    "phone":           "0000000000",
                    "address":         "Admin Office",
                    "dob":             "1990-01-01",
                    "gender":          "Other",
                    "city":            "Bengaluru",
                    "password_hash":   generate_password_hash(Config.ADMIN_PASSWORD),
                    "account_number":  "ADMIN000000000",
                    "balance":         0.0,
                    "account_status":  "Active",
                    "fraud_score":     0,
                    "is_admin":        True,
                    "failed_attempts": 0,
                    "is_locked":       False,
                    "created_at":      datetime.utcnow(),
                    "last_login":      None,
                }
                result = db.users.insert_one(user_doc)
                user_doc["_id"] = result.inserted_id
            else:
                db.users.update_one({"email": email}, {"$set": {"is_admin": True}})
                user_doc["is_admin"] = True

            user = User(user_doc)
            login_user(user, remember=remember)
            db.users.update_one({"email": email}, {"$set": {"last_login": datetime.utcnow(), "failed_attempts": 0}})
            _log_login(db, str(user_doc["_id"]), True)
            return redirect(url_for("admin.dashboard"))

        if not user_doc:
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")

        # ── Account checks ───────────────────────────────────────────────
        if user_doc.get("is_locked"):
            flash("Your account is locked. Contact support.", "danger")
            return render_template("auth/login.html")

        if user_doc.get("account_status") == "Unverified":
            session["pending_verify_email"] = email
            flash("Please verify your email first.", "warning")
            return redirect(url_for("auth.verify_otp"))

        if user_doc.get("account_status") == "Frozen":
            flash("Your account has been frozen. Contact support.", "danger")
            return render_template("auth/login.html")

        if not check_password_hash(user_doc["password_hash"], password):
            attempts = user_doc.get("failed_attempts", 0) + 1
            update = {"$set": {"failed_attempts": attempts}}
            if attempts >= Config.MAX_FAILED_ATTEMPTS:
                update["$set"]["is_locked"] = True
                flash("Too many failed attempts. Account locked.", "danger")
            else:
                flash(f"Invalid password. {Config.MAX_FAILED_ATTEMPTS - attempts} attempts remaining.", "danger")
            db.users.update_one({"_id": user_doc["_id"]}, update)
            _log_login(db, str(user_doc["_id"]), False)
            return render_template("auth/login.html")

        # ── Successful login ─────────────────────────────────────────────
        db.users.update_one(
            {"_id": user_doc["_id"]},
            {"$set": {"last_login": datetime.utcnow(), "failed_attempts": 0}}
        )
        user_doc["failed_attempts"] = 0
        user = User(user_doc)
        login_user(user, remember=remember)
        _log_login(db, str(user_doc["_id"]), True)

        # Security email
        try:
            ip = _get_ip()
            location = _get_location(ip)
            email_service.send_login_alert(user_doc["full_name"], email, ip, _get_browser(), location)
        except Exception:
            pass

        # Add welcome notification
        db.notifications.insert_one({
            "user_id":    str(user_doc["_id"]),
            "message":    f"Welcome back, {user_doc['full_name']}! You logged in from {location}",
            "type":       "login",
            "read":       False,
            "created_at": datetime.utcnow(),
        })

        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html")


def _log_login(db, user_id: str, success: bool):
    db.login_history.insert_one({
        "user_id":    user_id,
        "login_time": datetime.utcnow(),
        "ip":         _get_ip(),
        "device":     _get_browser(),
        "success":    success,
    })


# ── Logout ───────────────────────────────────────────────────────────────────

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))


# ── Forgot Password ──────────────────────────────────────────────────────────

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        db    = get_db()
        email = request.form.get("email", "").strip().lower()
        user  = db.users.find_one({"email": email})
        if user:
            otp = otp_service.generate_otp()
            otp_service.store_otp(db, email, otp, "password_reset")
            email_service.send_password_reset_otp(user["full_name"], email, otp)
            session["reset_email"] = email
            flash("OTP sent to your email.", "success")
            return redirect(url_for("auth.reset_password"))
        flash("Email not found.", "danger")
    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        db           = get_db()
        otp          = request.form.get("otp", "").strip()
        new_password = request.form.get("new_password", "")
        confirm      = request.form.get("confirm_password", "")

        if new_password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("auth/reset_password.html", email=email)
        if len(new_password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth/reset_password.html", email=email)

        result = otp_service.verify_otp(db, email, otp, "password_reset")
        if result["valid"]:
            db.users.update_one(
                {"email": email},
                {"$set": {"password_hash": generate_password_hash(new_password),
                           "failed_attempts": 0, "is_locked": False}}
            )
            session.pop("reset_email", None)
            flash("Password reset successful! Please log in.", "success")
            return redirect(url_for("auth.login"))
        flash(result["reason"], "danger")

    return render_template("auth/reset_password.html", email=email)
