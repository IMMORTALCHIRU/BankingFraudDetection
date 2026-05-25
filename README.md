# BankGuard — ML-Powered Banking Fraud Detection System

A complete enterprise-grade web application for detecting fraudulent banking transactions using machine learning, built with Flask, MongoDB, and modern responsive UI.

## 🎯 Features

### 12 Complete Modules
1. **Public Home Page** — Landing page with ML security explanation
2. **User Authentication** — Registration, login, logout, password reset
3. **OTP Email Verification** — 2FA via Gmail SMTP for registration & transactions
4. **User Dashboard** — Analytics dashboard with transaction charts
5. **Transaction Management** — Deposit, transfer, withdrawal with history & CSV export
6. **Fraud Detection Engine** — Real-time ML predictions (RandomForest + XGBoost)
7. **Admin Panel** — Full system analytics and user management
8. **Complaint Management** — User complaints with admin replies
9. **Feedback Management** — Transaction feedback with star ratings
10. **Alerts & Notifications** — Real-time fraud alert system
11. **Analytics & Reporting** — Monthly trends, fraud statistics, user growth
12. **Profile Management** — Edit profile, change password, login history

### 🤖 ML Features
- **Fraud Classification**: RandomForest with 100% accuracy on training data
- **Risk Scoring**: XGBoost regression with 0.996 R² score
- **Real-time Prediction**: Automatic fraud analysis on every transaction
- **Smart Encoding**: Handles unknown categorical values from production data
- **12 ML Features**: Transaction time, amount, location, account metrics, etc.

### 🔒 Security
- Flask-Login with session management
- CSRF protection on all forms
- Password hashing with Werkzeug
- MongoDB indexes for performance
- Admin role-based access control
- Failed login attempt tracking

### 🎨 UI/UX
- Bootstrap 5 responsive design
- Chart.js for analytics visualization
- Modern gradient cards and animations
- Mobile-friendly interface
- Toast notifications for user feedback

## 📋 Prerequisites

- **Python** 3.11+
- **MongoDB** 8.0+ (local or remote)
- **Gmail account** for email verification

## 🚀 Setup

### 1. Clone & Install

```bash
cd /Users/chiranjeevichandrasekhark/Desktop/BankingFraudDetection
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file (already exists with defaults):
```env
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=True

MONGO_URI=mongodb://localhost:27017/
MONGO_DB=BankingFraudDB

SECRET_KEY=your-secret-key-here
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
```

### 3. Start MongoDB

```bash
# macOS with Homebrew
brew services start mongodb-community

# Or manually
mongod --dbpath /usr/local/var/mongodb
```

### 4. Run the App

```bash
python app.py
```

The app will start at `http://localhost:5000`

## 👤 Default Credentials

**Admin User:**
- Email: `bhavanimutagar7@gmail.com`
- Password: `Admin@123`

**Note**: This user is automatically created on first app startup.

## 📁 Project Structure

```
BankingFraudDetection/
├── app.py                    # Flask factory & app initialization
├── config.py                 # Configuration settings
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
│
├── services/                 # Business logic
│   ├── fraud_engine.py       # ML model loading & prediction
│   ├── email_service.py      # Email sending via Gmail SMTP
│   └── otp_service.py        # OTP generation & verification
│
├── routes/                   # Flask blueprints
│   ├── auth.py              # Authentication (login, register, reset)
│   ├── dashboard.py         # User dashboard
│   ├── transactions.py      # Transaction management
│   ├── admin.py             # Admin panel
│   ├── complaints.py        # Complaint handling
│   └── profile.py           # User profile management
│
├── templates/               # HTML templates (26 files)
│   ├── base.html            # Base template with navbar
│   ├── home.html            # Landing page
│   ├── auth/                # Login, register, password reset forms
│   ├── user/                # Dashboard, transactions, profile
│   ├── admin/               # Admin dashboards & management
│   └── errors/              # 404, 403, 500 error pages
│
├── static/                  # Static files
│   ├── css/
│   │   ├── main.css         # Global styling
│   │   └── dashboard.css    # Dashboard-specific styles
│   └── js/
│       └── main.js          # Toggle password, counters, scroll effects
│
└── training/                # ML models & preprocessing
    ├── BankingFraudDetection.ipynb    # Training notebook
    ├── dataset.py           # Data generation
    └── models/              # Pre-trained ML models
        ├── BestFraudClassificationModel.pkl
        ├── BestRiskScorePredictionModel.pkl
        ├── FraudDetectionPreprocessor.pkl
        └── model_metadata.json
```

## 🗄️ Database Schema

**Collections:**
- `users` — User accounts with balance & settings
- `transactions` — Transaction records with fraud predictions
- `fraud_alerts` — Triggered fraud alerts
- `otp_verifications` — Registration OTP storage
- `login_history` — Login attempts tracking
- `notifications` — User notifications
- `complaints` — User complaints
- `feedbacks` — Transaction feedback
- `admin_logs` — Admin actions log

## 🔄 Login Flow

1. User enters email & password
2. Password verified against hashed value
3. Login attempt tracked
4. Session created with Flask-Login
5. Redirected to dashboard on success

## 💳 Transaction Flow

1. User initiates deposit/transfer/withdrawal
2. ML fraud detection runs automatically
3. If normal: transaction approved, balance updated
4. If suspicious/high-value: OTP verification required
5. Transaction recorded with fraud prediction
6. User receives confirmation email
7. Data stored in MongoDB with timestamp

## 📊 ML Prediction Features

**12 Features Used:**
1. `transaction_time` — HH:MM format (time-based patterns)
2. `transaction_amount` — Transaction value
3. `avg_transaction_30d` — Average transaction in 30 days
4. `transaction_frequency_10min` — Transactions in last 10 minutes
5. `current_location` — City (31 cities supported)
6. `previous_location` — Previous transaction city
7. `account_balance` — Current balance
8. `transaction_type` — Deposit/Transfer/Withdrawal
9. `account_age_days` — Days since account creation
10. `failed_login_attempts` — Recent failed logins
11. `login_hour` — Hour of login (0-23)
12. `transactions_today` — Daily transaction count

**Supported Cities (31):**
Bengaluru, Mumbai, Delhi, Hyderabad, Chennai, Pune, Kolkata, Ahmedabad, Jaipur, Lucknow, Kochi, Surat, Patna, Noida, Chandigarh, Hubballi, Belagavi, Vijayapura, Dharwad, Mysuru, Udupi, Manipal, Shimoga, Karwar, Gulbarga, Raichur, Bellary, Bidar, Bagalkot, Hassan, Chitradurga

## 🧪 Testing

```bash
# Test app initialization
python -c "from app import create_app, get_db; app = create_app(); print('✓ App OK')"

# Test MongoDB connection
python -c "from pymongo import MongoClient; MongoClient('mongodb://localhost:27017/').admin.command('ping'); print('✓ MongoDB OK')"
```

## 📧 Email Configuration

Gmail SMTP is pre-configured. To use a different email provider:

1. Update `MAIL_SERVER` & `MAIL_PORT` in `.env`
2. Generate app-specific password (not your Gmail password)
3. Update `MAIL_USERNAME` & `MAIL_PASSWORD`

**Gmail App Password:**
1. Enable 2-Step Verification
2. Go to myaccount.google.com/apppasswords
3. Generate new app password
4. Copy to `MAIL_PASSWORD` in `.env`

## 🐛 Troubleshooting

### MongoDB Connection Failed
```
✗ Error: [Errno 111] Connection refused

Solution:
1. Check if MongoDB is running: pgrep mongod
2. Start MongoDB: brew services start mongodb-community
3. Verify connection: mongo localhost:27017
```

### AttributeError: 'NoneType' object has no attribute 'users'
```
Solution:
1. Ensure MongoDB is running
2. Check MONGO_URI in .env
3. Restart the app: python app.py
```

### Email Not Sending
```
Solution:
1. Verify Gmail app password (not regular password)
2. Check MAIL_USERNAME & MAIL_PASSWORD in .env
3. Ensure 2-Step Verification is enabled on Gmail
4. Check Flask-Mail logs in app console
```

## 📈 Performance Notes

- **ML Prediction**: ~50ms per transaction
- **Database Query**: Indexed for <10ms response
- **OTP Verification**: 5 min expiry for registration, 60 sec for transactions
- **Session Timeout**: Configurable in Flask-Login
- **Max Failed Logins**: 5 attempts triggers account freeze

## 🔐 Security Best Practices

1. **Production Deployment:**
   - Set `FLASK_ENV=production`
   - Use strong `SECRET_KEY` (min 32 chars)
   - Enable HTTPS
   - Use MongoDB Atlas with auth
   - Hide `.env` file

2. **Database Backups:**
   ```bash
   mongodump --db BankingFraudDB --out ./backup
   mongorestore --db BankingFraudDB ./backup/BankingFraudDB
   ```

3. **Monitoring:**
   - Check login_history for suspicious patterns
   - Monitor fraud_alerts for trends
   - Review admin_logs for unauthorized access

## 📝 License

This is a demonstration project for educational purposes.

## 📞 Support

For issues or questions:
1. Check troubleshooting section above
2. Verify MongoDB is running
3. Check `.env` configuration
4. Review app logs in terminal

---

**Built with:** Flask • MongoDB • scikit-learn • XGBoost • Bootstrap 5 • Chart.js
