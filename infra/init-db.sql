-- MedAxis Platform — PostgreSQL database initialization
-- Creates one database per service (data ownership boundary)

CREATE DATABASE medaxis_auth;
CREATE DATABASE medaxis_inventory;
CREATE DATABASE medaxis_billing;
CREATE DATABASE medaxis_replenishment;
CREATE DATABASE medaxis_ai;
CREATE DATABASE medaxis_notifications;

-- Grant all privileges to the medaxis user
GRANT ALL PRIVILEGES ON DATABASE medaxis_auth TO medaxis;
GRANT ALL PRIVILEGES ON DATABASE medaxis_inventory TO medaxis;
GRANT ALL PRIVILEGES ON DATABASE medaxis_billing TO medaxis;
GRANT ALL PRIVILEGES ON DATABASE medaxis_replenishment TO medaxis;
GRANT ALL PRIVILEGES ON DATABASE medaxis_ai TO medaxis;
GRANT ALL PRIVILEGES ON DATABASE medaxis_notifications TO medaxis;
