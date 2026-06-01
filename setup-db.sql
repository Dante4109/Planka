-- Planka Database Setup Script
-- Run this as the PostgreSQL superuser (postgres):
--   psql -U postgres -f setup-db.sql
--
-- To change the password, update both this file and the DATABASE_URL in .env

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'planka') THEN
    CREATE ROLE planka WITH LOGIN PASSWORD '2ZorM7GGUXhkAot5oWUv4Y9t3nxfSXoz';
    RAISE NOTICE 'Role planka created.';
  ELSE
    RAISE NOTICE 'Role planka already exists, skipping creation.';
  END IF;
END
$$;

-- Create the database if it doesn't exist
SELECT 'CREATE DATABASE planka OWNER planka'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'planka')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE planka TO planka;
