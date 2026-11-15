-- Dev only. Runs once on first container start (see docker-compose.yml).
-- The API connects as ankana_app (no superuser, no BYPASSRLS) so RLS applies.
-- The Alembic migration grants table privileges to it.
CREATE ROLE ankana_app LOGIN PASSWORD 'ankana_app_dev';
