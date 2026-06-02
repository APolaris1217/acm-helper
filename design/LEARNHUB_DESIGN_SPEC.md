# LearnHub 设计规范

> 基于截图解析 + Claymorphism 风格 | 用于 ACM Helper 全站改版

---

## 1. 配色体系

### 主色板

| 角色 | 色值 | CSS 变量 | 用途 |
|---|---|---|---|
| 主绿 | `#32c258` | `--color-primary` | 主按钮、进度条、强调文字 |
| 深绿 | `#28a348` | `--color-primary-hover` | 按钮悬停、激活态 |
| 浅绿 | `#d4f5dd` | `--color-primary-light` | 标签背景、浅色区块 |
| 浅蓝 | `#b2d7e8` | `--color-accent-blue` | 次要按钮、信息卡片 |
| 浅粉 | `#f9cdc2` | `--color-accent-pink` | 徽章、特殊标签 |
| 背景米白 | `#fff8f0` | `--color-background` | 页面主背景 |
| 纯白 | `#ffffff` | `--color-surface` | 卡片、容器背景 |
| 文字深灰 | `#2a303c` | `--color-foreground` | 标题、正文 |
| 次要文字 | `#6b7280` | `--color-muted` | 辅助说明、水印 |
| 描边黑 | `#2a303c` | `--color-border` | 全局粗描边（核心特征） |

### 语义色

| 角色 | 色值 | 用途 |
|---|---|---|
| 正确绿 | `#16a34a` | AC 状态、通过率 |
| 错误红 | `#ef4444` | WA/RE 状态、删除按钮 |
| 警告橙 | `#f97316` | TLE 状态、需要加强 |
| 中性灰 | `#94a3b8` | 无数据、禁用态 |

### 等级色（薄弱分析用）

| 等级 | 色值 |
|---|---|
| 严重薄弱 | `#dc2626` |
| 需要加强 | `#f97316` |
| 一般 | `#f59e0b` |
| 掌握较好 | `#10b981` |

---

## 2. 字体系统

### 推荐字体（来自设计引擎）

| 用途 | 字体 | 字重 |
|---|---|---|
| 标题 | **Baloo 2** | 600–700 |
| 正文 | **Comic Neue** | 400 |
| 代码/数据 | JetBrains Mono | 400–500 |

**Google Fonts 引用**（国内用本地回退）：
```css
/* 优先用系统字体回退，Google Fonts 国内不可用 */
--font-heading: 'Baloo 2', 'Comic Sans MS', 'PingFang SC', sans-serif;
--font-body: 'Comic Neue', 'PingFang SC', 'Noto Sans SC', sans-serif;
--font-mono: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
```

### 排版层级

| 层级 | 字号 | 字重 | 行高 | 用途 |
|---|---|---|---|---|
| H1 | 28px | 700 | 1.3 | 页面大标题 |
| H2 | 22px | 700 | 1.3 | 区块标题 |
| H3 | 18px | 600 | 1.4 | 卡片标题 |
| H4 | 16px | 600 | 1.4 | 小标题 |
| Body | 14px | 400 | 1.6 | 正文 |
| Caption | 12px | 400 | 1.5 | 辅助文字、标签 |
| Small | 11px | 400 | 1.4 | 页脚、水印 |

---

## 3. 间距系统（基于 4px 网格）

| Token | 值 | 用途 |
|---|---|---|
| `--space-xs` | 4px | 图标与文字间距 |
| `--space-sm` | 8px | 组件内间距 |
| `--space-md` | 12px | 卡片 padding |
| `--space-lg` | 16px | 区块内间距 |
| `--space-xl` | 24px | 区块间距 |
| `--space-2xl` | 32px | 页面级间距 |
| `--space-3xl` | 48px | 大区块分隔 |

---

## 4. 圆角系统

| Token | 值 | 用途 |
|---|---|---|
| `--radius-sm` | 6px | 标签、徽章、小按钮 |
| `--radius-md` | 10px | 卡片、输入框 |
| `--radius-lg` | 16px | 大卡片、弹窗 |
| `--radius-xl` | 24px | 大按钮、主面板 |
| `--radius-full` | 9999px | 胶囊按钮、进度条 |

---

## 5. 描边系统（Claymorphism 核心特征）

```css
--border-width: 2.5px;          /* 全局粗描边 */
--border-style: solid;
--border-color: #2a303c;        /* 黑色描边 */
--shadow-clay: 0 6px 0 #2a303c; /* Clay 风格立体阴影 */
--shadow-clay-sm: 0 3px 0 #2a303c;
```

**规则**：所有交互元素（按钮、卡片、输入框）必须有粗黑描边 + 底部阴影形成 3D 凸起效果。悬停时阴影内缩，模拟按压感。

---

## 6. 阴影层级

| Token | 值 | 用途 |
|---|---|---|
| `--shadow-sm` | `0 3px 0 #2a303c` | 小按钮、标签 |
| `--shadow-md` | `0 6px 0 #2a303c` | 卡片、大按钮 |
| `--shadow-lg` | `0 8px 0 #2a303c` | 弹窗、主面板 |
| `--shadow-none` | `0 0 0 #2a303c` | 按压态（无阴影） |
| `--shadow-float` | `0 4px 16px rgba(0,0,0,0.12)` | 悬浮元素（徽章、提示框） |

---

## 7. 组件规范

### 7.1 按钮 (Button)

```
┌──────────────────────────┐
│   border: 2.5px solid #2a303c          │
│   background: #32c258                  │
│   color: #fff                          │
│   font-weight: 700                     │
│   font-size: 14px                      │
│   border-radius: 24px (胶囊) / 10px    │
│   padding: 8px 20px                    │
│   box-shadow: 0 3px 0 #2a303c          │
│   cursor: pointer                      │
│                                        │
│   :hover {                              │
│     background: #28a348                │
│     transform: translateY(1px)         │
│     box-shadow: 0 2px 0 #2a303c        │
│   }                                    │
│   :active {                             │
│     transform: translateY(3px)         │
│     box-shadow: none                   │
│   }                                    │
└──────────────────────────┘
```

**变体**：
- `.btn-primary` — 绿底白字
- `.btn-secondary` — 浅蓝 `#b2d7e8` 底 + 深灰字
- `.btn-outline` — 白底 + 粗黑描边
- `.btn-danger` — 红底白字
- `.btn-sm` — 字号 12px，padding 4px 12px

### 7.2 卡片 (Card)

```
┌──────────────────────────────┐
│  border: 2.5px solid #2a303c                   │
│  background: #ffffff                           │
│  border-radius: 16px                           │
│  padding: 20px                                 │
│  box-shadow: 0 6px 0 #2a303c                   │
│  font-family: var(--font-body)                 │
│  transition: transform 0.15s ease              │
│                                                │
│  :hover {                                       │
│    transform: translateY(-2px)                 │
│    box-shadow: 0 8px 0 #2a303c                 │
│  }                                             │
└──────────────────────────────┘
```

### 7.3 进度条 (Progress Bar)

```
┌──────────────────────────────────┐
│  容器:                                  │
│    border: 2.5px solid #2a303c          │
│    background: #fff                     │
│    border-radius: 9999px                │
│    height: 12px (sm) / 20px (md)        │
│    overflow: hidden                     │
│                                         │
│  填充:                                   │
│    background: #32c258                  │
│    height: 100%                         │
│    border-radius: 9999px                │
│    transition: width 0.5s ease          │
│    display: flex; align-items: center   │
│    justify-content: center              │
│    color: #fff; font-size: 11px         │
│    font-weight: 700                     │
└──────────────────────────────────┘
```

### 7.4 徽章 (Badge)

```
┌────────────┐
│  border: 2px solid #2a303c               │
│  border-radius: 9999px                   │
│  padding: 2px 10px                       │
│  font-size: 11px                         │
│  font-weight: 600                        │
│  background: (语义色 浅色版)              │
│  box-shadow: 0 2px 0 #2a303c             │
└────────────┘
```

**变体**：
- `.badge-new` — 粉色 `#f9cdc2` 背景 + `#2a303c` 文字
- `.badge-green` — 浅绿 `#d4f5dd` 背景
- `.badge-blue` — 浅蓝 `#b2d7e8` 背景
- `.badge-level-serious` — 红底白字（严重薄弱）
- `.badge-level-need` — 橙底白字（需要加强）
- `.badge-level-normal` — 黄底深字（一般）
- `.badge-level-good` — 绿底白字（掌握较好）

### 7.5 导航栏 (Navbar)

```
┌──────────────────────────────────────────────┐
│  背景: #ffffff                               │
│  底部边框: 2.5px solid #2a303c               │
│  box-shadow: 0 4px 0 #2a303c                │
│  padding: 0 24px                             │
│  height: 56px                                │
│  display: flex; align-items: center          │
│  position: sticky; top: 0; z-index: 100      │
└──────────────────────────────────────────────┘
```

**导航项**：
- 圆角胶囊按钮，带 `--shadow-sm`
- 激活态：绿底白字 + 无阴影（按压感）
- 图标 + 文字标签
- 间距 4px

### 7.6 侧边栏 (Sidebar)

```
┌──────────────┐
│  背景: #fff8f0                              │
│  右边框: 2.5px solid #2a303c               │
│  宽度: 220px                                │
│  padding: 16px                              │
└──────────────┘
```

### 7.7 悬浮气泡 (Bubble) — 薄弱分析 Top5

```
┌─────────────┐
│  圆形，border-radius: 50%                    │
│  border: 2.5px solid #2a303c               │
│  box-shadow: 0 4px 0 #2a303c               │
│  display: flex; flex-direction: column     │
│  align-items: center; justify-content: center │
│  color: #fff                                │
│  font-weight: 700                           │
│  animation: float 3s ease-in-out infinite   │
└─────────────┘
```

---

## 8. 动画规范

| 类型 | 时长 | 缓动 | 用途 |
|---|---|---|---|
| 按钮悬停 | 150ms | `ease` | transform + box-shadow 过渡 |
| 按钮按压 | 100ms | `ease-in` | scale(0.95) + box-shadow 消失 |
| 卡片悬浮 | 200ms | `ease-out` | translateY(-2px) |
| 进度条填充 | 500ms | `ease-out` | width 过渡 |
| 模态框打开 | 250ms | `cubic-bezier(0.34,1.56,0.64,1)` | scale + opacity |
| 气泡浮动 | 3s | `ease-in-out` | translateY ±6px 循环 |
| 列表交错 | 30–50ms/item | `ease-out` | stagger 入场 |

```css
/* 全局过渡 */
*, *::before, *::after {
  transition: all 0.15s ease;
}

/* 减少动画 */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 9. 完整 CSS 变量定义

```css
:root {
  /* === 主色 === */
  --color-primary: #32c258;
  --color-primary-hover: #28a348;
  --color-primary-light: #d4f5dd;
  --color-accent-blue: #b2d7e8;
  --color-accent-pink: #f9cdc2;
  --color-background: #fff8f0;
  --color-surface: #ffffff;
  --color-foreground: #2a303c;
  --color-muted: #6b7280;

  /* === 语义色 === */
  --color-success: #16a34a;
  --color-error: #ef4444;
  --color-warning: #f97316;
  --color-info: #3b82f6;

  /* === 等级色 === */
  --color-level-serious: #dc2626;
  --color-level-need: #f97316;
  --color-level-normal: #f59e0b;
  --color-level-good: #10b981;

  /* === 字体 === */
  --font-heading: 'Baloo 2', 'Comic Sans MS', 'PingFang SC', sans-serif;
  --font-body: 'Comic Neue', 'PingFang SC', 'Noto Sans SC', sans-serif;
  --font-mono: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;

  /* === 字号 === */
  --text-h1: 28px;
  --text-h2: 22px;
  --text-h3: 18px;
  --text-h4: 16px;
  --text-body: 14px;
  --text-caption: 12px;
  --text-small: 11px;

  /* === 间距 === */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 24px;
  --space-2xl: 32px;
  --space-3xl: 48px;

  /* === 圆角 === */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-xl: 24px;
  --radius-full: 9999px;

  /* === 描边 === */
  --border-width: 2.5px;
  --border-style: solid;
  --border-color: #2a303c;

  /* === 阴影 === */
  --shadow-sm: 0 3px 0 #2a303c;
  --shadow-md: 0 6px 0 #2a303c;
  --shadow-lg: 0 8px 0 #2a303c;
  --shadow-float: 0 4px 16px rgba(0,0,0,0.12);
}
```

---

## 10. 页面布局结构

```
┌─────────────────────────────────────────────┐
│  NAVBAR (sticky)                             │
│  Logo | 首页 | 课程 | 分析 | 关于 | 头像      │
├─────────────────────────────────────────────┤
│  ┌──────┐                                    │
│  │ 新品  │  ← Badge (粉色)                   │
│  └──────┘                                    │
│                                              │
│  ┌──────────────────┐  ┌──────────────────┐ │
│  │  左侧标题文案区    │  │  右侧课程卡片      │ │
│  │  大标题 H1        │  │  ┌──────────────┐ │ │
│  │  副标题           │  │  │ 进度条        │ │ │
│  │  描述文字          │  │  │ 统计数据      │ │ │
│  │  CTA 按钮         │  │  │ 标签          │ │ │
│  │                   │  │  └──────────────┘ │ │
│  └──────────────────┘  └──────────────────┘ │
│                                              │
├─────────────────────────────────────────────┤
│  底部数据统计栏                                │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐               │
│  │ 做题│ │ AC │ │ 连续│ │ 活跃│               │
│  │ 数  │ │ 率 │ │ 打卡│ │ 天数│               │
│  └────┘ └────┘ └────┘ └────┘               │
└─────────────────────────────────────────────┘
```

---

## 11. 改版实施清单

### Phase 1: CSS Token 迁移
- [ ] 替换 `:root` 变量为 LearnHub 配色
- [ ] 更新描边宽度为 2.5px
- [ ] 更新圆角为圆润风格（10-24px）
- [ ] 所有组件 box-shadow 改为 clay 立体阴影

### Phase 2: 组件风格统一
- [ ] 按钮改为胶囊型 + 粗黑描边 + 立体阴影
- [ ] 卡片改为圆角 + 粗黑描边
- [ ] 进度条改为圆角胶囊型
- [ ] 标签/徽章改为圆角 + 描边
- [ ] 气泡改为粗黑描边

### Phase 3: 布局优化
- [ ] 侧边栏增加粗黑右边框
- [ ] 导航栏增加底部粗黑描边 + 立体阴影
- [ ] 数据统计栏改为圆角卡片组

### Phase 4: 动画增强
- [ ] 按钮添加按压动画 (translateY + box-shadow)
- [ ] 卡片添加悬浮效果
- [ ] 气泡添加浮动动画
- [ ] 支持 prefers-reduced-motion

### Phase 5: 中文化
- [ ] 所有文案替换为中文
- [ ] 标签映射 (`TAG_CN`) 保持现有中文映射
- [ ] 错误提示、状态文字中文化
