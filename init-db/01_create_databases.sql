-- MedAxis Platform — PostgreSQL database initialisation
-- Creates one database per service (strict data ownership boundary)

CREATE DATABASE medaxis_auth;
CREATE DATABASE medaxis_inventory;
CREATE DATABASE medaxis_billing;
CREATE DATABASE medaxis_replenishment;
CREATE DATABASE medaxis_ai;
CREATE DATABASE medaxis_notifications;

GRANT ALL PRIVILEGES ON DATABASE medaxis_auth          TO postgres;
GRANT ALL PRIVILEGES ON DATABASE medaxis_inventory     TO postgres;
GRANT ALL PRIVILEGES ON DATABASE medaxis_billing       TO postgres;
GRANT ALL PRIVILEGES ON DATABASE medaxis_replenishment TO postgres;
GRANT ALL PRIVILEGES ON DATABASE medaxis_ai            TO postgres;
GRANT ALL PRIVILEGES ON DATABASE medaxis_notifications TO postgres;
