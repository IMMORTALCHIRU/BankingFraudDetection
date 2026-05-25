"""Profile management blueprint."""

import re
from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash)
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId

from app import get_db
from services.fraud_engine import CITIES

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


@profile_bp.route("/")
@login_required
def index():
    db      = get_db()
    user_id = current_user.get_id()
    user    = db.users.find_one({"_id": ObjectId(user_id)})
    login_hist = list(db.login_history.find({"user_id": user_id}).sort("login_time", -1).limit(5))
    return render_template("user/profile.html", user=user, login_history=login_hist, cities=CITIES)


@profile_bp.route("/update", methods=["POST"])
@login_required
def update():
    db      = get_db()
    user_id = current_user.get_id()
    phone   = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    city    = request.form.get("city", "").strip()

    if phone and not re.match(r"^[6-9]\d{9}$", phone):
        flash("Invalid phone number.", "danger")
        return redirect(url_for("profile.index"))

    update_data = {"updated_at": datetime.utcnow()}
    if phone:
        update_data["phone"] = phone
    if address:
        update_data["address"] = address
    if city and city in CITIES:
        update_data["city"] = city

    db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    flash("Profile updated successfully.", "success")
    return redirect(url_for("profile.index"))


@profile_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    db           = get_db()
    user_id      = current_user.get_id()
    current_pass = request.form.get("current_password", "")
    new_pass     = request.form.get("new_password", "")
    confirm_pass = request.form.get("confirm_password", "")

    user_doc = db.users.find_one({"_id": ObjectId(user_id)})

    if not check_password_hash(user_doc["password_hash"], current_pass):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("profile.index"))
    if new_pass != confirm_pass:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("profile.index"))
    if len(new_pass) < 8:
        flash("Password must be at least 8 characters.", "danger")
        return redirect(url_for("profile.index"))

    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password_hash": generate_password_hash(new_pass)}}
    )
    flash("Password changed successfully.", "success")
    return redirect(url_for("profile.index"))
