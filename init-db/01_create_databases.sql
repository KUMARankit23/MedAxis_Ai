-- MedAxis Platform — PostgreSQL database initialisation
-- Creates one database per service (strict data ownership boundary)
-- Uses IF NOT EXISTS to be idempotent (safe to run multiple times)

SELECT 'CREATE DATABASE medaxis_auth'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'medaxis_auth')\gexec

SELECT 'CREATE DATABASE medaxis_inventory'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'medaxis_inventory')\gexec

SELECT 'CREATE DATABASE medaxis_billing'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'medaxis_billing')\gexec

SELECT 'CREATE DATABASE medaxis_replenishment'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'medaxis_replenishment')\gexec

SELECT 'CREATE DATABASE medaxis_reporting'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'medaxis_reporting')\gexec

SELECT 'CREATE DATABASE medaxis_ai'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'medaxis_ai')\gexec

SELECT 'CREATE DATABASE medaxis_notifications'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'medaxis_notifications')\gexec

GRANT ALL PRIVILEGES ON DATABASE medaxis_auth          TO postgres;
GRANT ALL PRIVILEGES ON DATABASE medaxis_inventory     TO postgres;
GRANT ALL PRIVILEGES ON DATABASE medaxis_billing       TO postgres;
GRANT ALL PRIVILEGES ON DATABASE medaxis_replenishment TO postgres;
GRANT ALL PRIVILEGES ON DATABASE medaxis_reporting     TO postgres;
GRANT ALL PRIVILEGES ON DATABASE medaxis_ai            TO postgres;
GRANT ALL PRIVILEGES ON DATABASE medaxis_notifications TO postgres;
