-- =============================================================================
-- ACM-Helper Complete Database Setup
-- Run everything in one command:
--   sqlite3 acm_helper.db < all.sql
--
-- Or step by step:
--   sqlite3 acm_helper.db < schema.sql
--   sqlite3 acm_helper.db < views.sql
--   sqlite3 acm_helper.db < triggers.sql
--   sqlite3 acm_helper.db < seed.sql
-- =============================================================================

-- ===== SCHEMA: 7 tables + indexes =====
.read schema.sql

-- ===== VIEWS: 3 views for stats/weakness/activity =====
.read views.sql

-- ===== TRIGGERS: 2 auto-update triggers =====
.read triggers.sql

-- ===== SEED DATA: default user + tag dictionary =====
.read seed.sql
