-- FinSight AI — Database Schema Initialization Script
-- PostgreSQL 16 with pgvector extension

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Ensure clean startup
COMMENT ON DATABASE finsight_db IS 'FinSight AI Financial Analytics & Intelligence Platform Database';
