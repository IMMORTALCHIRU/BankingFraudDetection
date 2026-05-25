"""Admin blueprint — dashboard, user management, complaints, analytics."""

from datetime import datetime, timedelta
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, jsonify)
from flask_login import login_required, current_user
from bson import ObjectId

from app import get_db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    db  = get_db()
    now = datetime.utcnow()

    # Totals
    total_users      = db.users.count_documents({"is_admin": {"$ne": True}})
    total_txns       = db.transactions.count_documents({})
    fraud_txns       = db.transactions.count_documents({"fraud_prediction": "Fraud"})
    fraud_rate       = round(fraud_txns / total_txns * 100, 1) if total_txns else 0
    active_users     = db.users.count_documents({"account_status": "Active", "is_admin": {"$ne": True}})
    frozen_users     = db.users.count_documents({"account_status": "Frozen", "is_admin": {"$ne": True}})
    open_complaints  = db.complaints.count_documents({"status": "Open"})
    fraud_alerts     = db.fraud_alerts.count_documents({"resolved": False})
    total_volume     = sum(t.get("amount", 0) for t in db.transactions.find({}))
    
    # New users in last 30 days
    thirty_days_ago = now - timedelta(days=30)
    new_users_30d = db.users.count_documents({
        "created_at": {"$gte": thirty_days_ago},
        "is_admin": {"$ne": True}
    })
    
    # Stats dict for template
    stats = {
        "total_users": total_users,
        "total_txns": total_txns,
        "fraud_txns": fraud_txns,
        "total_volume": round(total_volume, 2),
        "fraud_rate": fraud_rate,
        "frozen_users": frozen_users,
        "open_complaints": open_complaints,
        "new_users_30d": new_users_30d,
    }

    # Daily transaction chart (last 7 days)
    daily_labels  = []
    daily_amounts = []
    daily_frauds  = []
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        d_total   = sum(
            t.get("amount", 0)
            for t in db.transactions.find({"timestamp": {"$gte": day_start, "$lt": day_end}})
        )
        d_fraud   = db.transactions.count_documents({
            "timestamp": {"$gte": day_start, "$lt": day_end},
            "fraud_prediction": "Fraud",
        })
        daily_labels.append(day_start.strftime("%d %b"))
        daily_amounts.append(round(d_total, 2))
        daily_frauds.append(d_fraud)

    # Risk distribution
    risk_dist = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    for t in db.transactions.find({}, {"risk_level": 1}):
        rl = t.get("risk_level", "Low")
        if rl in risk_dist:
            risk_dist[rl] += 1

    # Monthly fraud trend (last 6 months)
    monthly_labels = []
    monthly_fraud  = []
    for i in range(5, -1, -1):
        ms = (now.replace(day=1) - timedelta(days=i * 30)).replace(day=1, hour=0, minute=0, second=0)
        me = (ms + timedelta(days=32)).replace(day=1)
        m_fraud = db.transactions.count_documents({
            "timestamp": {"$gte": ms, "$lt": me},
            "fraud_prediction": "Fraud",
        })
        monthly_labels.append(ms.strftime("%b %Y"))
        monthly_fraud.append(m_fraud)

    # User growth (last 6 months)
    user_growth_labels  = []
    user_growth  = []
    for i in range(5, -1, -1):
        ms = (now.replace(day=1) - timedelta(days=i * 30)).replace(day=1, hour=0, minute=0, second=0)
        me = (ms + timedelta(days=32)).replace(day=1)
        count = db.users.count_documents({"created_at": {"$gte": ms, "$lt": me}, "is_admin": {"$ne": True}})
        user_growth_labels.append(ms.strftime("%b %Y"))
        user_growth.append(count)

    # Recent transactions
    recent_txns = list(db.transactions.find().sort("timestamp", -1).limit(10))

    # High-risk users
    high_risk_users = list(db.users.find(
        {"fraud_score": {"$gte": 50}, "is_admin": {"$ne": True}}
    ).sort("fraud_score", -1).limit(5))

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        daily_labels=daily_labels,
        daily_counts=daily_frauds,
        monthly_labels=monthly_labels,
        monthly_fraud=monthly_fraud,
        user_growth_labels=user_growth_labels,
        user_growth=user_growth,
        risk_dist=risk_dist,
        recent_txns=recent_txns,
        high_risk_users=high_risk_users,
    )


# ── User Management ───────────────────────────────────────────────────────────

@admin_bp.route("/users")
@login_required
@admin_required
def users():
    db       = get_db()
    page     = int(request.args.get("page", 1))
    per_page = 15
    search   = request.args.get("search", "").strip()
    status   = request.args.get("status", "")

    query = {"is_admin": {"$ne": True}}
    if search:
        query["$or"] = [
            {"full_name":      {"$regex": search, "$options": "i"}},
            {"email":          {"$regex": search, "$options": "i"}},
            {"account_number": {"$regex": search, "$options": "i"}},
            {"phone":          {"$regex": search, "$options": "i"}},
        ]
    if status:
        query["account_status"] = status

    total = db.users.count_documents(query)
    user_list = list(
        db.users.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    pages = max(1, (total + per_page - 1) // per_page)
    return render_template("admin/users.html",
                           users=user_list, page=page, pages=pages,
                           total=total, search=search, status=status)


@admin_bp.route("/users/<user_id>")
@login_required
@admin_required
def user_detail(user_id):
    db       = get_db()
    user_doc = db.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        flash("User not found.", "danger")
        return redirect(url_for("admin.users"))

    txns        = list(db.transactions.find({"sender_id": user_id}).sort("timestamp", -1).limit(20))
    alerts      = list(db.fraud_alerts.find({"user_id": user_id}).sort("created_at", -1).limit(10))
    # Ensure all required fields exist with defaults
    for a in alerts:
        a["amount"] = a.get("amount", 0)
        a["risk_score"] = a.get("risk_score", 0)
        a["risk_level"] = a.get("risk_level", "Low")
        a["fraud_probability"] = a.get("fraud_probability", 0)
        a["confidence"] = a.get("confidence", 0)
        a["timestamp"] = a.get("timestamp", a.get("created_at"))
    login_hist  = list(db.login_history.find({"user_id": user_id}).sort("login_time", -1).limit(10))
    complaints  = list(db.complaints.find({"user_id": user_id}).sort("created_at", -1))
    return render_template("admin/user_detail.html",
                           user=user_doc, transactions=txns, fraud_alerts=alerts,
                           login_hist=login_hist, complaints=complaints)


@admin_bp.route("/users/<user_id>/freeze", methods=["POST"])
@login_required
@admin_required
def freeze_user(user_id):
    db      = get_db()
    user    = db.users.find_one({"_id": ObjectId(user_id)})
    new_status = "Frozen" if user.get("account_status") != "Frozen" else "Active"
    db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"account_status": new_status}})
    _admin_log(db, f"Account {new_status}", user_id)
    flash(f"Account {new_status}.", "success" if new_status == "Active" else "warning")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/<user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    db = get_db()
    db.users.delete_one({"_id": ObjectId(user_id)})
    _admin_log(db, "User Deleted", user_id)
    flash("User deleted.", "info")
    return redirect(url_for("admin.users"))


# ── Transactions ──────────────────────────────────────────────────────────────

@admin_bp.route("/transactions")
@login_required
@admin_required
def transactions():
    db       = get_db()
    page     = int(request.args.get("page", 1))
    per_page = 15
    fraud    = request.args.get("fraud", "")
    risk     = request.args.get("risk", "")
    search   = request.args.get("search", "").strip()

    query = {}
    if fraud in ("Fraud", "Normal"):
        query["fraud_prediction"] = fraud
    if risk in ("Low", "Medium", "High", "Critical"):
        query["risk_level"] = risk
    if search:
        query["$or"] = [
            {"sender_name":      {"$regex": search, "$options": "i"}},
            {"receiver_name":    {"$regex": search, "$options": "i"}},
            {"receiver_account": {"$regex": search, "$options": "i"}},
        ]

    total = db.transactions.count_documents(query)
    txns  = list(db.transactions.find(query).sort("timestamp", -1)
                 .skip((page - 1) * per_page).limit(per_page))
    pages = max(1, (total + per_page - 1) // per_page)
    
    # Build filters dict for template
    filters = {"search": search, "fraud": fraud, "risk": risk}
    
    return render_template("admin/transactions.html",
                           transactions=txns, page=page, pages=pages,
                           total=total, filters=filters)


# ── Complaints ────────────────────────────────────────────────────────────────

@admin_bp.route("/complaints")
@login_required
@admin_required
def complaints():
    db    = get_db()
    items = list(db.complaints.find().sort("created_at", -1))
    for c in items:
        user = db.users.find_one({"_id": ObjectId(c["user_id"])}, {"full_name": 1, "email": 1})
        c["user_name"]  = user["full_name"] if user else "Unknown"
        c["user_email"] = user["email"] if user else ""
    return render_template("admin/complaints.html", complaints=items)


@admin_bp.route("/complaints/<complaint_id>/update", methods=["POST"])
@login_required
@admin_required
def update_complaint(complaint_id):
    db     = get_db()
    status = request.form.get("status", "Open")
    reply  = request.form.get("reply", "").strip()[:1000]
    db.complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$set": {"status": status, "admin_reply": reply, "updated_at": datetime.utcnow()}}
    )
    flash("Complaint updated.", "success")
    return redirect(url_for("admin.complaints"))


# ── Fraud Alerts ──────────────────────────────────────────────────────────────

@admin_bp.route("/fraud-alerts")
@login_required
@admin_required
def fraud_alerts():
    db       = get_db()
    page     = int(request.args.get("page", 1))
    per_page = 20
    
    total = db.fraud_alerts.count_documents({})
    alerts = list(db.fraud_alerts.find().sort("created_at", -1)
                  .skip((page - 1) * per_page).limit(per_page))
    pages = max(1, (total + per_page - 1) // per_page)
    
    for a in alerts:
        user = db.users.find_one({"_id": ObjectId(a["user_id"])}, {"full_name": 1, "email": 1})
        a["user_name"]  = user["full_name"] if user else "Unknown"
        a["user_email"] = user["email"] if user else ""
        # Set defaults for any missing fields
        a["amount"] = a.get("amount", 0)
        a["risk_score"] = a.get("risk_score", 0)
        a["risk_level"] = a.get("risk_level", "Low")
        a["fraud_probability"] = a.get("fraud_probability", 0)
        a["timestamp"] = a.get("timestamp", a.get("created_at"))
    
    return render_template("admin/fraud_alerts.html", alerts=alerts, page=page, pages=pages, total=total)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _admin_log(db, action: str, user_id: str):
    db.admin_logs.insert_one({
        "action":      action,
        "user_id":     user_id,
        "admin_email": current_user.email if hasattr(current_user, "email") else "admin",
        "timestamp":   datetime.utcnow(),
    })
