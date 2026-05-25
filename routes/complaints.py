"""Complaints blueprint."""

from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash)
from flask_login import login_required, current_user
from bson import ObjectId

from app import get_db

complaints_bp = Blueprint("complaints", __name__, url_prefix="/complaints")


@complaints_bp.route("/")
@login_required
def list_complaints():
    db      = get_db()
    user_id = current_user.get_id()
    items   = list(db.complaints.find({"user_id": user_id}).sort("created_at", -1))
    return render_template("user/complaints.html", complaints=items)


@complaints_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_complaint():
    if request.method == "POST":
        db      = get_db()
        subject = request.form.get("subject", "").strip()[:200]
        desc    = request.form.get("description", "").strip()[:2000]
        txn_ref = request.form.get("txn_ref", "").strip()

        if not subject or not desc:
            flash("Subject and description are required.", "danger")
            return render_template("user/new_complaint.html")

        db.complaints.insert_one({
            "user_id":     current_user.get_id(),
            "subject":     subject,
            "description": desc,
            "txn_ref":     txn_ref,
            "status":      "Open",
            "admin_reply": "",
            "created_at":  datetime.utcnow(),
            "updated_at":  datetime.utcnow(),
        })
        flash("Complaint submitted successfully. We will respond within 48 hours.", "success")
        return redirect(url_for("complaints.list_complaints"))

    return render_template("user/new_complaint.html")
