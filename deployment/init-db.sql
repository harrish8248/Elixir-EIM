-- Initialize PostgreSQL Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "ltree";

-- Create Non-Superuser Application Role for RLS Enforcement
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'elixir_app_role') THEN
        CREATE ROLE elixir_app_role WITH LOGIN PASSWORD 'app_secure_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'elixir_app_user') THEN
        CREATE ROLE elixir_app_user WITH LOGIN PASSWORD 'app_secure_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

-- Grant schema and future table permissions to non-superuser application role
GRANT ALL ON SCHEMA public TO elixir;
GRANT ALL ON SCHEMA public TO elixir_app_role;
GRANT ALL ON SCHEMA public TO elixir_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO elixir_app_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO elixir_app_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO elixir_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO elixir_app_user;
