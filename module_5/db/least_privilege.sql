-- Run as an admin account, after db/schema.sql:
--   psql -d gradcafe -f db/least_privilege.sql
-- Then set the password inside psql so it never lands in a file:
--   \password gradcafe_app

-- Login only. Not a superuser, cannot create databases or roles.
CREATE ROLE gradcafe_app WITH LOGIN
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

-- Only this database may be opened.
REVOKE ALL ON DATABASE gradcafe FROM PUBLIC;
GRANT CONNECT ON DATABASE gradcafe TO gradcafe_app;

-- The role can see the schema but not create objects in it.
GRANT USAGE ON SCHEMA public TO gradcafe_app;
REVOKE CREATE ON SCHEMA public FROM gradcafe_app;

-- The analysis page reads. Pull Data adds new rows. Nothing else is needed.
-- No UPDATE, DELETE, TRUNCATE, or ownership, so no DROP or ALTER either.
GRANT SELECT, INSERT ON TABLE applicants TO gradcafe_app;
