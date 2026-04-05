import os
DATABASE_URL = os.getenv("DATABASE_URL",
    f"postgresql://{os.getenv('DB_USER','postgres')}:{os.getenv('DB_PASSWORD','postgres')}"
    f"@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/medaxis_billing")
JWT_SECRET    = os.getenv("JWT_SECRET", "medaxis-change-in-production")
JWT_ALGORITHM = "HS256"
INVENTORY_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8002")
