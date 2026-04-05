import os
BILLING_DB_URL   = os.getenv("BILLING_DB_URL",   f"postgresql://{os.getenv('DB_USER','postgres')}:{os.getenv('DB_PASSWORD','postgres')}@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/medaxis_billing")
INVENTORY_DB_URL = os.getenv("INVENTORY_DB_URL",  f"postgresql://{os.getenv('DB_USER','postgres')}:{os.getenv('DB_PASSWORD','postgres')}@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/medaxis_inventory")
JWT_SECRET = os.getenv("JWT_SECRET","medaxis-change-in-production")
JWT_ALGORITHM = "HS256"
