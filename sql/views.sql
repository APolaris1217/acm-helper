-- =============================================================================
-- ACM-Helper Database Views (3)
-- Usage: sqlite3 acm_helper.db < views.sql
-- Prerequisite: schema.sql must be run first
-- =============================================================================

-- =============================================================================
-- VIEW 1: v_user_submission_stats
-- Per-user, per-platform aggregate submission statistics
-- Used by: /api/v3/stats/user/{id}
-- =============================================================================
CREATE VIEW IF NOT EXISTS v_user_submission_stats AS
SELECT
    pa.app_user_id,
    pa.platform,
    pa.username AS oj_username,
    COUNT(DISTINCT s.id)                                                      AS total_submissions,
    COUNT(DISTINCT CASE WHEN s.result = 'AC' THEN s.problem_id END)           AS ac_problems,
    ROUND(
        CAST(COUNT(DISTINCT CASE WHEN s.result = 'AC' THEN s.problem_id END) AS REAL)
        / NULLIF(COUNT(DISTINCT s.problem_id), 0) * 100, 1
    )                                                                         AS ac_rate_pct,
    COUNT(DISTINCT CASE WHEN s.submit_time != ''
        THEN SUBSTR(s.submit_time, 1, 10) END)                                AS active_days,
    MAX(s.submit_time)                                                        AS last_submit,
    MIN(s.submit_time)                                                        AS first_submit
FROM platform_accounts pa
LEFT JOIN submissions s ON s.platform_account_id = pa.id
GROUP BY pa.app_user_id, pa.platform, pa.username;

-- =============================================================================
-- VIEW 2: v_tag_weakness_ranking
-- Tag-level weakness analysis: for each user, for each algorithm tag,
-- compute AC rate, average difficulty, and error distribution
-- Used by: /api/v3/stats/weakness/{id}
-- =============================================================================
CREATE VIEW IF NOT EXISTS v_tag_weakness_ranking AS
SELECT
    pa.app_user_id,
    pa.platform,
    t.name_cn                                                                  AS tag_name,
    t.name_en                                                                  AS tag_en,
    COUNT(DISTINCT s.problem_id)                                                AS problems_attempted,
    COUNT(DISTINCT CASE WHEN s.result = 'AC' THEN s.problem_id END)             AS problems_ac,
    ROUND(
        CAST(COUNT(DISTINCT CASE WHEN s.result = 'AC' THEN s.problem_id END) AS REAL)
        / NULLIF(COUNT(DISTINCT s.problem_id), 0), 4
    )                                                                           AS ac_rate,
    ROUND(AVG(p.difficulty), 0)                                                 AS avg_difficulty,
    COUNT(DISTINCT CASE WHEN s.result = 'WA'  THEN s.id END)                    AS wa_count,
    COUNT(DISTINCT CASE WHEN s.result = 'TLE' THEN s.id END)                    AS tle_count,
    COUNT(DISTINCT CASE WHEN s.result = 'RE'  THEN s.id END)                    AS re_count
FROM tags t
JOIN problem_tags pt   ON pt.tag_id = t.id
JOIN problems p        ON p.id = pt.problem_id
JOIN submissions s     ON s.problem_id = p.id
JOIN platform_accounts pa ON pa.id = s.platform_account_id
GROUP BY pa.app_user_id, pa.platform, t.id
HAVING COUNT(DISTINCT s.problem_id) >= 3;    -- filter noise: >= 3 problems for this tag

-- =============================================================================
-- VIEW 3: v_daily_activity
-- Daily submission counts and AC counts, per user per platform
-- Used by: /api/v3/stats/activity/{id}
-- =============================================================================
CREATE VIEW IF NOT EXISTS v_daily_activity AS
SELECT
    pa.app_user_id,
    pa.platform,
    SUBSTR(s.submit_time, 1, 10)                                               AS submit_date,
    COUNT(*)                                                                    AS total_subs,
    SUM(CASE WHEN s.result = 'AC' THEN 1 ELSE 0 END)                            AS ac_subs
FROM submissions s
JOIN platform_accounts pa ON pa.id = s.platform_account_id
WHERE s.submit_time != ''
GROUP BY pa.app_user_id, pa.platform, SUBSTR(s.submit_time, 1, 10);
