-- Run as schema-owning pao_migrator, after reviewed migrations, not app startup.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pao_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pao_app;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.alembic_version FROM pao_app;
ALTER DEFAULT PRIVILEGES FOR ROLE pao_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pao_app;
ALTER DEFAULT PRIVILEGES FOR ROLE pao_migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO pao_app;
