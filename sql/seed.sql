-- =============================================================================
-- ACM-Helper Seed Data
-- Default user + algorithm tag dictionary
-- Usage: sqlite3 acm_helper.db < seed.sql
-- Prerequisite: schema.sql must be run first
-- =============================================================================

-- Default application user (used for single-user mode)
INSERT OR IGNORE INTO app_users (id, username, email) VALUES (1, '默认用户', '');

-- Algorithm tag dictionary (from TAG_CN mapping)
-- Total: 107 unique Chinese tags

INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '2-SAT');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'A*');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'Ad-hoc');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'BFS');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'BSGS');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'CDQ 分治');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'CRT');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'DFS');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'Dancing Links');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'FFT');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'FWT');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'Floyd');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'KMP');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'LCA');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'LCT');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'Manacher');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'NTT');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'PAM');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'SA');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'SAM');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'ST 表');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'STL');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'Tarjan');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', 'wqs 二分');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '三分');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '主席树');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '二分');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '二分图');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '二次剩余');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '交互');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '位运算');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '倍增');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '凸包');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '分块');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '分治');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '前缀和');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '动态规划');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '区间 DP');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '单调栈');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '单调队列');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '博弈论');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '原根');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '双指针');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '可持久化线段树');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '后缀结构');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '哈希');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '图匹配');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '图论');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '基环树');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '多项式');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '字典树');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '字符串');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '容斥原理');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '差分');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '平衡树');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '并查集');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '强连通分量');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '扫描线');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '折半搜索');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '拓扑排序');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '排序');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '搜索');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '数位 DP');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '数学');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '数据结构');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '数论');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '斜率维护技巧');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '暴力枚举');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '最小割');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '最短路');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '期望');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '构造');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '树');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '树剖');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '树形 DP');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '树状数组');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '树的直径');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '树链剖分');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '概率');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '模拟');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '欧拉回路');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '点分治');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '状压 DP');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '生成函数');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '生成树');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '矩阵');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '矩阵乘法');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '矩阵加速');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '筛法');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '线性基');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '线性规划');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '线段树');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '线段树合并');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '组合数学');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '网络流');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '背包 DP');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '莫队');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '虚树');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '表达式解析');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '计算几何');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '调度');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '贪心');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '费用流');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '逆元');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '逆序对');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '随机化');
INSERT OR IGNORE INTO tags (name_en, name_cn) VALUES ('', '高斯消元');