---
name: code-quality-gate
version: "1.6.0"
last_updated: "2026-04-27"
changelog:
  - "1.6.0: 架构优化 - 补 RuleCategory 枚举/修 Rule 构造参数/抽取公共 utils.py/添加版本号/标签字典 JSON"
  - "1.5.0: 新增应用宝用例标签规范(testcase-labels.md)及 LABEL-01~12 规则"
  - "1.4.0: 新增性能测试维度(PERF-01~15)、存储规则组(STORAGE-01~14)"
  - "1.3.0: 新增用例脑图生成器(testcase-mindmap-generator.py)"
  - "1.2.0: 新增测试策略生成器(test-strategy-generator.py)"
  - "1.1.0: 新增用例评审三维检查(testcase-reviewer.py)"
  - "1.0.0: 初始版本 - 代码扫描器 + 需求扫描器 + 5 大测试方法论"
description: >
  全栈质量测试卡点专家。将经典测试方法论（边界值、等价类划分、因果图、正交实验、错误推测）和缺陷分析方法
  固化为可执行的质量检测规则，覆盖代码、文本需求文档、图片需求文档、Figma设计稿等多类型资产。
  作为研发全流程的质量门禁：需求评审→设计审查→代码提测→用例评审→发布验收。
  当需要进行代码质量审查、需求文档质量检测、UI设计稿评审、测试用例生成指导、
  测试用例评审（规范性+完整性+耦合场景三维检查）、
  测试策略生成（基于代码变更+需求+耦合场景）、缺陷根因分析时应使用此技能。
  特别适用于AI辅助开发的左移质量保障场景。
---

# Code Quality Gate - 全栈质量测试卡点

## 概述

本 Skill 将经典软件测试方法论转化为**可自动检测的质量规则**，覆盖软件开发生命周期的**四种核心资产类型**：

```
┌─────────────────────────────────────────────────────────────┐
│                   全栈质量卡点覆盖范围                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   需求阶段              设计阶段            开发阶段          │
│   ┌──────────┐        ┌──────────┐       ┌──────────┐       │
│   │ 文本需求  │        │ 图片原型  │       │ 源代码    │       │
│   │ PRD/用户  │        │ UI设计稿  │       │ AI生成    │       │
│   │ 故事/规格 │        │ Figma稿   │       │ 手写代码  │       │
│   └─────┬────┘        └─────┬────┘       └─────┬────┘       │
│         │                   │                   │             │
│         ▼                   ▼                   ▼             │
│  requirement-scan     image/figma-scan     code-scanner      │
│  -rules.md           -rules.md            .py                │
│                                                             │
│         ══════════════════════════════════════              │
│                    共享方法论层                              │
│         test-methods.md + defect-analysis.md                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 核心能力矩阵

| 能力维度 | 文本需求 | 图片原型 | Figma设计稿 | 源代码 |
|----------|----------|----------|-------------|--------|
| **边界值检测** | 数值边界明确? | 边界状态设计? | 边界交互定义? | 边界代码保护? ✅ |
| **等价类覆盖** | 输入分类完整? | 状态枚举完整? | 变体组件覆盖? | 分支处理完备? ✅ |
| **因果图分析** | 条件组合穷尽? | 条件流程闭环? | 逻辑分支完备? | 组合条件正确? ✅ |
| **错误推测法** | 异常场景遗漏? | 错误态设计缺失? | 异常提示缺? | 典型错误防? ✅ |
| **缺陷模式匹配** | 需求缺陷识别 | 原型问题发现 | 设计规范违反 | 代码缺陷检测 ✅ |

---

## 触发条件

以下任一场景应触发此 Skill：

### 需求阶段（左移）
1. **需求文档评审** — PRD/用户故事/规格说明书编写完成后，检查需求质量
2. **需求变更评估** — 需求变更时，评估变更对质量的影响
3. **AI生成需求审核** — AI生成的需求文档需要质量把关

### 设计阶段
4. **UI原型/设计稿评审** — 图片格式的设计稿（PNG/JPG/Sketch导出）
5. **Figma设计稿审查** — 在线协作设计稿的规范性检查
6. **可访问性(A11y)检查** — 设计稿的无障碍合规性

### 开发阶段
7. **代码提交/PR审查** — 检查代码是否符合测试方法论要求
8. **研发提测前** — 执行代码质量门禁扫描
9. **AI代码评审** — 对AI生成的代码进行专项质量评估

### 测试阶段
10. **缺陷复盘** — 进行缺陷根因分析和模式识别
11. **测试策略制定** — 基于代码变更+需求+耦合场景，自动生成六维测试策略（新增范围/存量影响/兼容性/弱网/历史版本/**性能**）
12. **用例评审** — 对已编写的测试用例集做规范性+完整性+耦合场景三维评审，产出"不规范点+缺失场景"清单

---

## 使用流程

### 步骤一：确定扫描目标类型

```
输入资产 → 自动识别类型 → 选择扫描器
────────────────────────────────────
*.py / *.java / *.js / *.ts ...  → 代码扫描器 (code-scanner.py)
*.md / *.txt / *.docx / 需求文档   →  需求文档扫描器 (requirement-scanner.py)
*.png / *.jpg / *.jpeg / *.svg     →  图片原型扫描器 (image-scan rules)
figma:// URL / Figma JSON 导出      →  Figma设计稿扫描 (figma-scan rules)
```

### 步骤二：选择对应的知识库和工具

| 目标类型 | 加载文件 | 执行方式 |
|----------|----------|----------|
| **源代码** | `references/scan-rules.md` + `test-methods.md` | `python scripts/code-scanner.py <dir> --lang <lang>` |
| **文本需求** | `references/requirement-scan-rules.md` + `test-methods.md` | `python scripts/requirement-scanner.py <file>` |
| **图片原型** | `references/image-scan-rules.md` + `test-methods.md` | AI视觉分析（调用image_gen/read_file读取图片后按规则分析） |
| **Figma稿** | `references/figma-scan-rules.md` + `test-methods.md` | 解析Figma JSON后按规则分析 |
| **生成用例** | `references/testcase-template.md` + `test-methods.md` | 按Markdown模板输出标准格式测试用例 |
| **用例评审** | `references/testcase-review.md` + `testcase-template.md` + `test-methods.md` | `python scripts/testcase-reviewer.py <cases.md> [--context ctx.yaml]` |
| **测试策略** | `references/test-strategy.md` + `test-methods.md` | `python scripts/test-strategy-generator.py -r req.yaml --diff-from <base> --diff-to <head>` |
| **PCYYB专项** | `references/pcyyb-checklist.md` | 按PC应用宝检查矩阵逐项覆盖 |
| **边界值速查** | `references/boundary-techniques.md` | 三层×八维度边界技巧总索引（含漏测TOP10） |
| **用例设计方法扩展** | `references/case-design-methods.md` | 判定表法 + 状态转换测试（L0~L4路径/循环覆盖） |
| **用例脑图输出** | `references/testcase-mindmap-format.md` | 脑图结构（根→F→S→G→W→T）+ label并行展示，支持 XMind/Mermaid/XML |

### 步骤三：执行扫描

#### 代码扫描
```bash
python scripts/code-scanner.py ./src --lang python --output json
```

#### 需求文档扫描
```bash
python scripts/requirement-scanner.py ./docs/PRD-v2.md
# 支持格式: .md, .txt, .docx(需安装python-docx)
```

#### 图片原型扫描（AI辅助）
```bash
# 使用read_file工具读取图片后,按 image-scan-rules.md 中的规则逐项检查
# 或通过AI视觉能力自动识别:
# 1. 读取图片
# 2. 提取UI元素和交互描述
# 3. 对照 image-scan-rules.md 规则逐一检测
# 4. 输出结构化报告
```

#### Figma设计稿扫描
```bash
# 方式A: 通过Figma API获取JSON
# 方式B: 从浏览器开发者工具复制Figma设计数据
# 方式C: 导出Figma JSON文件
python scripts/requirement-scanner.py figma-export.json --mode figma
```

#### 测试策略生成（基于代码变更+需求+耦合场景）
```bash
# 1) 准备需求描述文件 req.yaml
#    type: new_feature | modify | bugfix | refactor | data_migration
#    platforms / user_groups / acceptance_criteria / dependencies...
#
# 2) 执行策略生成（自动拉取 git diff 并匹配规则）
python scripts/test-strategy-generator.py \
    --requirement req.yaml \
    --diff-from main --diff-to HEAD \
    --coupling coupling.yaml \
    --output-md test-strategy.md \
    --output-json test-strategy.json

# 3) 输出六维度策略：
#    ① 新增功能测试范围
#    ② 存量功能影响范围（含上下游耦合）
#    ③ 兼容性测试决策（底层/系统API/原生层变更自动判定）
#    ④ 弱网测试决策（网络请求/支付/长连接自动识别）
#    ⑤ 历史版本验证决策（数据迁移/客户端依赖/协议破坏性变更自动识别）
#    ⑥ 性能测试决策（新增接口/DB/缓存/首屏/大数据量/依赖自动识别）⭐
```

#### 用例评审（规范性 + 完整性 + 耦合场景三维）
```bash
# 1) 准备用例集 Markdown 文件（格式参考 testcase-template.md）
# 2) 可选准备评审上下文 context.yaml:
#    module: "应用宝-下载"
#    platforms: ["PC"]
#    involves: ["download", "login", "network", "compatibility"]
#    field_types: ["input_text", "list"]
#
# 3) 执行评审
python scripts/testcase-reviewer.py cases.md \
    --context context.yaml \
    --output-md testcase-review-report.md \
    --output-json testcase-review-report.json

# 4) 输出两份表格 + 评审结论：
#    ① 用例不规范点清单（违反规则/严重度/修复建议）
#    ② 用例缺失场景清单（缺失维度/触发规则/建议补充/优先级）
#    ③ 评审汇总（质量评分 + 通过/有条件通过/打回）
```

#### 用例脑图生成（Markdown 用例集 → XMind 可导入大纲）
```bash
# 把已编写好的 Markdown 用例集（TC-xxx 格式）自动转为脑图大纲
# 脑图结构：根(需求名) → F(场景) → S(用例)[label] → G(前提) → W(步骤) → T(预期)
# 其中：优先级+所属端作为 label 与 S 并行展示；没有 G 时 W 直接挂 S
python scripts/testcase-mindmap-generator.py cases.md \
    --requirement-name "积分中心签到翻倍卡" \
    --group-by module \
    --output mindmap.md

# 输出 mindmap.md 可直接：
#   - 复制内容粘贴到 XMind / MindMaster / 幕布 空白画布
#   - 或在 XMind 菜单 "文件→导入→Markdown" 选择该文件
# 详细节点规范参见 references/testcase-mindmap-format.md
```

### 步骤四：输出统一格式的质量报告

无论哪种目标类型，输出格式统一：

```json
{
  "scan_type": "code|requirement|image|figma",
  "target": "路径或名称",
  "summary": {
    "total_checks": 42,
    "passed": 30,
    "warnings": 8,
    "blockers": 4,
    "score": 78.5,
    "pass_gate": false
  },
  "issues": [
    {
      "rule_id": "REQ-03",
      "category": "COMPLETENESS",
      "severity": "BLOCKER",
      "description": "...",
      "suggestion": "..."
    }
  ],
  "method_coverage": {
    "boundary_analysis": {"checked": 15, "passed": 12, "rate": "80%"},
    "equivalence_class": {"checked": 8, "passed": 6, "rate": "75%"},
    "cause_effect": {"checked": 5, "passed": 4, "rate": "80%"},
    "error_guessing": {"checked": 14, "passed": 8, "rate": "57%"}
  }
}
```

---

## 规则体系总架构

```
┌─────────────────────────────────────────────────────────────┐
│                    全栈质量规则体系                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  L0: 共享方法论层 (所有类型共用)                             │
│  ├── test-methods.md (5大测试方法)                          │
│  └── defect-analysis.md (缺陷分析体系)                       │
│         │                                                   │
│         ├── L1-A: 需求文档规则层                             │
│         │   └── references/requirement-scan-rules.md        │
│         │       ├── REQ-COMP: 完整性规则 (等价类+因果图)     │
│         │       ├── REQ-CLARITY: 清晰度规则                  │
│         │       ├── REQ-CONSIST: 一致性规则                  │
│         │       └── REQ-TESTABLE: 可测试性规则               │
│         │                                                   │
│         ├── L1-B: 图片原型规则层                             │
│         │   └── references/image-scan-rules.md               │
│         │       ├── IMG-COMP: 完整性规则                     │
│         │       ├── IMG-INTERACT: 交互完整性                 │
│         │       ├── IMG-STATE: 状态覆盖                      │
│         │       └── IMG-A11Y: 无障碍规则                    │
│         │                                                   │
│         ├── L1-C: Figma设计稿规则层                          │
│         │   └── references/figma-scan-rules.md               │
│         │       ├── FIG-LAYOUT: 布局规范                     │
│         │       ├── FIG-COMP: 组件规范                       │
│         │       ├── FIG-RESP: 响应式                         │
│         │       ├── FIG-A11Y: 无障碍                         │
│         │       └── FIG-DEV: 开发交付规范                    │
│         │                                                   │
│         └── L1-D: 代码规则层                                 │
│             └── references/scan-rules.md                     │
│                 ├── INPUT/NULL/BOUNDARY/EXCEPTION/LOGIC     │
│                 ├── RESOURCE/CONCURRENT/SECURITY             │
│                 ├── AI-CODE/PERF                            │
│                 └── 共 40+ 条可执行规则                       │
│                                                             │
│  L2: 执行层                                                 │
│  ├── scripts/code-scanner.py           (代码自动化扫描)      │
│  ├── scripts/requirement-scanner.py    (需求文档自动化扫描)  │
│  ├── scripts/test-strategy-generator.py(测试策略自动生成)    │
│  ├── scripts/testcase-reviewer.py      (用例评审三维扫描)    │
│  └── AI视觉分析引擎                     (图片/Figma智能扫描) │
│                                                             │
│  L3: 策略生成层 (基于 L0~L2 的输入推导测试策略)              │
│  └── references/test-strategy.md                            │
│      ├── NEW-xx: 新增功能测试范围规则                        │
│      ├── IMP-xx: 存量功能影响范围规则                        │
│      ├── COMPAT-xx: 兼容性测试决策规则                       │
│      ├── NET-xx: 弱网测试决策规则                            │
│      └── HIST-xx: 历史版本验证决策规则                       │
│      └── PERF-xx: 性能测试决策规则 ⭐                        │
│                                                             │
│  L4: 用例评审层 (基于 L0/L1-D 规则 对用例集做三维评审)       │
│  └── references/testcase-review.md                          │
│      ├── FORM-xx:  规范性规则（元数据/G/W/T/优先级）         │
│      ├── COV-xx:   完整性规则（场景/边界/等价类/错误推测）   │
│      └── COUP-xx:  耦合场景规则（下载/登录/网络/兼容/频控）  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 测试策略生成专项（Test Strategy Generation）

基于 **代码变更 + 需求内容 + 耦合场景** 三要素，自动推导并输出六维测试策略。规则详见 `references/test-strategy.md`。

### 六维策略输出

| 维度 | 核心问题 | 触发依据 |
|------|----------|----------|
| **① 新增功能测试范围** | 本次新增什么？覆盖到什么程度？ | 需求类型=new_feature / 新增接口/组件/状态机 |
| **② 存量功能影响范围** | 哪些已有功能被波及？需回归什么？ | 公共函数/共享状态/接口/schema/路由/权限变更 |
| **③ 兼容性测试决策** | 需不需要专项兼容性测试？ | 底层代码/系统API/原生层/渲染引擎/新依赖变更 |
| **④ 弱网测试决策** | 需不需要弱网测试？哪些场景？ | 网络请求/长连接/支付/关键路径/大文件/直播 |
| **⑤ 历史版本验证决策** | 需不需要老版本回归？ | 数据迁移/前端依赖客户端/协议破坏性变更/本地存储结构变更 |
| **⑥ 性能测试决策** ⭐ | 需不需要性能测试？哪些项？ | 新增接口/DB/缓存/首屏/大数据量/算法复杂度/新依赖/高并发业务 |

### 决策输出分级

- 🔴 **必测（P0）** — 触发高危规则（如 COMPAT-01 底层变更、HIST-04 协议破坏性变更、NET-04 支付变更、PERF-15 高并发业务）
- 🟠 **建议测（P1）** — 触发中等规则
- 🟡 **可选测（P2）** — 触发低危规则
- ⚪ **不涉及** — 无触发规则

### 典型决策样例

| 变更类型 | 新增 | 存量 | 兼容性 | 弱网 | 历史版本 | 性能 |
|----------|------|------|--------|------|----------|------|
| 纯 CSS 改版 | ⚪ | 🟡 | 🟡 | ⚪ | ⚪ | ⚪ |
| 新增接口+前端调用 | 🔴 | 🟠 | 🟡 | 🔴 | 🟠 | 🔴 |
| 客户端 SDK 升级+协议删字段 | ⚪ | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| 数据库 schema 升级 | 🟠 | 🔴 | 🟠 | 🟡 | 🔴 | 🔴 |
| 高并发营销活动 | 🔴 | 🟠 | 🟡 | 🔴 | 🟠 | 🔴 |

### 使用方式

```bash
# 最简调用（自动拉取 git diff）
python scripts/test-strategy-generator.py -r req.yaml

# 完整调用
python scripts/test-strategy-generator.py \
  --requirement req.yaml \
  --coupling coupling.yaml \
  --diff-from v8.4.0 --diff-to v8.5.0 \
  --manual-flags flags.yaml \
  --output-md strategy.md \
  --output-json strategy.json
```

### 策略生成 Checklist（AI/人工通用）

- [ ] 需求类型是否明确（new/modify/bugfix/refactor/data_migration）？
- [ ] 代码 diff 是否可获取？
- [ ] 上下游调用链/共享状态是否识别？
- [ ] 六维度是否全部给出决策（不允许留空）？
- [ ] 每维决策是否标注触发规则ID（可追溯）？
- [ ] 是否给出工作量估算（人日，含性能测试专项）？
- [ ] 策略是否能直接对接 `testcase-template.md` 生成用例？

---

## 用例评审专项（Test Case Review）

对已编写的测试用例集做 **规范性 + 完整性 + 耦合场景** 三维评审，规则详见 `references/testcase-review.md`。

### 三维评审体系

| 维度 | 规则前缀 | 检查目标 | 规则来源 |
|------|----------|----------|----------|
| **① 规范性** | `FORM-*` | 标签/命名/G/W/T/优先级是否合规 | `testcase-template.md` |
| **② 完整性** | `COV-*` | 场景法/边界值/等价类/错误推测/正交实验是否覆盖 | `test-methods.md` |
| **③ 耦合场景** | `COUP-*` | 下载/登录/网络/兼容/窗口/频控等关键耦合是否覆盖 | `pcyyb-checklist.md` + `test-strategy.md` |

### 规范性规则集（FORM-*）

- **FORM-M\*** 元数据：编号/标题/优先级/模块/方法/GWT 齐全
- **FORM-T\*** 标题：不以操作动词起头、不模糊、多场景需"-页面名"区分
- **FORM-G\*** Given：不依赖其他用例、无"或/分别"选择性词语、描述完整
- **FORM-W\*** When：动宾结构、无"或/分别"、无连词、无假设词、无预期混入、不跨多页面
- **FORM-TH\*** Then：无操作、无假设、无"支持/可以"说明词、无概括词、一条一个检查点
- **FORM-A\*** 原子性：一条用例一个验证点、DRY 不重复
- **FORM-P\*** 优先级分布：P0 10-30% / P1 ≥50% / P2 ≥10%

### 完整性规则集（COV-*）

- **COV-S\*** 场景法：主成功+分支成功+分支失败+返回/取消/重试
- **COV-B\*** 边界值：空/最小/最大/超限（字符串/数值/列表/文件/频控）
- **COV-E\*** 等价类：用户分群/登录态/APK类型/安装状态/多语言/特殊字符
- **COV-ER\*** 错误推测：空值/快速点击/快速切换/强刷/杀进程/权限拒绝
- **COV-O\*** 正交实验：OS/显卡/虚拟化/渲染/分辨率/浏览器

### 耦合场景规则集（COUP-*）

- **COUP-D\*** 下载：跨页一致性/状态机/切账号/断网/并发
- **COUP-L\*** 登录：QQ↔微信切换/游客转正/登出清理/Token刷新
- **COUP-W\*** 窗口：大小调整/多屏拖拽/强刷
- **COUP-N\*** 网络：弱网/断网/网络切换/超时
- **COUP-C\*** 兼容：系统版本/安装版本/引擎/硬件
- **COUP-F\*** 频控：次数上限/时间窗

### 输出产物（两份核心表格）

**表一：用例不规范点清单**
| # | 用例编号 | 用例标题 | 违反规则 | 严重度 | 具体问题 | 修复建议 |

**表二：用例缺失场景清单**
| # | 缺失维度 | 触发规则 | 缺失场景 | 建议补充 | 优先级 |

### 评审结论决策

| 结论 | 条件 |
|------|------|
| ✅ **通过** | 0 BLOCKER + 不规范率 < 5% + 无 P0 缺失场景 |
| ⚠️ **有条件通过** | 0 BLOCKER + 不规范率 < 15% + P0 缺失场景 ≤ 2 |
| ❌ **打回** | 有 BLOCKER 或不规范率 ≥ 15% 或 P0 缺失场景 > 2 |

### 使用方式

```bash
# 最简调用
python scripts/testcase-reviewer.py cases.md

# 完整调用（推荐）
python scripts/testcase-reviewer.py cases.md \
  --context context.yaml \
  --output-md review-report.md \
  --output-json review-report.json

# context.yaml 示例：
# module: "应用宝-下载"
# platforms: ["PC"]
# involves: ["download", "login", "network", "compatibility"]
# field_types: ["input_text", "list"]
```

### 评审 Checklist（AI/人工通用）

- [ ] 用例集是否包含编号/标题/优先级/模块/方法/GWT 六要素？
- [ ] 是否扫描出所有 "或/分别/任意" 选择性词语违规？
- [ ] 优先级分布是否合理（P0 10-30% / P1 ≥50% / P2 ≥10%）？
- [ ] 按方法学维度（场景/边界/等价/错误推测）是否都有覆盖？
- [ ] 按耦合维度（下载/登录/网络/兼容/窗口/频控）是否都有覆盖？
- [ ] 是否输出了两份表格（不规范点 + 缺失场景）？
- [ ] 是否给出了评审结论（通过/有条件通过/打回）？

---



## 质量门禁标准（通用）

### 🔴 BLOCKER - 必须修复方可继续
- 需求：关键业务流程描述缺失、 acceptance criteria 不明确
- 设计：核心页面/流程缺少错误态设计
- 代码：安全漏洞、空指针风险、除零风险
- Figma：无障碍严重违规（如色对比度不足）

### 🟠 CRITICAL - 强烈建议修复
- 需求：边界值场景未定义、异常流程未描述
- 设计：空状态/加载态/超时态缺失
- 代码：异常被吞掉、switch缺default
- Figma：命名不规范、组件未复用

### 🟡 MAJOR - 建议优化
- 需求：非功能需求不完整、术语不一致
- 设计：hover/focus态缺失
- 代码：魔法数字、日志不足
- Figma：响应式断点不全

### 🔵 MINOR - 锦上添花
- 所有类型的风格/体验类改进建议

---

## 与CI/CD集成示例

```yaml
# .gitlab-ci.yml 全栈质量门禁示例
stages:
  - requirements-review
  - design-review
  - code-quality
  - test-strategy
  - testcase-review

# 阶段1: 需求文档质量检测
requirements_gate:
  stage: requirements-review
  script:
    - python .codebuddy/skills/code-quality-gate/scripts/requirement-scanner.py
        docs/PRD-*.md docs/user-stories/
  only:
    changes:
      - docs/**/*.md
      - docs/**/*.docx

# 阶段2: 设计稿质量检测 (Figma)
design_gate:
  stage: design-review
  script:
    - python .codebuddy/skills/code-quality-gate/scripts/requirement-scanner.py
        figma-exports/ --mode figma
  only:
    changes:
      - figma-exports/**/*.json

# 阶段3: 代码质量门禁
code_gate:
  stage: code-quality
  script:
    - python .codebuddy/skills/code-quality-gate/scripts/code-scanner.py src/
        --lang ${PROJECT_LANG} --output json > quality-report.json
    - python .codebuddy/skills/code-quality-gate/scripts/check_gate.py quality-report.json
  artifacts:
    reports:
      quality: quality-report.json
  only:
    - merge_requests

# 阶段4: 测试策略生成（研发提测前）
test_strategy:
  stage: test-strategy
  script:
    - python .codebuddy/skills/code-quality-gate/scripts/test-strategy-generator.py
        --requirement docs/requirement.yaml
        --diff-from ${CI_MERGE_REQUEST_DIFF_BASE_SHA}
        --diff-to ${CI_COMMIT_SHA}
        --output-md test-strategy.md
        --output-json test-strategy.json
  artifacts:
    paths:
      - test-strategy.md
      - test-strategy.json
    expose_as: 'Test Strategy'
  only:
    - merge_requests

# 阶段5: 用例评审（测试用例提交时）
testcase_review:
  stage: testcase-review
  script:
    - python .codebuddy/skills/code-quality-gate/scripts/testcase-reviewer.py
        testcases/*.md
        --context testcases/review-context.yaml
        --output-md testcase-review-report.md
        --output-json testcase-review-report.json
  artifacts:
    paths:
      - testcase-review-report.md
      - testcase-review-report.json
    expose_as: 'Test Case Review'
  only:
    changes:
      - testcases/**/*.md
```

---

## 注意事项

1. **方法论统一** - 无论哪种资产类型，底层都是同一套测试方法论（边界值、等价类、因果图、正交实验、错误推测）
2. **左移越早越好** - 需求阶段发现问题修复成本是代码阶段的 1/10，是上线后的 1/100
3. **AI增强** - 对于图片和Figma类型，结合AI视觉分析能力可以大幅提升检测效率和准确性
4. **人机协同** - 自动化扫描作为基线，人工深度审查补充判断
5. **持续迭代** - 各规则库可根据项目特点定制和扩展
