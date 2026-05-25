"""Email service — registration OTP, security alerts, transaction alerts."""

import socket
from datetime import datetime
from flask import current_app, request
from flask_mail import Message

# Import the mail singleton lazily to avoid circular imports
def _mail():
    from app import mail
    return mail


def _get_device_info():
    ua = request.headers.get("User-Agent", "Unknown")
    return ua[:120]


def _get_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "Unknown")


def send_registration_otp(user_name: str, email: str, otp: str, ip: str = None):
    """Send OTP email after registration."""
    ip = ip or _get_ip()
    device = _get_device_info()
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    subject = "🔐 BankGuard — Verify Your Account"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;background:#f4f7fb;padding:30px;border-radius:12px;">
      <div style="background:linear-gradient(135deg,#1a2e5a,#2d6a9f);padding:25px;border-radius:10px 10px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:26px;">🏦 BankGuard</h1>
        <p style="color:#a8d4f5;margin:5px 0 0;">Fraud Detection &amp; Security Platform</p>
      </div>
      <div style="background:#fff;padding:30px;border-radius:0 0 10px 10px;">
        <h2 style="color:#1a2e5a;">Hello, {user_name}!</h2>
        <p style="color:#555;">Thank you for registering with <strong>BankGuard</strong>. Use the OTP below to verify your account.</p>

        <div style="background:#f0f8ff;border:2px dashed #2d6a9f;border-radius:10px;padding:25px;text-align:center;margin:20px 0;">
          <p style="margin:0;color:#777;font-size:14px;">Your One-Time Password</p>
          <h1 style="color:#1a2e5a;font-size:48px;letter-spacing:12px;margin:10px 0;">{otp}</h1>
          <p style="margin:0;color:#e74c3c;font-size:13px;">⏳ Valid for 5 minutes only</p>
        </div>

        <div style="background:#fff8e1;border-left:4px solid #f39c12;padding:15px;border-radius:5px;margin:20px 0;">
          <h4 style="margin:0 0 10px;color:#e67e22;">📋 Session Details</h4>
          <table style="width:100%;font-size:13px;color:#555;">
            <tr><td style="padding:4px 0;">🕐 Time:</td><td><strong>{now}</strong></td></tr>
            <tr><td style="padding:4px 0;">🌐 IP Address:</td><td><strong>{ip}</strong></td></tr>
            <tr><td style="padding:4px 0;">💻 Device:</td><td><strong>{device[:80]}</strong></td></tr>
          </table>
        </div>

        <div style="background:#ffeaea;border-left:4px solid #e74c3c;padding:12px;border-radius:5px;">
          <strong style="color:#c0392b;">⚠️ Security Warning:</strong>
          <p style="margin:5px 0 0;color:#888;font-size:13px;">Never share this OTP with anyone. BankGuard will never ask for your OTP via phone or chat.</p>
        </div>
      </div>
      <p style="text-align:center;color:#aaa;font-size:12px;margin-top:15px;">© 2024 BankGuard Security Platform. All rights reserved.</p>
    </div>
    """
    _send(email, subject, html)


def send_login_alert(user_name: str, email: str, ip: str = None, browser: str = None, location: str = "Unknown"):
    """Security email on successful login."""
    ip = ip or _get_ip()
    browser = browser or _get_device_info()
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    subject = "🔔 BankGuard — New Login Detected"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;background:#f4f7fb;padding:30px;border-radius:12px;">
      <div style="background:linear-gradient(135deg,#1a2e5a,#2d6a9f);padding:25px;border-radius:10px 10px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;">🏦 BankGuard</h1>
      </div>
      <div style="background:#fff;padding:30px;border-radius:0 0 10px 10px;">
        <h2 style="color:#1a2e5a;">Hello, {user_name}!</h2>
        <p>A new login was detected on your account.</p>
        <div style="background:#e8f5e9;border-left:4px solid #27ae60;padding:15px;border-radius:5px;margin:15px 0;">
          <table style="width:100%;font-size:14px;color:#555;">
            <tr><td>🕐 Time:</td><td><strong>{now}</strong></td></tr>
            <tr><td>🌐 IP:</td><td><strong>{ip}</strong></td></tr>
            <tr><td>💻 Browser:</td><td><strong>{browser[:80]}</strong></td></tr>
            <tr><td>📍 Location:</td><td><strong>{location}</strong></td></tr>
          </table>
        </div>
        <p style="color:#e74c3c;font-size:13px;">If this wasn't you, please <a href="#" style="color:#2d6a9f;">contact support immediately</a>.</p>
      </div>
    </div>
    """
    _send(email, subject, html)


def send_password_reset_otp(user_name: str, email: str, otp: str):
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")
    subject = "🔑 BankGuard — Password Reset OTP"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;background:#f4f7fb;padding:30px;border-radius:12px;">
      <div style="background:linear-gradient(135deg,#1a2e5a,#2d6a9f);padding:25px;border-radius:10px 10px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;">🏦 BankGuard</h1>
      </div>
      <div style="background:#fff;padding:30px;border-radius:0 0 10px 10px;">
        <h2 style="color:#1a2e5a;">Password Reset — {user_name}</h2>
        <p>Use the OTP below to reset your password.</p>
        <div style="background:#f0f8ff;border:2px dashed #2d6a9f;border-radius:10px;padding:25px;text-align:center;margin:20px 0;">
          <h1 style="color:#1a2e5a;font-size:48px;letter-spacing:12px;margin:10px 0;">{otp}</h1>
          <p style="margin:0;color:#e74c3c;font-size:13px;">⏳ Valid for 5 minutes</p>
        </div>
        <p style="color:#aaa;font-size:12px;">Requested at {now}. If you didn't request this, ignore this email.</p>
      </div>
    </div>
    """
    _send(email, subject, html)


def send_suspicious_transaction_alert(user_name: str, email: str,
                                       txn_data: dict, otp: str, admin_email: str = None):
    """Send OTP + details for a suspicious transaction — to user AND admin."""
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")
    amount     = f"₹{txn_data.get('amount', 0):,.2f}"
    receiver   = txn_data.get("receiver_name", "Unknown")
    risk_score = txn_data.get("risk_score", 0)
    confidence = txn_data.get("confidence", 0)
    prediction = txn_data.get("fraud_prediction", "Suspicious")
    ip         = txn_data.get("ip", "Unknown")
    device     = txn_data.get("device", "Unknown")[:80]

    subject = "🚨 BankGuard — Suspicious Transaction Alert"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;background:#fff8f8;padding:30px;border-radius:12px;">
      <div style="background:linear-gradient(135deg,#c0392b,#e74c3c);padding:25px;border-radius:10px 10px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;">⚠️ SUSPICIOUS TRANSACTION</h1>
        <p style="color:#ffc9c9;margin:5px 0 0;">BankGuard Fraud Detection</p>
      </div>
      <div style="background:#fff;padding:30px;border-radius:0 0 10px 10px;">
        <h2 style="color:#c0392b;">Hello, {user_name}!</h2>
        <p>A suspicious transaction has been flagged on your account. An OTP is required to proceed.</p>

        <div style="background:#ffeaea;border:2px solid #e74c3c;border-radius:10px;padding:20px;margin:15px 0;">
          <table style="width:100%;font-size:14px;color:#555;">
            <tr><td>💰 Amount:</td><td><strong style="color:#c0392b;">{amount}</strong></td></tr>
            <tr><td>👤 Receiver:</td><td><strong>{receiver}</strong></td></tr>
            <tr><td>🕐 Time:</td><td><strong>{now}</strong></td></tr>
            <tr><td>⚠️ Risk Score:</td><td><strong style="color:#e74c3c;">{risk_score:.1f}/100</strong></td></tr>
            <tr><td>🎯 Confidence:</td><td><strong>{confidence:.1f}%</strong></td></tr>
            <tr><td>🔍 Prediction:</td><td><strong>{prediction}</strong></td></tr>
            <tr><td>🌐 IP Address:</td><td><strong>{ip}</strong></td></tr>
            <tr><td>💻 Device:</td><td><strong>{device}</strong></td></tr>
          </table>
        </div>

        <div style="background:#f0f8ff;border:2px dashed #2d6a9f;border-radius:10px;padding:20px;text-align:center;margin:15px 0;">
          <p style="margin:0;color:#777;">Transaction Verification OTP</p>
          <h1 style="color:#1a2e5a;font-size:48px;letter-spacing:12px;margin:10px 0;">{otp}</h1>
          <p style="margin:0;color:#e74c3c;font-size:13px;">⏳ Valid for 60 seconds only!</p>
        </div>
        <p style="color:#888;font-size:13px;">If you did not initiate this, your account may be compromised. Contact support immediately.</p>
      </div>
    </div>
    """
    _send(email, subject, html)
    if admin_email:
        admin_subject = f"🚨 [ADMIN ALERT] Suspicious Transaction — {user_name}"
        _send(admin_email, admin_subject, html)


def send_transaction_confirmation(user_name: str, email: str, txn_data: dict):
    """Confirmation email after successful transaction."""
    now    = datetime.now().strftime("%d %b %Y, %I:%M %p")
    amount = f"₹{txn_data.get('amount', 0):,.2f}"
    subject = "✅ BankGuard — Transaction Successful"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;background:#f4f7fb;padding:30px;border-radius:12px;">
      <div style="background:linear-gradient(135deg,#1a6e3c,#27ae60);padding:25px;border-radius:10px 10px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;">✅ Transaction Successful</h1>
      </div>
      <div style="background:#fff;padding:30px;border-radius:0 0 10px 10px;">
        <h2 style="color:#1a6e3c;">Hello, {user_name}!</h2>
        <p>Your transaction of <strong>{amount}</strong> has been processed successfully.</p>
        <div style="background:#e8f5e9;border-left:4px solid #27ae60;padding:15px;border-radius:5px;">
          <table style="width:100%;font-size:14px;color:#555;">
            <tr><td>💰 Amount:</td><td><strong>{amount}</strong></td></tr>
            <tr><td>👤 Receiver:</td><td><strong>{txn_data.get('receiver_name','—')}</strong></td></tr>
            <tr><td>📋 Type:</td><td><strong>{txn_data.get('transaction_type','—')}</strong></td></tr>
            <tr><td>🕐 Time:</td><td><strong>{now}</strong></td></tr>
            <tr><td>🆔 Ref ID:</td><td><strong>{txn_data.get('txn_id','—')}</strong></td></tr>
          </table>
        </div>
      </div>
    </div>
    """
    _send(email, subject, html)


def _send(to: str, subject: str, html: str):
    """Internal helper to send an email (silently skips on error)."""
    try:
        m = Message(subject=subject, recipients=[to], html=html)
        _mail().send(m)
    except Exception as exc:
        current_app.logger.warning(f"[EmailService] Failed to send to {to}: {exc}")
