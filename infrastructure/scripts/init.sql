-- FinSight AI — PostgreSQL initialisation (runs once when the Docker volume is created).
-- Tables are created by the backend on startup (SQLAlchemy metadata.create_all).
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
COMMENT ON DATABASE finsight_db IS 'FinSight AI — financial analytics & intelligence platform';
