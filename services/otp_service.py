"""OTP generation, storage and verification via MongoDB."""

import random
import string
from datetime import datetime, timedelta
from bson import ObjectId


def generate_otp(length: int = 4) -> str:
    return "".join(random.choices(string.digits, k=length))


def store_otp(db, email: str, otp: str, otp_type: str = "registration",
              expiry_minutes: int = 5) -> ObjectId:
    """
    Insert (or replace) an OTP document for the given email + type.
    Returns the inserted _id.
    """
    # Remove any existing OTPs of the same type for this email
    db.otp_verifications.delete_many({"email": email, "otp_type": otp_type})

    expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)
    doc = {
        "email":      email,
        "otp":        otp,
        "otp_type":   otp_type,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "used":       False,
        "attempts":   0,
    }
    result = db.otp_verifications.insert_one(doc)
    return result.inserted_id


def store_txn_otp(db, transaction_id: str, otp: str, expiry_seconds: int = 60) -> ObjectId:
    """Store a short-lived OTP tied to a specific transaction."""
    db.otp_verifications.delete_many({"transaction_id": transaction_id, "otp_type": "transaction"})
    expires_at = datetime.utcnow() + timedelta(seconds=expiry_seconds)
    doc = {
        "transaction_id": transaction_id,
        "otp":            otp,
        "otp_type":       "transaction",
        "created_at":     datetime.utcnow(),
        "expires_at":     expires_at,
        "used":           False,
        "attempts":       0,
    }
    result = db.otp_verifications.insert_one(doc)
    return result.inserted_id


def verify_otp(db, email: str, otp: str, otp_type: str = "registration") -> dict:
    """
    Returns {"valid": True/False, "reason": str}
    """
    doc = db.otp_verifications.find_one({
        "email":    email,
        "otp_type": otp_type,
        "used":     False,
    })
    if not doc:
        return {"valid": False, "reason": "OTP not found or already used."}

    # Increment attempt counter
    db.otp_verifications.update_one(
        {"_id": doc["_id"]},
        {"$inc": {"attempts": 1}}
    )

    if doc.get("attempts", 0) >= 5:
        return {"valid": False, "reason": "Maximum OTP attempts exceeded. Please request a new OTP."}

    if datetime.utcnow() > doc["expires_at"]:
        return {"valid": False, "reason": "OTP has expired. Please request a new one."}

    if doc["otp"] != otp.strip():
        return {"valid": False, "reason": "Incorrect OTP. Please try again."}

    # Mark as used
    db.otp_verifications.update_one({"_id": doc["_id"]}, {"$set": {"used": True}})
    return {"valid": True, "reason": "OTP verified successfully."}


def verify_txn_otp(db, transaction_id: str, otp: str) -> dict:
    doc = db.otp_verifications.find_one({
        "transaction_id": transaction_id,
        "otp_type":       "transaction",
        "used":           False,
    })
    if not doc:
        return {"valid": False, "reason": "OTP not found or already used."}

    if datetime.utcnow() > doc["expires_at"]:
        # Mark transaction as fraud
        return {"valid": False, "reason": "OTP expired. Transaction flagged as fraud.", "expired": True}

    if doc["otp"] != otp.strip():
        return {"valid": False, "reason": "Incorrect OTP."}

    db.otp_verifications.update_one({"_id": doc["_id"]}, {"$set": {"used": True}})
    return {"valid": True, "reason": "Transaction verified."}
