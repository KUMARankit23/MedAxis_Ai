"""Auth Service — configuration from environment variables."""
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('DB_USER','postgres')}:{os.getenv('DB_PASSWORD','postgres')}"
    f"@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/medaxis_auth"
)

JWT_SECRET          = os.getenv("JWT_SECRET", "medaxis-change-in-production")
JWT_ALGORITHM       = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_HOURS  = int(os.getenv("REFRESH_TOKEN_HOURS", "8"))
