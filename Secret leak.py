# app_config.py
# WARNING: This file contains dummy data for testing scanning tools.

# Simulated AWS Credentials (Invalid/Fake structure)
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# Simulated Third-Party API Token (Invalid/Fake structure)
STRIPE_API_KEY = "sk_test_51NxF2B2ePTwWusMzL8oExampleTokenNotReal00Xyz"

# Simulated Database Connection String (Invalid/Fake structure)
DATABASE_URL = "postgresql://db_admin:P@ssword2026!@localhost:5432/production_db"

def connect_services():
    print(f"Initializing connection with AWS Key: {AWS_ACCESS_KEY_ID}")
    print(f"Initializing Stripe client with key prefix: {STRIPE_API_KEY[:7]}")

if __name__ == "__main__":
    connect_services()