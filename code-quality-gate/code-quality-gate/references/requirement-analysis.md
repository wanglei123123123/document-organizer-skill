# 需求来源解析方法论

> 本文件定义如何从不同来源的需求文档中提取可用于代码质量校验的测试规则。
> 支持三类来源：文本需求文档、图片需求文档、Figma设计稿。

---

## 一、概述

### 为什么需要从需求提取测试规则

```
┌─────────────────────────────────────────────────────┐
│   传统方式:  需求 → 研发编码 → 提测 → 测试写用例    │
│   问题: 测试用例基于"对代码的理解"而非"需求本身"      │
│                                                     │
│   新方式:  需求 → 提取规则 → 代码+规则对齐校验       │
│   优势: 直接验证代码是否满足了需求中的约束            │
│         发现"需求说了但代码没实现"的盲区              │
└─────────────────────────────────────────────────────┘
```

### 三类需求来源对比

| 维度 | 文本PRD | 图片文档 | Figma设计稿 |
|------|---------|----------|-------------|
| 解析技术 | NLP/正则/LLM | OCR + 多模态LLM | Figma REST API |
| 信息密度 | 高(结构化文字) | 中(需识别转换) | 高(结构化数据) |
| 边界条件 | 明确(文字描述) | 需识别推断 | 隐含在约束中 |
| 状态枚举 | 列表/表格 | 流程图/状态图 | Variants/交互流 |
| 交互规则 | 文字描述 | 原型截图 | 原型交互定义 |
| 视觉规范 | 无/简单 | 截图参考 | Design Token |
| 自动化程度 | ★★★★★ | ★★★☆☆ | ★★★★★ |

---

## 二、文本需求文档解析

### 2.1 支持的文档格式

| 格式 | 文件扩展名 | 解析方式 |
|------|-----------|---------|
| Markdown | .md | 直接解析标题/列表/表格 |
| Word | .docx | python-docx 提取文本和表格 |
| 纯文本 | .txt | 直接读取 |
| Confluence | HTML export | BeautifulSoup 提取 |
| TAPD/Jira | API response | JSON 解析 |

### 2.2 提取算法

#### 边界条件提取

```python
"""
从文本中提取数值边界条件
"""
BOUNDARY_PATTERNS = {
    # 中文模式
    "zh_range": r'(?P<field>\w+)(?:的)?(?:范围|取值)(?:为|是|:)\s*(?P<min>[\d.]+)\s*[-~到至]\s*(?P<max>[\d.]+)',
    "zh_max": r'(?P<field>\w+)(?:不超过|最多|不得超过|最大|上限为?)\s*(?P<max>[\d.]+)\s*(?P<unit>\w*)',
    "zh_min": r'(?P<field>\w+)(?:至少|最少|不少于|最小|下限为?)\s*(?P<min>[\d.]+)\s*(?P<unit>\w*)',
    "zh_length": r'(?P<field>\w+)(?:长度|字数|字符数)(?:不超过|最多|限制为?)\s*(?P<max>\d+)\s*(?:位|个|字符)?',
    "zh_count": r'(?:最多|至多)(?:允许)?(?P<max>\d+)\s*(?:个|条|次)\s*(?P<field>\w+)',
    
    # 英文模式
    "en_range": r'(?P<field>\w+)\s+(?:must be|should be|is)\s+between\s+(?P<min>[\d.]+)\s+and\s+(?P<max>[\d.]+)',
    "en_max": r'(?:maximum|max|up to|at most|no more than)\s+(?P<max>[\d.]+)\s+(?P<field>\w+)',
    "en_min": r'(?:minimum|min|at least|no less than)\s+(?P<min>[\d.]+)\s+(?P<field>\w+)',
    "en_length": r'(?P<field>\w+)\s+(?:max(?:imum)?\s+)?length\s+(?:is|of|:)\s*(?P<max>\d+)',
}
```

#### 状态枚举提取

```python
"""
从文本中提取状态枚举和分类
"""
ENUM_PATTERNS = {
    # 中文列举模式
    "zh_list": r'(?P<field>\w+)(?:包括|分为|分别是|可选值有|状态有)\s*[:：]\s*(?P<values>.+?)(?:\n|$)',
    "zh_status": r'(?P<field>\w+)状态\s*[:：]\s*(?P<values>.+?)(?:\n|$)',
    "zh_role": r'(?:角色|用户类型)(?:包括|分为)\s*[:：]\s*(?P<values>.+?)(?:\n|$)',
    
    # 英文列举模式
    "en_enum": r'(?P<field>\w+)\s+(?:can be|includes?|options?)\s*[:：]\s*(?P<values>.+?)(?:\n|$)',
    "en_status": r'(?:status|state)(?:es)?\s*[:：]\s*(?P<values>.+?)(?:\n|$)',
}

# 值分隔符: 、，,/|；;  以及 Markdown列表符号 - * 1. 2.
VALUE_SEPARATORS = r'[、，,/|；;]|\n\s*[-*]\s*|\n\s*\d+[.)]\s*'
```

#### 条件组合提取

```python
"""
从文本中提取多条件组合逻辑
"""
CONDITION_PATTERNS = {
    "zh_and": r'当\s*(?P<c1>.+?)\s*(?:且|并且|同时)\s*(?P<c2>.+?)\s*时\s*[,，]\s*(?P<effect>.+)',
    "zh_or": r'当\s*(?P<c1>.+?)\s*(?:或|或者)\s*(?P<c2>.+?)\s*时\s*[,，]\s*(?P<effect>.+)',
    "zh_if": r'如果\s*(?P<condition>.+?)\s*[,，]\s*则\s*(?P<effect>.+)',
    "zh_unless": r'除非\s*(?P<condition>.+?)\s*[,，]\s*否则\s*(?P<effect>.+)',
    "en_when_and": r'when\s+(?P<c1>.+?)\s+and\s+(?P<c2>.+?)\s*[,，]\s*(?P<effect>.+)',
    "en_if": r'if\s+(?P<condition>.+?)\s*[,，]\s*then\s+(?P<effect>.+)',
}
```

### 2.3 验收条件(AC)解析

```python
"""
解析 Given/When/Then 格式的验收条件
"""
AC_PATTERN = r'''
    (?:Given|假设|前置条件)\s*[:：]?\s*(?P<given>.+?)\n
    (?:When|当|操作)\s*[:：]?\s*(?P<when>.+?)\n
    (?:Then|则|期望结果)\s*[:：]?\s*(?P<then>.+?)(?:\n|$)
'''

# 示例输入:
# Given: 用户已登录且是VIP会员
# When: 下单金额超过100元
# Then: 自动享受双倍积分

# 解析输出:
# {
#   "preconditions": ["用户已登录", "是VIP会员"],
#   "action": "下单金额超过100元",
#   "expected": "自动享受双倍积分",
#   "test_points": {
#     "boundaries": [{"field": "order_amount", "threshold": 100}],
#     "equivalence_classes": [{"field": "user_type", "valid": ["VIP"]}],
#     "cause_effects": [{"causes": ["is_logged_in","is_vip","amount>100"], "effect": "double_points"}]
#   }
# }
```

---

## 三、图片需求文档解析

### 3.1 处理流程

```
图片输入
    │
    ▼
┌───────────────────┐
│ Step1: 预处理     │  去噪/增强对比度/矫正倾斜
└────────┬──────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌───────┐
│ OCR   │ │ VLM   │  并行处理
│ 文字  │ │ 视觉  │  
└───┬───┘ └───┬───┘
    │         │
    ▼         ▼
┌───────────────────┐
│ Step2: 信息融合   │  文字+视觉结构合并
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Step3: 规则提取   │  应用REQ-TEXT规则
└────────┬──────────┘
         │
         ▼
  requirement_rules.json
```

### 3.2 OCR工具选型建议

| 工具 | 中文支持 | 表格支持 | 手写支持 | 成本 | 推荐场景 |
|------|----------|----------|----------|------|---------|
| Tesseract 5 | ★★★☆ | ★★☆☆ | ★☆☆☆ | 免费 | 标准印刷体文档 |
| PaddleOCR | ★★★★★ | ★★★★ | ★★★☆ | 免费 | 中文为主的文档 |
| 腾讯云OCR | ★★★★★ | ★★★★★ | ★★★★ | 按量 | 生产环境 |
| Google Vision | ★★★★ | ★★★★ | ★★★☆ | 按量 | 多语种混合 |
| Azure AI Vision | ★★★★ | ★★★★★ | ★★★★ | 按量 | 表格密集型文档 |

### 3.3 多模态LLM视觉分析

```python
"""
使用多模态LLM分析图片需求文档的Prompt模板
"""

VISION_ANALYSIS_PROMPT = """
你是一个资深的测试分析专家。请仔细分析这张需求文档的图片，完成以下任务：

## 任务1: 文字内容提取
提取图中所有可见的文字内容，保持原始结构（标题、段落、列表、表格）

## 任务2: 视觉结构识别
- 如果包含流程图：列出所有节点名称、判断分支（条件+Yes/No路径）、终止节点
- 如果包含状态图：列出所有状态、状态间的转换事件和条件
- 如果包含表格：提取所有行列数据
- 如果包含UI原型：列出所有可见的UI元素（输入框、按钮、下拉菜单等）

## 任务3: 测试关注点提取
从以上内容中提取：

### 边界条件
列出所有涉及数值范围、长度限制、数量约束的地方
格式: {"field": "字段名", "min": 最小值, "max": 最大值, "unit": "单位"}

### 状态/枚举
列出所有状态列表、可选值、分类类型
格式: {"field": "字段名", "values": ["值1","值2","值3"]}

### 条件组合
列出所有多条件组合的业务规则
格式: {"causes": ["条件1","条件2"], "effect": "结果", "logic": "AND/OR"}

### 异常场景
列出所有提到的错误、异常、降级场景
格式: {"scenario": "描述", "expected_behavior": "预期处理"}

请以JSON格式输出所有结果。
"""
```

---

## 四、Figma设计稿解析

### 4.1 Figma API接入

```python
"""
Figma API接入工具
"""
import os
import requests
from typing import Dict, List, Optional

FIGMA_BASE_URL = "https://api.figma.com/v1"

class FigmaParser:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("FIGMA_TOKEN")
        if not self.token:
            raise ValueError("FIGMA_TOKEN environment variable or token parameter required")
        self.headers = {"X-Figma-Token": self.token}
    
    def get_file(self, file_key: str) -> Dict:
        """获取Figma文件完整数据"""
        resp = requests.get(f"{FIGMA_BASE_URL}/files/{file_key}", headers=self.headers)
        resp.raise_for_status()
        return resp.json()
    
    def get_components(self, file_key: str) -> Dict:
        """获取文件中的所有组件"""
        resp = requests.get(f"{FIGMA_BASE_URL}/files/{file_key}/components", headers=self.headers)
        resp.raise_for_status()
        return resp.json()
    
    def get_styles(self, file_key: str) -> Dict:
        """获取设计样式(颜色/字体/效果)"""
        resp = requests.get(f"{FIGMA_BASE_URL}/files/{file_key}/styles", headers=self.headers)
        resp.raise_for_status()
        return resp.json()
    
    def get_images(self, file_key: str, node_ids: List[str], format: str = "png") -> Dict:
        """导出节点为图片"""
        ids = ",".join(node_ids)
        resp = requests.get(
            f"{FIGMA_BASE_URL}/images/{file_key}?ids={ids}&format={format}",
            headers=self.headers
        )
        resp.raise_for_status()
        return resp.json()
```

### 4.2 Figma节点类型映射

```yaml
# Figma节点类型 → 测试规则映射
node_type_mapping:
  
  TEXT:
    识别方式: node.type == "TEXT"
    提取: 文本内容(characters), 字体样式(style)
    映射规则: 无直接规则,作为上下文辅助识别
  
  INSTANCE:  # 组件实例
    识别方式: node.type == "INSTANCE"
    提取: 组件名(name), 属性(componentProperties)
    映射:
      name含"Input/Field": → INPUT-01~04 (输入校验)
      name含"Select/Dropdown": → INPUT-03 (枚举完备)
      name含"Button/Btn": → LOGIC (状态处理)
      name含"Table/List": → PERF-01 (数据加载)
      name含"Modal/Dialog": → LOGIC-01 (分支完整)
  
  COMPONENT_SET:  # 组件集(含Variants)
    识别方式: node.type == "COMPONENT_SET"
    提取: 所有variant属性及其可选值
    映射: → INPUT-03 (所有variant值必须在代码中处理)
    示例:
      Variants: State=Default, State=Hover, State=Disabled, State=Error
      → 代码中按钮组件必须处理这4种状态
  
  FRAME:  # 画板/容器
    识别方式: node.type == "FRAME"
    提取: 子节点列表, 布局属性(layoutMode, padding)
    映射:
      含多个Input子节点: → 表单校验规则组
      含原型交互: → 页面路由规则
```

### 4.3 从Figma提取规则的完整流程

```
Figma File
    │
    ├─── 1. GET /files/{key} ──→ 获取完整节点树
    │
    ├─── 2. 遍历节点树
    │    ├── 收集所有 INSTANCE 节点 (组件实例)
    │    ├── 收集所有 COMPONENT_SET 节点 (组件集/Variants)
    │    ├── 收集所有 TEXT 节点 (文案内容)
    │    └── 收集所有带 prototyping 的节点 (交互流程)
    │
    ├─── 3. 组件分析
    │    ├── Input类: 提取验证约束 → boundaries[]
    │    ├── Select类: 提取选项列表 → equivalence_classes[]
    │    ├── Button类: 提取状态变体 → ui_rules[]
    │    └── Form类: 提取必填/格式 → ui_rules[]
    │
    ├─── 4. 交互分析
    │    ├── 提取所有页面跳转 → page_flows[]
    │    ├── 提取触发条件 → cause_effects[]
    │    └── 提取错误/空状态 → error_scenarios[]
    │
    ├─── 5. 样式分析
    │    ├── GET /files/{key}/styles → design_tokens{}
    │    └── 提取颜色/字体/间距规范
    │
    └─── 6. 输出
         └── requirement_rules.json (统一格式)
```

---

## 五、统一输出格式: requirement_rules.json

```json
{
  "meta": {
    "source_type": "text|image|figma",
    "source_path": "path/to/source or figma_file_key",
    "parse_timestamp": "2026-04-13T11:00:00Z",
    "parser_version": "1.0.0"
  },
  
  "boundaries": [
    {
      "id": "B001",
      "field": "username",
      "type": "string_length",
      "min": 2,
      "max": 20,
      "unit": "characters",
      "source_ref": "PRD 3.1.1 用户名长度限制",
      "code_check": "代码中应有 len(username) >= 2 and len(username) <= 20"
    },
    {
      "id": "B002",
      "field": "order_amount",
      "type": "numeric_range",
      "min": 0.01,
      "max": 999999.99,
      "unit": "CNY",
      "source_ref": "PRD 4.2 订单金额约束",
      "code_check": "代码中应有 0.01 <= amount <= 999999.99 校验"
    }
  ],
  
  "equivalence_classes": [
    {
      "id": "E001",
      "field": "order_status",
      "valid_values": ["pending", "paid", "shipped", "delivered", "cancelled"],
      "invalid_values": ["unknown", "null", "empty_string"],
      "source_ref": "PRD 2.3 订单状态列表",
      "code_check": "switch/if-elif必须覆盖5种有效状态+default兜底"
    }
  ],
  
  "cause_effects": [
    {
      "id": "CE001",
      "causes": ["user.is_vip == true", "order.amount > 100"],
      "effect": "apply_double_points",
      "logic": "AND",
      "source_ref": "PRD 5.1 VIP积分规则",
      "code_check": "代码中应有 is_vip AND amount>100 的组合判断"
    }
  ],
  
  "ui_rules": [
    {
      "id": "UI001",
      "element": "email_input",
      "type": "text_input",
      "required": true,
      "validation": "email_format",
      "max_length": 100,
      "placeholder": "请输入邮箱",
      "error_message": "邮箱格式不正确",
      "source_ref": "Figma: Registration Form / Email Input",
      "code_check": "前端表单应有email格式校验+长度限制+必填校验"
    }
  ],
  
  "design_tokens": {
    "colors": {
      "primary": "#1A73E8",
      "error": "#D93025",
      "success": "#188038",
      "warning": "#F29900"
    },
    "typography": {
      "heading-1": {"font_size": 24, "font_weight": 700, "line_height": 32},
      "body": {"font_size": 14, "font_weight": 400, "line_height": 22}
    },
    "spacing": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32}
  },
  
  "error_scenarios": [
    {
      "id": "ERR001",
      "scenario": "网络请求超时",
      "expected_behavior": "显示重试提示,保留用户已输入的数据",
      "source_ref": "PRD 6.2 异常处理"
    }
  ]
}
```

---

## 六、需求规则与代码扫描的关联

### 关联方式

```
requirement_rules.json 中的每条规则
      │
      ├── boundaries[i]
      │   └── 生成: INPUT-02 (参数范围校验) 的具体检查目标
      │         检查: 代码中是否有 field >= min AND field <= max
      │
      ├── equivalence_classes[i]
      │   └── 生成: INPUT-03 (枚举完备性) 的具体检查目标
      │         检查: switch/if-elif 是否覆盖了 valid_values 中的所有值
      │
      ├── cause_effects[i]
      │   └── 生成: LOGIC (多条件组合) 的具体检查目标
      │         检查: 代码中是否有对应的多条件判断组合
      │
      ├── ui_rules[i]
      │   └── 生成: 前端代码校验检查项
      │         检查: form validation / 状态处理 / 样式实现
      │
      └── error_scenarios[i]
          └── 生成: AICD-02 (happy path) 的具体检查目标
                检查: 对应异常场景是否有try-catch / 降级处理
```

### 使用方式

```bash
# 1. 从文本需求提取规则
python scripts/requirement-parser.py --source text --input prd.md --output req_rules.json

# 2. 从图片需求提取规则
python scripts/requirement-parser.py --source image --input screenshots/ --output req_rules.json

# 3. 从Figma提取规则
python scripts/requirement-parser.py --source figma --file-key abc123 --output req_rules.json

# 4. 基于需求规则+代码扫描规则联合检查
python scripts/code-scanner.py src/ --lang python --requirements req_rules.json --output json
```
