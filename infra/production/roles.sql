-- EMPTY DEDICATED CLUSTER ONLY. Never run against the Windows/local primary.
-- psql variables are supplied privately by the operator; never commit real values.
\set ON_ERROR_STOP on
CREATE ROLE pao_migrator LOGIN PASSWORD :'migrator_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE pao_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE :"database" OWNER pao_migrator;
\connect :database
CREATE EXTENSION IF NOT EXISTS vector;
REVOKE ALL ON DATABASE :"database" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"database" TO pao_app, pao_migrator;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO pao_migrator;
GRANT USAGE ON SCHEMA public TO pao_app;
