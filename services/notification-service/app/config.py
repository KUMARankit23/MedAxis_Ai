import os
DATABASE_URL = os.getenv("DATABASE_URL",
    f"postgresql://{os.getenv('DB_USER','postgres')}:{os.getenv('DB_PASSWORD','postgres')}"
    f"@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/medaxis_notifications")
