import os

SERVICES = {
    "/auth":          os.getenv("AUTH_SERVICE_URL",          "http://auth-service:8001"),
    "/inventory":     os.getenv("INVENTORY_SERVICE_URL",     "http://inventory-service:8002"),
    "/billing":       os.getenv("BILLING_SERVICE_URL",       "http://billing-service:8003"),
    "/replenishment": os.getenv("REPLENISHMENT_SERVICE_URL", "http://replenishment-service:8004"),
    "/reporting":     os.getenv("REPORTING_SERVICE_URL",     "http://reporting-service:8005"),
    "/ai":            os.getenv("AI_SERVICE_URL",            "http://ai-insights-service:8006"),
    "/notifications": os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8007"),
}

RATE_LIMIT    = int(os.getenv("RATE_LIMIT", "100"))
RATE_WINDOW   = int(os.getenv("RATE_WINDOW", "60"))
