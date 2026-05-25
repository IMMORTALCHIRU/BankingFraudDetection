"""Transaction blueprint — deposit, transfer, history, verify, receipt."""

import io
import csv
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, jsonify, session, make_response, current_app)
from flask_login import login_required, current_user
from bson import ObjectId

from app import get_db
from config import Config
from services import fraud_engine, otp_service, email_service

transactions_bp = Blueprint("transactions", __name__, url_prefix="/transactions")

CITIES = fraud_engine.CITIES
TRANSACTION_TYPES = fraud_engine.TRANSACTION_TYPES


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "0.0.0.0")


def _get_device():
    return request.headers.get("User-Agent", "Unknown")[:150]


def _build_fraud_features(db, user_doc: dict, amount: float,
                           txn_type: str, receiver_city: str) -> dict:
    user_id    = str(user_doc["_id"])
    now        = datetime.utcnow()
    login_hour = now.hour

    # avg_transaction_30d
    since_30d = now - timedelta(days=30)
    recent_txns = list(db.transactions.find({
        "sender_id": user_id,
        "timestamp": {"$gte": since_30d},
        "status":    {"$in": ["Completed", "Verified"]},
    }))
    avg_txn_30d = (
        sum(t["amount"] for t in recent_txns) / len(recent_txns)
        if recent_txns else amount
    )

    # transaction_frequency_10min
    since_10m = now - timedelta(minutes=10)
    txn_freq_10min = db.transactions.count_documents({
        "sender_id": user_id,
        "timestamp": {"$gte": since_10m},
    })

    # account_age_days
    created_at     = user_doc.get("created_at", now)
    account_age    = max(1, (now - created_at).days)

    # transactions_today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    txns_today  = db.transactions.count_documents({
        "sender_id": user_id,
        "timestamp": {"$gte": today_start},
    })

    # Previous location (last completed transaction city)
    last_txn = db.transactions.find_one(
        {"sender_id": user_id, "status": {"$in": ["Completed", "Verified"]}},
        sort=[("timestamp", -1)]
    )
    prev_location = last_txn.get("location", user_doc.get("city", "Bengaluru")) if last_txn else user_doc.get("city", "Bengaluru")

    return {
        "transaction_time":          now.strftime("%H:%M"),
        "transaction_amount":        amount,
        "avg_transaction_30d":       avg_txn_30d,
        "transaction_frequency_10min": txn_freq_10min + 1,
        "current_location":          receiver_city,
        "previous_location":         prev_location,
        "account_balance":           user_doc.get("balance", 5000),
        "transaction_type":          txn_type,
        "account_age_days":          account_age,
        "failed_login_attempts":     user_doc.get("failed_attempts", 0),
        "login_hour":                login_hour,
        "transactions_today":        txns_today + 1,
    }


# ── Deposit ───────────────────────────────────────────────────────────────────

@transactions_bp.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    db = get_db()

    if request.method == "POST":
        user_id  = current_user.get_id()
        user_doc = db.users.find_one({"_id": ObjectId(user_id)})
        amount   = float(request.form.get("amount", 0))
        notes    = request.form.get("notes", "").strip()[:200]

        if amount <= 0:
            flash("Enter a valid amount.", "danger")
            return render_template("user/deposit.html")

        now = datetime.utcnow()
        txn_count = db.transactions.count_documents({"sender_id": user_id})

        # Build features
        features = _build_fraud_features(db, user_doc, amount, "Deposit",
                                          user_doc.get("city", "Bengaluru"))
        fraud_result = {"fraud_prediction": "Normal", "predicted_risk_score": 0,
                        "confidence": 99, "is_suspicious": False, "risk_level": "Low", "fraud_probability": 0}
        if txn_count >= Config.BASELINE_TXN_COUNT:
            fraud_result = fraud_engine.predict_transaction(features)

        # Build transaction
        txn_doc = {
            "sender_id":          user_id,
            "sender_name":        user_doc["full_name"],
            "receiver_account":   user_doc["account_number"],
            "receiver_name":      user_doc["full_name"],
            "amount":             amount,
            "transaction_type":   "Deposit",
            "timestamp":          now,
            "location":           user_doc.get("city", "Bengaluru"),
            "device":             _get_device(),
            "ip":                 _get_ip(),
            "notes":              notes,
            "fraud_prediction":   fraud_result["fraud_prediction"],
            "fraud_probability":  fraud_result.get("fraud_probability", 0),
            "risk_score":         fraud_result["predicted_risk_score"],
            "confidence":         fraud_result["confidence"],
            "risk_level":         fraud_result["risk_level"],
            "otp_verified":       False,
            "status":             "Completed",
        }

        result = db.transactions.insert_one(txn_doc)
        txn_id = str(result.inserted_id)

        # Credit balance
        db.users.update_one({"_id": ObjectId(user_id)}, {"$inc": {"balance": amount}})

        # Confirmation email
        try:
            email_service.send_transaction_confirmation(
                user_doc["full_name"], user_doc["email"],
                {"amount": amount, "receiver_name": user_doc["full_name"],
                 "transaction_type": "Deposit", "txn_id": txn_id}
            )
        except Exception:
            pass

        flash(f"₹{amount:,.2f} deposited successfully!", "success")
        return redirect(url_for("transactions.receipt", txn_id=txn_id))

    return render_template("user/deposit.html")


# ── Transfer ──────────────────────────────────────────────────────────────────

@transactions_bp.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    db = get_db()

    if request.method == "POST":
        user_id         = current_user.get_id()
        user_doc        = db.users.find_one({"_id": ObjectId(user_id)})
        receiver_account = request.form.get("receiver_account", "").strip()
        amount          = float(request.form.get("amount", 0))
        txn_type        = request.form.get("transaction_type", "Transfer")
        notes           = request.form.get("notes", "").strip()[:200]

        if txn_type not in TRANSACTION_TYPES:
            txn_type = "Transfer"

        # Validations
        if amount <= 0:
            flash("Enter a valid amount.", "danger")
            return render_template("user/transfer.html", cities=CITIES)
        if amount > user_doc.get("balance", 0):
            flash("Insufficient balance.", "danger")
            return render_template("user/transfer.html", cities=CITIES)
        # Only check for own account transfer if NOT a withdrawal
        if txn_type != "Withdrawal" and receiver_account == user_doc["account_number"]:
            flash("Cannot transfer to your own account.", "danger")
            return render_template("user/transfer.html", cities=CITIES)

        # Validate receiver
        receiver = db.users.find_one({"account_number": receiver_account})
        if not receiver:
            flash("Receiver account not found.", "danger")
            return render_template("user/transfer.html", cities=CITIES)

        if receiver.get("account_status") in ("Frozen",):
            flash("Receiver account is frozen.", "danger")
            return render_template("user/transfer.html", cities=CITIES)

        now = datetime.utcnow()
        txn_count = db.transactions.count_documents({"sender_id": user_id})

        # Build ML features
        features = _build_fraud_features(db, user_doc, amount, txn_type,
                                          receiver.get("city", "Bengaluru"))
        fraud_result = {"fraud_prediction": "Normal", "predicted_risk_score": 0,
                        "confidence": 99, "is_suspicious": False, "risk_level": "Low", "fraud_probability": 0}
        if txn_count >= Config.BASELINE_TXN_COUNT:
            fraud_result = fraud_engine.predict_transaction(features)

        # Build transaction document (pending)
        txn_doc = {
            "sender_id":          user_id,
            "sender_name":        user_doc["full_name"],
            "receiver_account":   receiver_account,
            "receiver_name":      receiver["full_name"],
            "amount":             amount,
            "transaction_type":   txn_type,
            "timestamp":          now,
            "location":           receiver.get("city", "Bengaluru"),
            "device":             _get_device(),
            "ip":                 _get_ip(),
            "notes":              notes,
            "fraud_prediction":   fraud_result["fraud_prediction"],
            "fraud_probability":  fraud_result.get("fraud_probability", 0),
            "risk_score":         fraud_result["predicted_risk_score"],
            "confidence":         fraud_result["confidence"],
            "risk_level":         fraud_result["risk_level"],
            "otp_verified":       False,
            "status":             "Pending",
        }
        result = db.transactions.insert_one(txn_doc)
        txn_id = str(result.inserted_id)

        # ── High-value OR suspicious → OTP verification ──────────────────
        if amount >= Config.HIGH_VALUE_TXN_LIMIT or fraud_result["is_suspicious"]:
            otp = otp_service.generate_otp()
            otp_service.store_txn_otp(db, txn_id, otp, Config.TXN_OTP_EXPIRY_SECONDS)
            txn_data_for_email = {
                "amount": amount, "receiver_name": receiver["full_name"],
                "risk_score": fraud_result["predicted_risk_score"],
                "confidence": fraud_result["confidence"],
                "fraud_prediction": fraud_result["fraud_prediction"],
                "ip": _get_ip(), "device": _get_device()[:80],
            }
            try:
                email_service.send_suspicious_transaction_alert(
                    user_doc["full_name"], user_doc["email"],
                    txn_data_for_email, otp, Config.ADMIN_EMAIL
                )
            except Exception:
                pass

            # Calculate risk level based on risk score
            risk_score = fraud_result.get('predicted_risk_score', 0)
            if risk_score >= 75:
                risk_level = "Critical"
            elif risk_score >= 60:
                risk_level = "High"
            elif risk_score >= 35:
                risk_level = "Medium"
            else:
                risk_level = "Low"
            
            db.fraud_alerts.insert_one({
                "user_id":    user_id,
                "transaction_id": txn_id,
                "alert_type": "SuspiciousTransaction",
                "description": f"Transaction of ₹{amount:,.2f} flagged (risk: {risk_score:.1f})",
                "amount": amount,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "fraud_probability": fraud_result.get('fraud_probability', 0),
                "confidence": fraud_result.get('confidence', 0),
                "timestamp": now,
                "created_at": now,
                "resolved":   False,
            })

            session["otp_txn_id"] = txn_id
            flash("Suspicious transaction detected! Please verify with OTP.", "warning")
            return redirect(url_for("transactions.verify_transaction"))

        # ── Normal transaction → complete immediately ─────────────────────
        db.transactions.update_one({"_id": ObjectId(txn_id)}, {"$set": {"status": "Completed"}})
        # Deduct from sender
        db.users.update_one({"_id": ObjectId(user_id)}, {"$inc": {"balance": -amount}})
        # Only add to receiver if NOT a withdrawal (withdrawal is transfer to own account)
        if txn_type != "Withdrawal":
            db.users.update_one({"_id": receiver["_id"]},   {"$inc": {"balance": amount}})

        try:
            email_service.send_transaction_confirmation(
                user_doc["full_name"], user_doc["email"],
                {"amount": amount, "receiver_name": receiver["full_name"],
                 "transaction_type": txn_type, "txn_id": txn_id}
            )
        except Exception:
            pass

        flash(f"₹{amount:,.2f} transferred to {receiver['full_name']} successfully!", "success")
        return redirect(url_for("transactions.receipt", txn_id=txn_id))

    return render_template("user/transfer.html", cities=CITIES)


# ── Verify suspicious transaction OTP ────────────────────────────────────────

@transactions_bp.route("/verify", methods=["GET", "POST"])
@login_required
def verify_transaction():
    txn_id = session.get("otp_txn_id")
    if not txn_id:
        return redirect(url_for("transactions.transfer"))

    db = get_db()

    if request.method == "POST":
        otp      = request.form.get("otp", "").strip()
        result   = otp_service.verify_txn_otp(db, txn_id, otp)
        txn_doc  = db.transactions.find_one({"_id": ObjectId(txn_id)})

        if result["valid"]:
            user_id  = current_user.get_id()
            user_doc = db.users.find_one({"_id": ObjectId(user_id)})
            receiver = db.users.find_one({"account_number": txn_doc["receiver_account"]})
            amount   = txn_doc["amount"]

            db.transactions.update_one(
                {"_id": ObjectId(txn_id)},
                {"$set": {"status": "Verified", "otp_verified": True}}
            )
            db.users.update_one({"_id": ObjectId(user_id)}, {"$inc": {"balance": -amount}})
            if receiver:
                db.users.update_one({"_id": receiver["_id"]}, {"$inc": {"balance": amount}})

            # Resolve fraud alert
            db.fraud_alerts.update_many(
                {"transaction_id": txn_id},
                {"$set": {"resolved": True}}
            )

            session.pop("otp_txn_id", None)
            flash("Transaction verified and completed successfully!", "success")
            return redirect(url_for("transactions.receipt", txn_id=txn_id))

        elif result.get("expired"):
            # Mark as fraud
            db.transactions.update_one(
                {"_id": ObjectId(txn_id)},
                {"$set": {"status": "Fraud", "fraud_prediction": "Fraud"}}
            )
            session.pop("otp_txn_id", None)
            flash("OTP expired. Transaction has been marked as fraudulent and frozen.", "danger")
            return redirect(url_for("transactions.history"))

        flash(result["reason"], "danger")

    txn_doc = db.transactions.find_one({"_id": ObjectId(txn_id)})
    return render_template("user/verify_transaction.html", txn=txn_doc)


# ── Receipt ──────────────────────────────────────────────────────────────────

@transactions_bp.route("/receipt/<txn_id>")
@login_required
def receipt(txn_id):
    db      = get_db()
    txn_doc = db.transactions.find_one({"_id": ObjectId(txn_id)})
    if not txn_doc:
        flash("Transaction not found.", "danger")
        return redirect(url_for("transactions.history"))
    if txn_doc["sender_id"] != current_user.get_id():
        flash("Access denied.", "danger")
        return redirect(url_for("transactions.history"))
    # Add transaction_id from MongoDB _id and map location to current_location
    txn_doc["transaction_id"] = str(txn_doc["_id"])
    txn_doc["current_location"] = txn_doc.get("location", "Unknown")
    return render_template("user/receipt.html", txn=txn_doc)


# ── History ───────────────────────────────────────────────────────────────────

@transactions_bp.route("/history")
@login_required
def history():
    db       = get_db()
    user_id  = current_user.get_id()
    page     = int(request.args.get("page", 1))
    per_page = 15
    search   = request.args.get("search", "").strip()
    txn_type = request.args.get("txn_type", "")
    status   = request.args.get("status", "")
    fraud    = request.args.get("fraud", "")

    query = {"sender_id": user_id}
    if search:
        query["$or"] = [
            {"receiver_name":    {"$regex": search, "$options": "i"}},
            {"receiver_account": {"$regex": search, "$options": "i"}},
        ]
    if txn_type in TRANSACTION_TYPES:
        query["transaction_type"] = txn_type
    if status:
        query["status"] = status
    if fraud in ("Fraud", "Normal"):
        query["fraud_prediction"] = fraud

    total = db.transactions.count_documents(query)
    txns  = list(
        db.transactions.find(query)
        .sort("timestamp", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )

    total_pages = max(1, (total + per_page - 1) // per_page)
    # Add transaction_id from _id for each transaction
    for txn in txns:
        txn["transaction_id"] = str(txn["_id"])
    filters = {
        "search": search,
        "txn_type": txn_type,
        "status": status,
        "fraud": fraud,
    }
    return render_template(
        "user/history.html",
        transactions=txns, page=page, pages=total_pages,
        total=total, filters=filters,
        transaction_types=TRANSACTION_TYPES,
    )


# ── Export CSV ────────────────────────────────────────────────────────────────

@transactions_bp.route("/export/csv")
@login_required
def export_csv():
    db      = get_db()
    user_id = current_user.get_id()
    txns    = list(db.transactions.find({"sender_id": user_id}).sort("timestamp", -1))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Receiver", "Amount (₹)", "Type", "Status",
                     "Fraud Prediction", "Risk Score", "Confidence (%)", "OTP Verified"])
    for t in txns:
        writer.writerow([
            t.get("timestamp", "").strftime("%Y-%m-%d %H:%M") if t.get("timestamp") else "",
            t.get("receiver_name", ""),
            f"{t.get('amount', 0):.2f}",
            t.get("transaction_type", ""),
            t.get("status", ""),
            t.get("fraud_prediction", ""),
            f"{t.get('risk_score', 0):.1f}",
            f"{t.get('confidence', 0):.1f}",
            "Yes" if t.get("otp_verified") else "No",
        ])

    resp = make_response(output.getvalue())
    resp.headers["Content-Disposition"] = "attachment; filename=transactions.csv"
    resp.headers["Content-type"] = "text/csv"
    return resp


# ── Feedback ──────────────────────────────────────────────────────────────────

@transactions_bp.route("/feedback/<txn_id>", methods=["GET", "POST"])
@login_required
def feedback(txn_id):
    db = get_db()
    if request.method == "POST":
        rating  = int(request.form.get("rating", 3))
        comment = request.form.get("comment", "").strip()[:500]
        db.feedbacks.insert_one({
            "user_id":        current_user.get_id(),
            "transaction_id": txn_id,
            "rating":         rating,
            "comment":        comment,
            "created_at":     datetime.utcnow(),
        })
        flash("Thank you for your feedback!", "success")
        return redirect(url_for("transactions.history"))
    txn_doc = db.transactions.find_one({"_id": ObjectId(txn_id)})
    return render_template("user/feedback.html", txn=txn_doc)


# ── Lookup receiver ───────────────────────────────────────────────────────────

@transactions_bp.route("/lookup-receiver")
@login_required
def lookup_receiver():
    acc = request.args.get("account", "").strip()
    db  = get_db()
    rec = db.users.find_one({"account_number": acc}, {"full_name": 1, "city": 1, "account_status": 1})
    if rec and rec.get("account_status") != "Frozen":
        return jsonify({"found": True, "name": rec["full_name"], "city": rec.get("city", "")})
    return jsonify({"found": False})
