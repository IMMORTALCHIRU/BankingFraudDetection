"""User dashboard blueprint."""

from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from bson import ObjectId

from app import get_db

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    if current_user.is_admin:
        from flask import redirect, url_for
        return redirect(url_for("admin.dashboard"))

    db      = get_db()
    user_id = current_user.get_id()
    user    = db.users.find_one({"_id": ObjectId(user_id)})

    # ── Aggregate stats ────────────────────────────────────────────────────
    txns = list(db.transactions.find({"sender_id": user_id}).sort("timestamp", -1))

    total_txns      = len(txns)
    fraud_alerts    = db.fraud_alerts.count_documents({"user_id": user_id, "resolved": False})
    total_deposits  = sum(t["amount"] for t in txns if t.get("transaction_type") == "Deposit")
    total_transfers = sum(t["amount"] for t in txns if t.get("transaction_type") == "Transfer")
    fraud_count     = sum(1 for t in txns if t.get("fraud_prediction") == "Fraud")

    recent_txns = txns[:8]

    # ── Monthly chart data (last 6 months) ─────────────────────────────────
    monthly_labels = []
    monthly_amounts = []
    now = datetime.utcnow()
    for i in range(5, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(day=1, hour=0, minute=0, second=0)
        month_end   = (month_start + timedelta(days=32)).replace(day=1)
        m_total = sum(
            t["amount"] for t in txns
            if month_start <= t.get("timestamp", datetime.min) < month_end
        )
        monthly_labels.append(month_start.strftime("%b %Y"))
        monthly_amounts.append(round(m_total, 2))

    # ── Transaction type pie data ─────────────────────────────────────────
    type_counts = {"Deposit": 0, "Transfer": 0, "Withdrawal": 0}
    for t in txns:
        t_type = t.get("transaction_type", "Transfer")
        if t_type in type_counts:
            type_counts[t_type] += 1

    # ── Fraud probability history (last 10 transactions) ─────────────────
    fraud_proba_data = [
        {"label": f"Txn {i+1}", "value": round(t.get("fraud_probability", 0) * 100, 1)}
        for i, t in enumerate(reversed(txns[-10:]))
    ]

    # ── Notifications ─────────────────────────────────────────────────────
    notifications = list(
        db.notifications.find({"user_id": user_id, "read": False})
        .sort("created_at", -1)
        .limit(5)
    )

    # ── Support Tickets with Admin Replies ─────────────────────────────────
    support_tickets = list(
        db.complaints.find({"user_id": user_id, "admin_reply": {"$ne": ""}})
        .sort("updated_at", -1)
        .limit(5)
    )

    return render_template(
        "user/dashboard.html",
        user=user,
        total_txns=total_txns,
        fraud_alerts=fraud_alerts,
        total_deposits=round(total_deposits, 2),
        total_transfers=round(total_transfers, 2),
        fraud_count=fraud_count,
        recent_txns=recent_txns,
        monthly_labels=monthly_labels,
        monthly_amounts=monthly_amounts,
        type_counts=type_counts,
        fraud_proba_data=fraud_proba_data,
        notifications=notifications,
        support_tickets=support_tickets,
        unread_count=len(notifications),
        now=datetime.utcnow(),
    )


@dashboard_bp.route("/mark-notifications-read", methods=["POST"])
@login_required
def mark_notifications_read():
    db = get_db()
    db.notifications.update_many(
        {"user_id": current_user.get_id()},
        {"$set": {"read": True}}
    )
    return jsonify({"status": "ok"})


@dashboard_bp.route("/notifications")
@login_required
def notifications():
    """View all notifications."""
    db = get_db()
    user_id = current_user.get_id()
    
    # Get all notifications
    all_notifications = list(
        db.notifications.find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(50)
    )
    
    # Mark all as read
    db.notifications.update_many(
        {"user_id": user_id},
        {"$set": {"read": True}}
    )
    
    return render_template("user/notifications.html", notifications=all_notifications)
