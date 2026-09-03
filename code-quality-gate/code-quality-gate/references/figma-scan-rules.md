# Figma设计稿质量检测规则库 (Figma Scan Rules)

> 本文件定义针对 **Figma 设计稿**（含 Figma JSON 导出/API 数据）的质量检测规则。
> 在纯图片规则基础上增加**结构化数据检测**能力：图层规范、组件使用、响应式、命名规范、开发交付等。

---

## 规则总索引

| 规则ID | 名称 | 方法来源 | 严重程度 |
|--------|------|----------|----------|
| **FIG-LAYOUT 布局规范组** |||||
| FIG-LAY-01 | 未使用Auto Layout(自动布局) | 错误推测 | CRITICAL |
| FIG-LAY-02 | 固定尺寸导致无法适配不同屏幕 | 边界值分析 | CRITICAL |
| FIG-LAY-03 | 元素未对齐到网格(Grid) | 等价类划分 | MAJOR |
| FIG-LAY-04 | 间距(Spacing)不遵循8pt网格体系 | 等价类划分 | MAJOR |
| FIG-LAY-05 | 存在游离/未归组的元素 | 错误推测 | MINOR |
| **FIG-COMP 组件规范组** |||||
| FIG-COMP-01 | 应使用Component但使用了实例拷贝 | 等价类划分 | CRITICAL |
| FIG-COMP-02 | 组件Props/Variant未正确使用 | 等价类划分 | MAJOR |
| FIG-COMP-03 | 组件嵌套层级过深(>5层) | 边界值分析 | MAJOR |
| FIG-COMP-04 | 缺少组件文档(Documentation) | 错误推测 | MINOR |
| FIG-COMP-05 | 组件命名不规范 | 等价类划分 | MINOR |
| **FIG-RESP 响应式组** |||||
| FIG-RESP-01 | 缺少响应式断点适配(移动端/平板/桌面) | 边值分析 | CRITICAL |
| FIG-RESP-02 | 文字未使用相对单位(Relative sizing) | 边界值分析 | MAJOR |
| FIG-RESP-03 | Constraint(约束)设置不当导致拉伸变形 | 错误推测 | CRITICAL |
| FIG-RESP-04 | 缺少安全区域(Safe Area)适配 | 边界值分析 | CRITICAL (Mobile) |
| **FIG-A11Y 无障碍组** |||||
| FIG-A11Y-01 | 缺少Layer描述(用于屏幕阅读器) | 等价类划分 | CRITICAL |
| FIG-A11Y-02 | 层级顺序不符合阅读顺序(Tab Order) | 因果图 | MAJOR |
| FIG-A11Y-03 | 颜色未使用语义化Token(Semantic Color) | 等价类划分 | MAJOR |
| **FIG-DEV 开发交付组** |||||
| FIG-DEV-01 | 导出资源(Slice/Asset)缺失或不完整 | 错误推测 | CRITICAL |
| FIG-DEV-02 | 缺少开发标注(Dev Mode/Inspect) | 边界值分析 | CRITICAL |
| FIG-DEV-03 | 字体/颜色/圆角/阴影未使用Style Token | 等价类划分 | MAJOR |
| FIG-DEV-04 | 命名不规范影响CSS类名生成 | 等价类划分 | MAJOR |
| FIG-DEV-05 | 缺少版本管理(Version History) | 错误推测 | MINOR |
| **FIG-CONS 一致性组** |||||
| FIG-CONS-01 | 跨页面相同组件样式不一致 | 等价类划分 | MAJOR |
| FIG-CONS-02 | Design Token定义与实际使用不一致 | 等价类划分 | CRITICAL |
| FIG-CONS-03 | 暗色模式(Dark Mode)适配不完整 | 等价类划分 | MAJOR |

---

## 详细规则定义

### FIG-LAYOUT 组 — 布局规范

#### FIG-LAY-01: 未使用Auto Layout
```yaml
规则ID: FIG-LAY-01
名称: "Frame/Group应使用Auto Layout但使用了固定定位"
方法来源: 错误推测法 (遗漏常见最佳实践)
严重程度: CRITICAL

检测逻辑 (Figma JSON):
  遍历所有 Frame 和 Group 类型节点:
  - layoutMode == "NONE" 且该容器内有多个子元素
  - 子元素使用绝对定位 (x, y 坐标而非自动排列)
  - 子元素数量 >= 3 → 更可能应该用 Auto Layout
  
  为什么重要:
  ❌ 无Auto Layout的问题:
    - 内容变化时需手动调整每个元素位置
    - 无法自适应不同文字长度/内容量
    - 开发实现时难以还原布局逻辑
    - 维护成本高,改一处要动多处

  ✅ Auto Layout的好处:
    - 内容驱动布局,自动适应
    - 与Flexbox/CSS Grid概念一致,便于开发
    - 支持嵌套构建复杂布局
    - 响应式适配更简单

  检测脚本逻辑 (伪代码):
  for node in all_frames_and_groups:
    if node.layoutMode == "NONE":
      if len(node.children) >= 3:
        # 检查子元素是否都是绝对定位
        absolute_count = sum(1 for c in node.children 
                              if c.layoutPositioning == "ABSOLUTE")
        if absolute_count == len(node.children):
          report("CRITICAL", f"{node.name}: {len(node.children)}个子元素全部绝对定位,建议使用Auto Layout")
```

#### FIG-LAY-02: 固定尺寸导致无法适配
```yaml
规则ID: FIG-LAY-02
名称: "Frame/元素使用固定像素宽度/高度,无法适配不同屏幕尺寸"
方法来源: 边界值分析法
严重程度: CRITICAL

检测逻辑:
  关键容器Frame检查:
  - 主内容区 Frame width 为固定值 (如 1440, 1280, 375 等)
  - 但没有对应的变体(Variant)或其他断点的版本
  - 或 width/height 都固定且没有 Constraints 设置

  应该做的:
  - 使用 Constraints (Left/Right/Top/Bottom) 替代固定定位
  - 使用 Fill Container 适配父容器
  - 为不同断点创建 Adaptive Variant
  - 移动端使用相对单位 (%, vw/vh)

  边界值检查:
  最小屏幕宽度 (320px iPhone SE) 时:
  - 固定宽度元素是否会溢出?
  - 文字是否会换行异常?
  - 按钮是否会过于拥挤?

  最大屏幕宽度 (1920px Desktop) 时:
  - 内容是否会过度拉伸?
  - 最大宽度(Max-width)是否设置?
```

#### FIG-LAY-04: 间距不遵循8pt网格
```yaml
规则ID: FIG-LAY-04
名称: "元素之间的间距(Spacing)不是8的倍数,破坏视觉节奏"
方法来源: 等价类划分法 (间距等价类: 4/8/12/16/24/32/48/64...)
严重程度: MAJOR

标准间距体系 (Base=8px):
  ┌────────┬────────┬──────────────────┐
  │ 间距值  │ 用途    │ 说明             │
  ├────────┼────────┼──────────────────┤
  │ 0      │ 紧贴    │ 无间隙           │
  │ 4      │ 微隙    │ 图标与文字间     │
  │ 8      │ 小间距  │ 相关元素之间     │
  │ 12     │ 中小    │ (较少用)         │
  │ 16     | 中间距  │ 区块内元素之间   │
  │ 24     │ 大间距  │ 区块之间         │
  │ 32     │ 超大    │ 主要区块间距     │
  │ 48     │ 章节间距│ 页面主要分区     │
  │ 64+    │ 特大    │ 页面级大区块     │
  └────────┴────────┴──────────────────┘

  检测逻辑:
  计算相邻元素的 itemSpacing 或 position差值:
  spacing % 8 != 0 且 spacing % 4 != 0 → 报告异常
  (允许 4px 的半级间距)
```

### FIG-COMP 组 — 组件规范

#### FIG-COMP-01: 应使用Component但用了实例拷贝
```yaml
规则ID: FIG-COMP-01
名称: "重复出现的UI元素应该是Component实例,但使用了Detach后的独立拷贝"
方法来源: 等价类划分法 (同一事物应归类为同一等价类)
严重程度: CRITICAL

检测逻辑:
  - 查找视觉上相似的元素组合
  - 检查它们是否引用同一个 Component
  - 如果多处出现相同模式但没有 Component 化 → 报告
  
  危害:
  - 一处修改需手动同步到所有拷贝 (易遗漏)
  - 增加文件体积
  - 开发无法复用组件代码
  - Design System 无法统一管控

  应该 Component化的信号:
  - 同样的按钮/标签/卡片样式出现 ≥ 3 次
  - 表单元素(输入框/选择器/开关)
  - 导航/Header/Footer
  - 卡片/列表项模板
  - 状态标签(Badge/Tag)
```

#### FIG-COMP-02: Variant使用不规范
```yaml
规则ID: FIG-COMP-02
名称: "组件Variant属性定义不全或不规范,导致变体组合爆炸或缺失"
方法来源: 等价类划分法
严重程度: MAJOR

正交实验法的应用 — Variant组合:
  组件通常有以下维度(因素),每个维度有若干水平:
  - Size: S / M / L
  - State: Default / Hover / Active / Disabled / Loading
  - Type: Primary / Secondary / Tertiary / Ghost
  - Icon: With Icon / No Icon
  
  检查:
  - Variant 属性命名是否语义清晰? (不用 "Property 1", "Variant 2")
  - 所有有意义的属性组合是否都有定义?
  - 是否存在冗余或重复的组合?
  
  推荐 Variant 命名:
  ✅ Size=S/M/L, State=Default/Hover/Disabled
  ❌ Variant 1=A/B/C, Variant 2=X/Y/Z
```

### FIG-DEV 组 — 开发交付

#### FIG-DEV-01: 导出资源缺失
```yaml
规则ID: FIG-DEV-01
名称: "需要开发的图片/图标资源未正确设置Slice或Export"
方法来源: 错误推测法
严重程度: CRITICAL

检查项:
  - 所有 Icon 是否都设置了 Export (SVG优先)?
  - 插画/图片是否有 Slice 定义?
  - 导出格式是否正确? (Icon→SVG, Photo→PNG/WebP, Logo→SVG)
  - 导出的 Scale/尺寸是否符合要求? (@1x/@2x/@3x)
  - 命名是否规范? (kebab-case)

  常见遗漏:
  - 缺省态插图
  - 空状态插画
  - 错误状态图标
  - 不同主题的图标 (亮色/暗色)
  - 启动图/Logo 各尺寸
```

#### FIG-DEV-02: 缺少开发标注
```yaml
规则ID: FIG-DEV-02
名称: "切换到Dev Mode后缺少关键的CSS属性标注或标注不准确"
方法来源: 边界值分析法
严重程度: CRITICAL

开发者需要的核心信息:
  - 精确的尺寸 (width/height/padding/margin)
  - 字体 (font-family/size/weight/line-height/letter-spacing)
  - 颜色 (hex/rgba/hsl + opacity)
  - 圆角 (border-radius, 可能为不规则圆角)
  - 阴影 (box-shadow 参数)
  - 渐变 (gradient 类型和参数)
  - 间距 (gap/flex gap)

  检查:
  - Dev Mode 下是否能准确读取以上属性?
  - 自定义字体是否标注了 fallback font stack?
  - 模糊效果(Blur)参数是否可读?
  - 混合模式(Blend Mode)是否注明?
```

#### FIG-DEV-03: Style Token使用不彻底
```yaml
规则ID: FIG-DEV-03
名称: "颜色/字体/圆角/阴影应使用Local Style Token但直接使用了硬编码值"
方法来源: 等价类划分法
严重程度: MAJOR

检测逻辑:
  遍历所有叶子节点的 style 引用:
  - fills 直接为 hex color 而非引用 Color Style → 警告
  - fontSize/fontName 直接设值而非引用 Text Style → 警告
  - cornerRadius 直接设值而非引用 Effect Style → 警告
  - effects (shadow) 直接设值而非引用 Effect Style → 警告

  为什么重要:
  - Token 化后全局修改一键生效
  - 方便生成 Design Token JSON (供前端使用)
  - 保证跨页面/组件的一致性
  - 支持暗色模式等主题切换
```

### FIG-RESP 组 — 响应式

#### FIG-RESP-01: 缺少多断点适配
```yaml
规则ID: FIG-RESP-01
名称: "仅有单一尺寸的设计稿,缺少移动端/平板/桌面等多断点适配"
方法来源: 边界值分析法
严重程度: CRITICAL

标准断点体系 (等价类):
  ┌──────────────┬──────────┬────────────────────┐
  │ 断点名称      │ 宽度范围  │ 代表设备           │
  ├──────────────┼──────────┼────────────────────┤
  │ Mobile S     │ 320px    │ iPhone SE / 小屏   │
  │ Mobile M     │ 375px    │ iPhone 12/13/14    │
  │ Mobile L     │ 390px    │ iPhone 14 Pro Max  │
  │ Tablet       │ 768px    │ iPad Portrait      │
  │ Desktop S    │ 1024px   │ 小笔记本           │
  │ Desktop M    │ 1440px   │ 常见桌面分辨率     │
  │ Desktop L    │ 1920px   │ 大屏显示器         │
  └──────────────┴──────────┴────────────────────┘

  检查:
  项目至少应有几个断点的设计?
  - 纯Mobile项目: Mobile M + Mobile L (2个)
  - Responsive项目: Mobile + Tablet + Desktop (3个)
  - 后台管理系统: Desktop S + Desktop M (2个)

  如果只有1个尺寸 → CRITICAL
```

#### FIG-RESP-04: 缺少Safe Area适配 (Mobile)
```yaml
规则ID: FIG-RESP-04
名称: "移动端设计稿未考虑iOS Safe Area(刘海/底部指示器)"
方法来源: 边界值分析法
严重程度: CRITICAL (Mobile项目)

Safe Area 边界:
  ┌──────────────────────────────────┐
  │  Status Bar (~44~54pt)  ← 不放内容 │
  │  ┌────────────────────────┐     │
  │  │                        │     │
  │  │    Safe Area 内容区    │     │
  │  │                        │     │
  │  └────────────────────────┘     │
  │  Home Indicator (~34pt) ← 不放  │
  └──────────────────────────────────┘

  检查:
  - Frame 是否使用了 Safe Area Guide (Figma内置)?
  - 底部固定按钮是否避开了 Home Indicator 区域?
  - 顶部内容是否避开了 Status Bar / 刘海区域?
  - 横屏模式下是否也做了适配?
```

### FIG-A11Y 组 — 无障碍 (结构化增强版)

#### FIG-A11Y-01: Layer描述缺失
```yaml
规则ID: FIG-A11Y-01
名称: "可交互元素/重要内容的Layer缺少description(描述),影响屏幕阅读器体验"
方法来源: 等价类划分法
严重程度: CRITICAL

检测逻辑:
  以下类型的 Layer 必须有 description:
  - 所有 Button 类型
  - 所有 Icon Button (图标按钮)
  - 链接 (Link)
  - 输入框 (Input) - description 作为 placeholder 参考
  - 图片 (Image) - description 用于 alt text
  - 重要信息卡片/图表

  Figma API 检查:
  for node in interactive_nodes:
    if not node.description or node.description.strip() == "":
      report("CRITICAL", f"{node.name}: 缺少layer description,屏幕阅读器将无法朗读此元素")
```

---

## Figma扫描工作流

```
Figma设计稿输入
     │
     ├─ 方式A: Figma API (推荐)
     │   → 获取 File Key → 调用 REST API → 得到完整JSON
     │
     ├─ 方式B: 手动导出JSON
     │   → Figma菜单 → Copy as JSON / Export → 保存JSON文件
     │
     └─ 方式C: Dev Mode Inspect
        → 浏览器开发者工具复制Figma节点数据
     │
     ▼
┌─────────────────────────────────────────┐
│  Step 1: 解析Figma JSON结构             │
│  • 构建 DOM树 (节点父子关系)             │
│  • 提取所有 Frame/Group/Component       │
│  • 提取所有 Text/Instance 节点           │
│  • 建立 Style Token 引用关系            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Step 2: 规则引擎逐项检测                │
│                                         │
│  布局检测:                              │
│  □ FIG-LAY-01: Auto Layout覆盖率         │
│  □ FIG-LAY-02: 响应式适配               │
│  □ FIG-LAY-04: 8pt网格 adherence       │
│                                         │
│  组件检测:                              │
│  □ FIG-COMP-01: Component化率           │
│  □ FIG-COMP-02: Variant规范性           │
│                                         │
│  响应式检测:                            │
│  □ FIG-RESP-01: 断点覆盖               │
│  □ FIG-RESP-03: Constraints            │
│  □ FIG-RESP-04: Safe Area (Mobile)     │
│                                         │
│  开发交付检测:                          │
│  □ FIG-DEV-01: 导出资源完整度           │
│  □ FIG-DEV-02: Dev Mode标注             │
│  □ FIG-DEV-03: Style Token使用率        │
│                                         │
│  无障碍检测:                            │
│  □ FIG-A11Y-01: Layer Description       │
│  □ FIG-A11Y-03: Semantic Colors         │
│                                         │
│  一致性检测:                            │
│  □ FIG-CONS-02: Token vs 实际值一致性    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Step 3: 输出报告                        │
│  • Figma节点路径定位 (精确到具体Frame)   │
│  • 自动修复建议 (如"转为Auto Layout")    │
│  • 开发风险提示                         │
│  • Design System合规评分                │
└─────────────────────────────────────────┘
```

## Figma质量评分卡

```
Figma设计稿质量评分卡
═══════════════════════════════════════

布局规范 (25%):
  Auto Layout使用率:    ___/100
  响应式断点覆盖:        ___/100
  网格/间距规范度:        ___/100
  小计:                  ___/100  权重×25% = ___

组件规范 (20%):
  组件化率:              ___/100
  Variant规范性:          ___/100
  组件文档完善度:         ___/100
  小计:                  ___/100  权重×20% = ___

开发交付 (25%):
  导出资源完整度:        ___/100
  Dev Mode标注完整度:     ___/100
  Style Token使用率:      ___/100
  命名规范度:            ___/100
  小计:                  ___/100  权重×25% = ___

无障碍 (15%):
  Layer描述覆盖率:       ___/100
  色彩对比度合规率:      ___/100
  触控目标尺寸合规率:    ___/100
  小计:                  ___/100  权重×15% = ___

一致性 (15%):
  跨页面一致性:          ___/100
  Token一致性:           ___/100
  小计:                  ___/100  权重×15% = ___

═══════════════════════════════════════
总分: ___/100   等级: A(90+) / B(75-89) / C(60-74) / D(<60)
门禁: ___ PASS / WARN / BLOCK
```
