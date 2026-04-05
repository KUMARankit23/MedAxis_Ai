import os
DATABASE_URL = os.getenv("DATABASE_URL",
    f"postgresql://{os.getenv('DB_USER','postgres')}:{os.getenv('DB_PASSWORD','postgres')}"
    f"@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/medaxis_ai")
JWT_SECRET    = os.getenv("JWT_SECRET","medaxis-change-in-production")
JWT_ALGORITHM = "HS256"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY","")
AI_PROVIDER    = os.getenv("AI_PROVIDER","pattern")  # pattern | openai | groq
