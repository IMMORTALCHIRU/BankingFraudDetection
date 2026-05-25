import pandas as pd
import numpy as np
import random
from faker import Faker
from datetime import datetime

fake = Faker("en_IN")

# -----------------------------
# CONFIGURATION
# -----------------------------
NUM_ROWS = 2000
FRAUD_RATIO = 0.50

cities = [
    "Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Chennai",
    "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow",
    "Kochi", "Surat", "Patna", "Noida", "Chandigarh",
    "Hubballi", "Belagavi", "Vijayapura", "Dharwad", "Mysuru", "Udupi", "Manipal", "Shimoga", 
    "Karwar", "Gulbarga", "Raichur", "Bellary", "Bidar", "Bagalkot", "Hassan", "Chitradurga"
]

transaction_types = ["Transfer", "Withdrawal", "Deposit"]

# ---------------------------------
# HELPER FUNCTIONS
# ---------------------------------

def weighted_choice(choices, weights):
    return random.choices(choices, weights=weights, k=1)[0]


def generate_account_age():
    return np.random.randint(10, 1200)


def generate_normal_transaction(avg_amount):
    std_dev = avg_amount * 0.25
    amount = np.random.normal(avg_amount, std_dev)
    return max(500, round(amount, 2))


def generate_fraud_transaction(avg_amount):
    multiplier = np.random.uniform(8, 40)
    return round(avg_amount * multiplier, 2)


def calculate_risk_score(
    transaction_amount,
    avg_transaction,
    txn_freq,
    account_age,
    failed_logins,
    login_hour,
    transactions_today,
    location_changed,
    transaction_type
):
    score = 0

    # -----------------------------
    # Transaction Amount Risk
    # -----------------------------
    ratio = transaction_amount / avg_transaction

    if ratio > 20:
        score += 40
    elif ratio > 10:
        score += 30
    elif ratio > 5:
        score += 20

    # -----------------------------
    # Midnight Activity
    # -----------------------------
    if login_hour >= 0 and login_hour <= 4:
        score += 20

    # -----------------------------
    # High Frequency Transactions
    # -----------------------------
    if txn_freq >= 10:
        score += 25
    elif txn_freq >= 6:
        score += 18
    elif txn_freq >= 4:
        score += 10

    # -----------------------------
    # Failed Logins
    # -----------------------------
    if failed_logins >= 6:
        score += 20
    elif failed_logins >= 3:
        score += 12

    # -----------------------------
    # New Account Risk
    # -----------------------------
    if account_age <= 30:
        score += 15
    elif account_age <= 90:
        score += 8

    # -----------------------------
    # Geolocation Change
    # -----------------------------
    if location_changed:
        score += 15

    # -----------------------------
    # Too Many Daily Transactions
    # -----------------------------
    if transactions_today >= 20:
        score += 18
    elif transactions_today >= 10:
        score += 10

    # -----------------------------
    # Transaction Type Risk
    # -----------------------------
    if transaction_type == "Transfer":
        score += 8
    elif transaction_type == "Withdrawal":
        score += 5

    return min(100, score)


def classify_fraud(score):
    return "Fraud" if score >= 70 else "Normal"


# ---------------------------------
# DATASET GENERATION
# ---------------------------------

dataset = []

for _ in range(NUM_ROWS):

    is_fraud = np.random.rand() < FRAUD_RATIO

    # ---------------------------------
    # Base User Financial Profile
    # ---------------------------------
    avg_transaction_30d = round(
        np.random.randint(2000, 25000),
        2
    )

    account_age_days = generate_account_age()

    # ---------------------------------
    # Fraud vs Normal Logic
    # ---------------------------------

    if is_fraud:

        transaction_amount = generate_fraud_transaction(
            avg_transaction_30d
        )

        transaction_frequency_10min = np.random.randint(5, 12)

        failed_login_attempts = np.random.randint(2, 9)

        login_hour = weighted_choice(
            [0, 1, 2, 3, 4, 23],
            [25, 20, 20, 15, 10, 10]
        )

        transactions_today = np.random.randint(8, 25)

        current_location = random.choice(cities)

        previous_location = random.choice(
            [city for city in cities if city != current_location]
        )

    else:

        transaction_amount = generate_normal_transaction(
            avg_transaction_30d
        )

        transaction_frequency_10min = np.random.randint(1, 4)

        failed_login_attempts = np.random.randint(0, 2)

        login_hour = weighted_choice(
            list(range(7, 23)),
            [1] * 16
        )

        transactions_today = np.random.randint(1, 6)

        current_location = random.choice(cities)

        previous_location = weighted_choice(
            [current_location, random.choice(cities)],
            [90, 10]
        )

    # ---------------------------------
    # Balance Logic
    # ---------------------------------

    if transaction_amount > avg_transaction_30d * 15:
        account_balance = round(
            transaction_amount * np.random.uniform(1.2, 3.0),
            2
        )
    else:
        account_balance = round(
            avg_transaction_30d * np.random.uniform(8, 30),
            2
        )

    # ---------------------------------
    # Transaction Type Logic
    # ---------------------------------

    if is_fraud:
        transaction_type = weighted_choice(
            ["Transfer", "Withdrawal"],
            [80, 20]
        )
    else:
        transaction_type = weighted_choice(
            ["Transfer", "Withdrawal", "Deposit"],
            [50, 20, 30]
        )

    # ---------------------------------
    # Time Formatting
    # ---------------------------------

    minute = np.random.randint(0, 60)

    transaction_time = f"{login_hour:02d}:{minute:02d}"

    # ---------------------------------
    # Risk Score
    # ---------------------------------

    location_changed = current_location != previous_location

    risk_score = calculate_risk_score(
        transaction_amount,
        avg_transaction_30d,
        transaction_frequency_10min,
        account_age_days,
        failed_login_attempts,
        login_hour,
        transactions_today,
        location_changed,
        transaction_type
    )

    fraud_label = classify_fraud(risk_score)

    # ---------------------------------
    # Final Row
    # ---------------------------------

    row = {
        "transaction_time": transaction_time,
        "transaction_amount": round(transaction_amount, 2),
        "avg_transaction_30d": avg_transaction_30d,
        "transaction_frequency_10min": transaction_frequency_10min,
        "current_location": current_location,
        "previous_location": previous_location,
        "account_balance": round(account_balance, 2),
        "transaction_type": transaction_type,
        "account_age_days": account_age_days,
        "failed_login_attempts": failed_login_attempts,
        "login_hour": login_hour,
        "transactions_today": transactions_today,
        "risk_score": risk_score,
        "fraud_label": fraud_label
    }

    dataset.append(row)

# ---------------------------------
# CREATE DATAFRAME
# ---------------------------------

df = pd.DataFrame(dataset)

# ---------------------------------
# REMOVE DUPLICATES
# ---------------------------------

df = df.drop_duplicates()

# ---------------------------------
# SAVE DATASET
# ---------------------------------

csv_file = "BankingFraudDetection.csv"
# xlsx_file = "BankingFraudDetection.xlsx"

df.to_csv(csv_file, index=False)
# df.to_excel(xlsx_file, index=False)

# ---------------------------------
# SUMMARY
# ---------------------------------

print("\nDataset Generated Successfully")
print(f"Rows: {len(df)}")
print(f"CSV File: {csv_file}")
# print(f"Excel File: {xlsx_file}")

print("\nFraud Distribution:")
print(df["fraud_label"].value_counts())

print("\nSample Data:")
print(df.head())