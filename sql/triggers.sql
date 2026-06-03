-- =============================================================================
-- ACM-Helper Database Triggers (2)
-- Usage: sqlite3 acm_helper.db < triggers.sql
-- Prerequisite: schema.sql must be run first
-- =============================================================================

-- =============================================================================
-- TRIGGER 1: trg_app_users_updated_at
-- Automatically update the updated_at timestamp whenever an app_users row is modified
-- =============================================================================
CREATE TRIGGER IF NOT EXISTS trg_app_users_updated_at
AFTER UPDATE ON app_users
FOR EACH ROW
BEGIN
    UPDATE app_users SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- =============================================================================
-- TRIGGER 2: trg_platform_accounts_updated_at
-- Automatically update the updated_at timestamp whenever a platform_accounts row is modified
-- =============================================================================
CREATE TRIGGER IF NOT EXISTS trg_platform_accounts_updated_at
AFTER UPDATE ON platform_accounts
FOR EACH ROW
BEGIN
    UPDATE platform_accounts SET updated_at = datetime('now') WHERE id = NEW.id;
END;
