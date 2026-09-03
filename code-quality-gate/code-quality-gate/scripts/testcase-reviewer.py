#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Case Reviewer
==================
基于 testcase-review.md 规则库，对 Markdown 格式的测试用例集做三维评审：
  ① 规范性检查 (FORM-*)
  ② 完整性检查 (COV-*)
  ③ 耦合场景检查 (COUP-*)

输出：
  - 用例不规范点清单（表格）
  - 用例缺失场景清单（表格）
  - 评审汇总（质量评分 + 结论）

使用：
  python testcase-reviewer.py cases.md \\
      [--context context.yaml] \\
      [--output-md review.md] \\
      [--output-json review.json]

context.yaml 示例：
  module: "应用宝-下载"
  platforms: ["PC"]
  involves: ["download", "login", "network"]
  field_types: ["input_text", "list", "file"]
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# 公共工具函数
try:
    from utils import extract_single_label, extract_multi_label, extract_section, extract_table_column, md_escape
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from utils import extract_single_label, extract_multi_label, extract_section, extract_table_column, md_escape


# ============================================================
# 数据模型
# ============================================================

@dataclass
class TestCase:
    id: str = ""
    title: str = ""
    priority: str = ""
    module: str = ""
    method: str = ""
    given: str = ""
    when: str = ""
    then: str = ""
    # 标签（testcase-labels.md 规范）
    platforms: list[str] = field(default_factory=list)   # 所属端
    phases: list[str] = field(default_factory=list)      # 适用阶段
    test_party: str = ""                                  # 所属测试方（虎牙侧/空）
    automation: str = ""                                  # 自动化状态
    raw: str = ""
    line_no: int = 0  # 在原文件中的起始行


@dataclass
class Issue:
    """用例不规范点"""
    tc_id: str
    tc_title: str
    rule_id: str
    severity: str  # BLOCKER / CRITICAL / MAJOR / MINOR
    description: str
    suggestion: str


@dataclass
class MissingScenario:
    """用例缺失场景"""
    dimension: str  # 规范维度/触发类型
    rule_id: str
    scenario: str
    suggestion: str
    priority: str  # P0 / P1 / P2


# ============================================================
# 用例解析器
# ============================================================

CASE_HEADING_PATTERN = re.compile(r"^#{2,4}\s*(TC[-_][\w\-]+)[:\s：]+(.+)$", re.MULTILINE)

FIELD_PATTERNS = {
    "priority": [
        re.compile(r"\*{0,2}优先级\*{0,2}\s*[:：]\s*(P[0-3])", re.IGNORECASE),
    ],
    "module": [
        re.compile(r"\*{0,2}所属模块\*{0,2}\s*[:：]\s*(.+)"),
    ],
    "method": [
        re.compile(r"\*{0,2}测试方法\*{0,2}\s*[:：]\s*(.+)"),
    ],
}


def parse_markdown_cases(content: str) -> list[TestCase]:
    """按 TC-xxx 标题切分用例"""
    cases: list[TestCase] = []
    # 找到所有标题及其位置
    matches = list(CASE_HEADING_PATTERN.finditer(content))
    for i, m in enumerate(matches):
        tc_id = m.group(1)
        title = m.group(2).strip().strip("*").strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end]
        line_no = content[:start].count("\n") + 1

        tc = TestCase(id=tc_id, title=title, raw=body, line_no=line_no)

        # 字段提取
        for field_name, patterns in FIELD_PATTERNS.items():
            for pat in patterns:
                fm = pat.search(body)
                if fm:
                    setattr(tc, field_name, fm.group(1).strip())
                    break

        # 标签字段提取（testcase-labels.md）
        tc.platforms = extract_multi_label(body, ["所属端", "端", "platforms", "platform"])
        tc.phases = extract_multi_label(body, ["适用阶段", "阶段", "phase", "phases"])
        party = extract_single_label(body, ["所属测试方", "测试方", "test_party"])
        tc.test_party = party.strip() if party else ""
        auto = extract_single_label(body, ["自动化", "automation"])
        tc.automation = auto.strip() if auto else ""

        # Given / When / Then 提取
        tc.given = extract_section(body, ["前置条件", "Given"])
        tc.when = _extract_when(body)
        tc.then = _extract_then(body)

        cases.append(tc)
    return cases


def _extract_when(body: str) -> str:
    """提取 When：可能出现在表格的操作列，也可能是段落"""
    paragraph = extract_section(body, ["操作步骤", "When", "操作"])
    if paragraph and len(paragraph) > 3:
        return paragraph
    table_when = extract_table_column(body, ["操作", "When"])
    return table_when


def _extract_then(body: str) -> str:
    paragraph = extract_section(body, ["预期结果", "Then", "预期"])
    if paragraph and len(paragraph) > 3:
        return paragraph
    table_then = extract_table_column(body, ["预期", "Then"])
    return table_then


# ============================================================
# 维度一：规范性检查规则
# ============================================================

# 选择性词语触发器（Given/When）
CHOICE_WORDS = ["或者", "或", "也可以", "还可以", "任意", "任选", "其中之一",
                "多种方式", "不同方式", "分别"]
CHOICE_SLASH = re.compile(r"[\w\u4e00-\u9fff]+\s*/\s*[\w\u4e00-\u9fff]+")

# When 中的假设词/连词/预期词
HYPOTHESIS_WORDS = ["如果", "假设", "可能", "应当"]
CONJ_WORDS = ["并且", "而且", "同时", "以及"]
RESULT_WORDS_IN_WHEN = ["弹出", "显示", "出现", "跳转到", "展示为", "提示"]

# Then 中的违规词
OP_STARTERS_IN_THEN = ["点击", "关闭", "回退", "输入", "打开", "按下"]
HYPOTHESIS_IN_THEN = ["可能", "应该", "也许"]
EXPLANATORY_IN_THEN = ["支持", "可以", "会", "能够"]
GENERIC_IN_THEN = ["相关", "对应的", "合理", "正确地", "合适的"]

# 多页面关键词
PAGE_KEYWORDS = ["首页", "我的", "详情页", "列表页", "设置页", "搜索页",
                 "下载盒子", "快捷工具栏", "更新列表", "主页"]

# 安全/支付/账号模块识别
SECURITY_MODULE_HINTS = ["支付", "登录", "账号", "密码", "验证码", "权限", "token", "授权"]

# 标签字典（testcase-labels.md 3.3/3.4）
VALID_PLATFORMS = {"PCYYB", "ARM", "手助", "微软绿色版", "ARM微软绿色版", "360SDK", "联想SDK"}
VALID_PHASES = {"冒烟", "集成", "虎牙集成", "微软集成用例", "360集成用例",
                "联想集成用例", "增量", "待审核"}
VALID_AUTOMATION = {"", "待自动化", "已自动化", "已自动化但暂未配置", "未自动化", "未填写"}
SDK_PLATFORM_TO_PHASE = {
    "微软绿色版": "微软集成用例",
    "ARM微软绿色版": "微软集成用例",
    "360SDK": "360集成用例",
    "联想SDK": "联想集成用例",
}


def check_form_rules(tc: TestCase, all_cases: list[TestCase]) -> list[Issue]:
    issues: list[Issue] = []

    # FORM-META
    if not tc.id or not tc.id.upper().startswith("TC"):
        issues.append(Issue(tc.id or "?", tc.title, "FORM-M01", "BLOCKER",
                            "用例编号缺失或不符合 TC-{模块}-{编号} 格式",
                            "为用例补充 TC-xxx-001 形式的编号"))
    if not tc.title or len(tc.title) < 3:
        issues.append(Issue(tc.id, tc.title, "FORM-M02", "BLOCKER",
                            "用例标题缺失", "补充描述清晰的测试场景标题"))
    if not tc.priority:
        issues.append(Issue(tc.id, tc.title, "FORM-M03", "BLOCKER",
                            "用例未标注优先级", "标注 P0/P1/P2"))
    elif tc.priority.upper() not in {"P0", "P1", "P2"}:
        issues.append(Issue(tc.id, tc.title, "FORM-M07", "MAJOR",
                            f"优先级取值非法: {tc.priority}",
                            "仅允许 P0/P1/P2"))
    if not tc.module:
        issues.append(Issue(tc.id, tc.title, "FORM-M04", "CRITICAL",
                            "未标注所属模块", "补充 '模块 > 功能 > 子功能'"))
    if not tc.method:
        issues.append(Issue(tc.id, tc.title, "FORM-M05", "CRITICAL",
                            "未标注测试方法", "补充: 边界值/等价类/场景法/因果图/错误推测/正交实验"))
    if not tc.given:
        issues.append(Issue(tc.id, tc.title, "FORM-M06", "BLOCKER",
                            "缺失前置条件(Given)", "补充 Given"))
    if not tc.when:
        issues.append(Issue(tc.id, tc.title, "FORM-M06", "BLOCKER",
                            "缺失操作步骤(When)", "补充 When"))
    if not tc.then:
        issues.append(Issue(tc.id, tc.title, "FORM-M06", "BLOCKER",
                            "缺失预期结果(Then)", "补充 Then"))

    # FORM-TITLE
    title = tc.title
    if re.match(r"^(点击|输入|选择|打开|按下)", title):
        issues.append(Issue(tc.id, title, "FORM-T01", "CRITICAL",
                            "标题以操作动词起头，像操作步骤而非场景",
                            "改为描述用户场景/测试目的"))
    if len(title) < 6 or re.search(r"(测试|验证).{0,2}$", title) or "bug" in title.lower():
        issues.append(Issue(tc.id, title, "FORM-T02", "MAJOR",
                            f"标题过于模糊: '{title}'",
                            "明确描述用户场景，如'使用QQ账号登录并下载应用'"))
    # FORM-T04：When 含多页面 但标题无 "-页面名"
    page_hits_in_when = [p for p in PAGE_KEYWORDS if p in tc.when]
    if len(page_hits_in_when) >= 2 and "-" not in title:
        issues.append(Issue(tc.id, title, "FORM-T04", "CRITICAL",
                            f"用例涉及多个页面{page_hits_in_when}但标题未加'-场景名'区分",
                            "按页面拆分用例，标题加 '-首页'/'-我的' 等后缀"))

    # FORM-GIVEN
    if tc.given:
        # G01 依赖其他用例
        if re.search(r"TC[-_]\w+", tc.given) or "执行完" in tc.given or "执行 " in tc.given:
            issues.append(Issue(tc.id, title, "FORM-G01", "BLOCKER",
                                "Given 依赖其他用例",
                                "独立声明账号/环境/入口，不引用其他 TC"))
        # G02 选择性词语
        choice_hits = _find_choice_words(tc.given)
        if choice_hits:
            # G05 例外：兼容性用例整合
            is_compat = any(k in tc.method for k in ["兼容", "正交"]) or \
                        any(k in title for k in ["兼容性", "不同版本", "不同引擎"])
            if not is_compat:
                issues.append(Issue(tc.id, title, "FORM-G02", "CRITICAL",
                                    f"Given 含选择性词语: {choice_hits}",
                                    "拆分为独立用例，每条 Given 只描述一种前提"))
        # G03 不完整
        if len(tc.given.replace(" ", "")) < 8:
            issues.append(Issue(tc.id, title, "FORM-G03", "MAJOR",
                                "Given 描述过于简短",
                                "补充账号/入口/环境/数据"))
        # G05 假设词
        if any(w in tc.given for w in HYPOTHESIS_WORDS[:3]):
            issues.append(Issue(tc.id, title, "FORM-G05", "CRITICAL",
                                "Given 含假设词",
                                "Given 必须是确定的前置条件"))

    # FORM-WHEN
    if tc.when:
        choice_hits = _find_choice_words(tc.when)
        if choice_hits:
            issues.append(Issue(tc.id, title, "FORM-W01", "BLOCKER",
                                f"When 含选择性词语: {choice_hits}",
                                "拆分用例，每条用例只含一条确定的操作路径"))
        conj_hits = [w for w in CONJ_WORDS if w in tc.when]
        if conj_hits:
            issues.append(Issue(tc.id, title, "FORM-W02", "MAJOR",
                                f"When 含连词: {conj_hits}",
                                "拆成多步操作（表格多行）"))
        hyp_hits = [w for w in HYPOTHESIS_WORDS if w in tc.when]
        if hyp_hits:
            issues.append(Issue(tc.id, title, "FORM-W03", "CRITICAL",
                                f"When 含假设词: {hyp_hits}",
                                "操作必须是确定的指令"))
        result_hits = [w for w in RESULT_WORDS_IN_WHEN if w in tc.when]
        if result_hits:
            issues.append(Issue(tc.id, title, "FORM-W04", "MAJOR",
                                f"When 混入预期结果词: {result_hits}",
                                "将预期内容移动到 Then"))
        if not re.search(r"[点击输入选择拖拽打开关闭按下切换滑动长按双击]", tc.when):
            issues.append(Issue(tc.id, title, "FORM-W05", "CRITICAL",
                                "When 无明确操作动作",
                                "补充动宾结构：点击xxx / 输入xxx"))
        if len(page_hits_in_when) >= 2:
            issues.append(Issue(tc.id, title, "FORM-W06", "CRITICAL",
                                f"When 涉及多个页面: {page_hits_in_when}",
                                "按页面拆分用例"))

    # FORM-THEN
    if tc.then:
        for op in OP_STARTERS_IN_THEN:
            if re.search(rf"(^|[，。；])\s*{op}", tc.then):
                issues.append(Issue(tc.id, title, "FORM-TH01", "CRITICAL",
                                    f"Then 含操作步骤: '{op}'",
                                    "将操作移动到 When，Then 只描述结果"))
                break
        hyp_then = [w for w in HYPOTHESIS_IN_THEN if w in tc.then]
        if hyp_then:
            issues.append(Issue(tc.id, title, "FORM-TH02", "CRITICAL",
                                f"Then 含假设词: {hyp_then}",
                                "Then 必须是确定可判定的结果"))
        exp_then = [w for w in EXPLANATORY_IN_THEN if w in tc.then]
        if exp_then:
            issues.append(Issue(tc.id, title, "FORM-TH03", "MAJOR",
                                f"Then 含说明性词: {exp_then}",
                                "改为具体可验证的描述，如'按钮变为灰色且不可点击'"))
        gen_then = [w for w in GENERIC_IN_THEN if w in tc.then]
        if gen_then:
            issues.append(Issue(tc.id, title, "FORM-TH04", "MAJOR",
                                f"Then 含概括性词: {gen_then}",
                                "具体化结果描述"))
        # TH05 多检查点
        separators = len(re.findall(r"[；;]|、", tc.then))
        if separators >= 3 and len(tc.then) > 60:
            issues.append(Issue(tc.id, title, "FORM-TH05", "MAJOR",
                                f"Then 包含过多检查点（{separators+1}个）",
                                "拆分为多条用例，每条1个检查点"))

    # FORM-ATOM A03
    if re.search(r"任意|合适的|适当的|若干", tc.given + tc.when):
        issues.append(Issue(tc.id, title, "FORM-A03", "MAJOR",
                            "含模糊词'任意/合适的/若干'",
                            "使用具体的数据/数量"))

    return issues


def check_label_rules(tc: TestCase) -> list[Issue]:
    """标签合规性检查（LABEL-01~11，单用例级）"""
    issues: list[Issue] = []
    title = tc.title

    # LABEL-01 优先级
    if not tc.priority:
        issues.append(Issue(tc.id, title, "LABEL-01", "BLOCKER",
                            "优先级必填（P0/P1/P2）", "补充 优先级: P0/P1/P2"))
    elif tc.priority.upper() not in {"P0", "P1", "P2"}:
        issues.append(Issue(tc.id, title, "LABEL-01", "BLOCKER",
                            f"优先级取值非法: {tc.priority}", "仅允许 P0/P1/P2"))

    # LABEL-02 所属端必填
    if not tc.platforms:
        issues.append(Issue(tc.id, title, "LABEL-02", "BLOCKER",
                            "所属端必填（至少 1 个）",
                            "补充 所属端: PCYYB / ARM / 手助 / 微软绿色版 / ARM微软绿色版 / 360SDK / 联想SDK（可多值）"))
    else:
        # LABEL-03 所属端取值合法
        illegal_p = [p for p in tc.platforms if p not in VALID_PLATFORMS]
        if illegal_p:
            issues.append(Issue(tc.id, title, "LABEL-03", "CRITICAL",
                                f"所属端取值不在字典内: {illegal_p}",
                                f"合法取值: {sorted(VALID_PLATFORMS)}"))

    # LABEL-04 适用阶段必填
    if not tc.phases:
        issues.append(Issue(tc.id, title, "LABEL-04", "BLOCKER",
                            "适用阶段必填（至少 1 个）",
                            "补充 适用阶段: 冒烟/集成/虎牙集成/微软集成用例/360集成用例/联想集成用例/增量/待审核"))
    else:
        # LABEL-05 适用阶段取值合法
        illegal_ph = [p for p in tc.phases if p not in VALID_PHASES]
        if illegal_ph:
            issues.append(Issue(tc.id, title, "LABEL-05", "CRITICAL",
                                f"适用阶段取值不在字典内: {illegal_ph}",
                                f"合法取值: {sorted(VALID_PHASES)}"))

    # LABEL-07 冒烟⊆集成
    if "冒烟" in tc.phases and "集成" not in tc.phases:
        issues.append(Issue(tc.id, title, "LABEL-07", "MAJOR",
                            "冒烟用例未同时标'集成'（集成⊇冒烟）",
                            "补充适用阶段'集成'"))

    # LABEL-08 虎牙侧应含虎牙集成
    if tc.test_party and "虎牙" in tc.test_party:
        if "虎牙集成" not in tc.phases:
            issues.append(Issue(tc.id, title, "LABEL-08", "MAJOR",
                                "所属测试方=虎牙侧 但适用阶段未含'虎牙集成'",
                                "补充适用阶段'虎牙集成'"))

    # LABEL-09 SDK 端应打对应专属集成标签
    for p in tc.platforms:
        expected_phase = SDK_PLATFORM_TO_PHASE.get(p)
        if expected_phase and expected_phase not in tc.phases:
            issues.append(Issue(tc.id, title, "LABEL-09", "MAJOR",
                                f"所属端含 {p} 但适用阶段未打 '{expected_phase}'",
                                f"补充适用阶段 '{expected_phase}'"))

    # LABEL-11 自动化取值合法
    if tc.automation and tc.automation not in VALID_AUTOMATION:
        issues.append(Issue(tc.id, title, "LABEL-11", "MAJOR",
                            f"自动化取值非法: {tc.automation}",
                            "合法取值: 待自动化 / 已自动化 / 已自动化但暂未配置"))

    return issues


def _find_choice_words(text: str) -> list[str]:
    hits: list[str] = []
    for w in CHOICE_WORDS:
        if w in text:
            hits.append(w)
    if CHOICE_SLASH.search(text):
        hits.append("/(斜杠分隔)")
    return hits


def check_duplicates_and_priority(cases: list[TestCase]) -> list[Issue]:
    """检查 DRY + 优先级分布"""
    issues: list[Issue] = []
    n = len(cases)
    # A02: 相似度
    for i in range(n):
        for j in range(i + 1, n):
            sim = _similarity(cases[i], cases[j])
            if sim >= 0.85:
                issues.append(Issue(
                    cases[j].id, cases[j].title, "FORM-A02", "MAJOR",
                    f"与 {cases[i].id} 高度相似（{sim:.0%}）",
                    "检查是否重复验证同一点，合并或差异化"
                ))
    # 优先级分布
    priorities = [c.priority.upper() for c in cases if c.priority]
    total = len(priorities)
    if total > 0:
        p0 = priorities.count("P0") / total
        p1 = priorities.count("P1") / total
        p2 = priorities.count("P2") / total
        if p0 > 0.30:
            issues.append(Issue("-", "全集", "FORM-P01", "MAJOR",
                                f"P0 占比 {p0:.0%} > 30%，可能过度标记",
                                "复核非核心路径降为 P1"))
        if p0 < 0.10 and total >= 10:
            issues.append(Issue("-", "全集", "FORM-P01", "MAJOR",
                                f"P0 占比 {p0:.0%} < 10%，核心覆盖不足",
                                "识别核心主流程并提升为 P0"))
        if p1 < 0.50 and total >= 10:
            issues.append(Issue("-", "全集", "FORM-P02", "MAJOR",
                                f"P1 占比 {p1:.0%} < 50%，功能覆盖不足",
                                "补充功能完整性用例"))
        if p2 < 0.10 and total >= 10:
            issues.append(Issue("-", "全集", "FORM-P03", "MAJOR",
                                f"P2 占比 {p2:.0%} < 10%，异常/边界覆盖不足",
                                "补充异常/边界/特殊场景用例"))
    return issues


def _similarity(a: TestCase, b: TestCase) -> float:
    """基于 Given/When/Then 的 Jaccard 相似度"""
    def tokens(s: str) -> set[str]:
        return set(re.findall(r"[\w\u4e00-\u9fff]+", s))
    a_tokens = tokens(a.given + a.when + a.then)
    b_tokens = tokens(b.given + b.when + b.then)
    if not a_tokens or not b_tokens:
        return 0.0
    inter = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return inter / union if union else 0.0


# ============================================================
# 维度二：完整性检查（COV-*）
# ============================================================

# 对每类规则定义：特征 keywords → 必须覆盖的场景 → 关键词匹配检测
COMPLETENESS_RULES = [
    # 场景法 — 基本三档
    {"id": "COV-S01", "dim": "场景法", "scene": "主成功场景未覆盖",
     "must_exist_keywords": [["成功", "正常", "正确"]], "priority": "P0"},
    {"id": "COV-S03", "dim": "场景法", "scene": "分支失败场景未覆盖",
     "must_exist_keywords": [["失败", "错误", "异常"]], "priority": "P1"},
    {"id": "COV-S04", "dim": "场景法", "scene": "用户路径闭环（返回/取消/重试）未覆盖",
     "must_exist_keywords": [["返回", "取消", "重试", "关闭"]], "priority": "P1"},

    # 场景法 — 扩展（需 context.involves 含 scenario 或 e2e 才激活）
    {"id": "COV-S06", "dim": "场景法", "scene": "基本流（Basic Flow）未显式标注",
     "context_involves": ["scenario", "e2e"],
     "must_exist_keywords": [["基本流", "Basic Flow", "主流程", "主路径"]],
     "priority": "P0"},
    {"id": "COV-S07", "dim": "场景法", "scene": "备选流A（成功替代）未覆盖（不同方式达成同一目标）",
     "context_involves": ["scenario", "e2e"],
     "must_exist_keywords": [["备选流", "替代", "另一种方式", "Alt-A"]],
     "priority": "P1"},
    {"id": "COV-S08", "dim": "场景法", "scene": "备选流B（失败可恢复）未覆盖（错误→重试）",
     "context_involves": ["scenario", "e2e"],
     "must_exist_keywords": [["可恢复", "重试成功", "恢复后", "Alt-B"]],
     "priority": "P0"},
    {"id": "COV-S09", "dim": "场景法", "scene": "备选流C（失败终止）未覆盖（致命错误退出）",
     "context_involves": ["scenario", "e2e"],
     "must_exist_keywords": [["终止", "退出场景", "放弃", "Alt-C"]],
     "priority": "P1"},
    {"id": "COV-S10", "dim": "场景法", "scene": "备选流D（并行打断）未覆盖（切账号/来电/通知）",
     "context_involves": ["scenario", "e2e"],
     "must_exist_keywords": [["打断", "来电", "通知", "切账号", "Alt-D"]],
     "priority": "P1"},
    {"id": "COV-S11", "dim": "场景法", "scene": "数据驱动表未使用（多角色/多数据堆在一条用例）",
     "context_involves": ["scenario", "e2e", "data_driven"],
     "must_exist_keywords": [["数据驱动", "Examples", "数据集", "子编号", ".001", ".002"]],
     "priority": "P1"},
    {"id": "COV-S12", "dim": "场景法", "scene": "多通道入口未覆盖（UX-5：首页/搜索/分享/扫码/深链）",
     "context_involves": ["scenario", "e2e"],
     "must_exist_keywords": [["分享", "扫码", "深链", "deep link", "多入口"]],
     "priority": "P2"},

    # 边界值（依上下文 field_types 开启）
    {"id": "COV-B01", "dim": "边界值", "scene": "输入框：空/超长/纯空格场景未覆盖",
     "context_types": ["input_text"],
     "must_exist_keywords": [["空"], ["最大长度", "超长", "超出"], ["空格"]],
     "priority": "P0"},
    {"id": "COV-B02", "dim": "边界值", "scene": "数值输入：最小/最大/超边界未覆盖",
     "context_types": ["number"],
     "must_exist_keywords": [["最小"], ["最大"], ["超过", "超出"]],
     "priority": "P1"},
    {"id": "COV-B03", "dim": "边界值", "scene": "列表/分页：0项/最大项/分页边界未覆盖",
     "context_types": ["list"],
     "must_exist_keywords": [["空列表", "0 条", "没有"], ["分页"]],
     "priority": "P1"},
    {"id": "COV-B05", "dim": "边界值", "scene": "文件上传：空文件/超大/格式不符未覆盖",
     "context_types": ["file"],
     "must_exist_keywords": [["空文件"], ["超大", "最大"], ["格式", "类型"]],
     "priority": "P1"},
    {"id": "COV-B06", "dim": "边界值", "scene": "频控边界：阈值前/刚达/超过未覆盖",
     "context_involves": ["frequency"],
     "must_exist_keywords": [["上限", "频次", "频控"]],
     "priority": "P1"},

    # 等价类
    {"id": "COV-E01", "dim": "等价类", "scene": "用户分群（新/老/VIP）未覆盖",
     "must_exist_keywords": [["新用户"], ["老用户", "存量用户"]],
     "priority": "P1"},
    {"id": "COV-E02", "dim": "等价类", "scene": "登录态（QQ/微信/游客）未完整覆盖",
     "context_involves": ["login"],
     "must_exist_keywords": [["QQ"], ["微信"], ["未登录", "游客"]],
     "priority": "P0"},
    {"id": "COV-E03", "dim": "等价类", "scene": "APK/非APK类型未覆盖",
     "context_involves": ["download"],
     "must_exist_keywords": [["APK"], ["小游戏", "H5", "非APK", "快应用"]],
     "priority": "P1"},
    {"id": "COV-E04", "dim": "等价类", "scene": "安装状态（全新/升级/降级/卸载重装）未覆盖",
     "context_involves": ["install"],
     "must_exist_keywords": [["全新安装"], ["升级", "覆盖升级"], ["降级"], ["卸载重装", "卸载后"]],
     "priority": "P1"},
    {"id": "COV-E05", "dim": "等价类", "scene": "多语言输入（中/英/韩/emoji）未覆盖",
     "context_types": ["input_text"],
     "must_exist_keywords": [["英文"], ["韩语", "韩文"], ["emoji", "表情"]],
     "priority": "P1"},
    {"id": "COV-E07", "dim": "等价类", "scene": "特殊字符（XSS/SQL/敏感词）未覆盖",
     "context_types": ["input_text"],
     "must_exist_keywords": [["XSS", "脚本注入"], ["SQL", "注入"], ["敏感词"]],
     "priority": "P0"},

    # 错误推测
    {"id": "COV-ER01", "dim": "错误推测", "scene": "空值/NULL 场景未覆盖",
     "must_exist_keywords": [["空值", "NULL", "未填写"]],
     "priority": "P1"},
    {"id": "COV-ER02", "dim": "错误推测", "scene": "快速重复点击未覆盖",
     "must_exist_keywords": [["快速点击", "连续点击", "重复点击"]],
     "priority": "P2"},
    {"id": "COV-ER03", "dim": "错误推测", "scene": "页面快速切换未覆盖",
     "must_exist_keywords": [["快速切换", "切换页面", "快速滑动"]],
     "priority": "P2"},
    {"id": "COV-ER04", "dim": "错误推测", "scene": "强刷/刷新中请求未覆盖",
     "must_exist_keywords": [["强刷", "下拉刷新", "刷新中"]],
     "priority": "P2"},
    {"id": "COV-ER05", "dim": "错误推测", "scene": "杀进程/异常退出未覆盖",
     "must_exist_keywords": [["杀进程", "强制退出", "异常退出"]],
     "priority": "P2"},
    {"id": "COV-ER06", "dim": "错误推测", "scene": "权限拒绝后再次请求未覆盖",
     "context_involves": ["permission"],
     "must_exist_keywords": [["权限拒绝", "拒绝授权"]],
     "priority": "P1"},

    # 判定表覆盖（需 context.involves 含 decision_table 或 multi_condition 才激活）
    {"id": "COV-DT01", "dim": "判定表", "scene": "多条件决策业务未建立判定表（未见判定表用例）",
     "context_involves": ["decision_table"],
     "must_exist_keywords": [["判定表", "决策表", "规则 R", "规则R"]],
     "priority": "P0"},
    {"id": "COV-DT05", "dim": "判定表", "scene": "判定表 L2 覆盖不足（化简后每条规则应对应1条用例）",
     "context_involves": ["decision_table"],
     "must_exist_keywords": [["R1", "R2", "规则1", "规则2"]],
     "priority": "P0"},
    {"id": "COV-DT07", "dim": "判定表", "scene": "默认/兜底规则（未匹配任何规则时的行为）未覆盖",
     "context_involves": ["decision_table"],
     "must_exist_keywords": [["默认", "兜底", "未匹配", "fallback"]],
     "priority": "P1"},

    # 状态转换覆盖（需 context.involves 含 state_machine 或相应业务标记才激活）
    {"id": "COV-ST01", "dim": "状态转换", "scene": "流程性业务未建立状态机（未见状态机用例）",
     "context_involves": ["state_machine"],
     "must_exist_keywords": [["状态", "状态机", "state"]],
     "priority": "P0"},
    {"id": "COV-ST05", "dim": "状态转换", "scene": "L0 状态覆盖不足（每个状态应至少1条用例）",
     "context_involves": ["state_machine"],
     "must_exist_keywords": [["初始", "初始态"], ["终止", "终止态", "完成"]],
     "priority": "P0"},
    {"id": "COV-ST07", "dim": "状态转换", "scene": "L1 非法事件拒绝未覆盖（每状态下的非法事件）",
     "context_involves": ["state_machine"],
     "must_exist_keywords": [["非法事件", "非法操作", "忽略", "不响应", "禁用"]],
     "priority": "P1"},
    {"id": "COV-ST08", "dim": "状态转换", "scene": "L3 全有效路径未覆盖（初始态→终止态所有简单路径）",
     "context_involves": ["state_machine"],
     "must_exist_keywords": [["路径", "完整流程", "走完", "→"]],
     "priority": "P0"},
    {"id": "COV-ST09", "dim": "状态转换", "scene": "L4 循环路径未覆盖（暂停/继续/失败/重试等cycle）",
     "context_involves": ["state_machine"],
     "must_exist_keywords": [["循环", "多次", "反复", "重试", "暂停"]],
     "priority": "P0"},
    {"id": "COV-ST10", "dim": "状态转换", "scene": "异常打断恢复未覆盖（杀进程/断网/切账号打断后状态恢复）",
     "context_involves": ["state_machine"],
     "must_exist_keywords": [["恢复", "重启后", "重新进入", "续传"]],
     "priority": "P1"},
    {"id": "COV-ST11", "dim": "状态转换", "scene": "状态持久化未覆盖（重启后状态从持久化恢复）",
     "context_involves": ["state_machine"],
     "must_exist_keywords": [["持久化", "重启", "保留", "存储"]],
     "priority": "P1"},

    # 存储/磁盘/权限覆盖（需 context.involves 含 storage 才激活）
    {"id": "COV-STG-SPACE-01", "dim": "存储:空间", "scene": "磁盘完全满时写入/下载行为未覆盖",
     "context_involves": ["storage"],
     "must_exist_keywords": [["磁盘满", "空间不足", "磁盘已满", "存储满"]],
     "priority": "P0"},
    {"id": "COV-STG-SPACE-02", "dim": "存储:空间", "scene": "写入中途磁盘变满未覆盖",
     "context_involves": ["storage"],
     "must_exist_keywords": [["下载中磁盘满", "写入中变满", "中途空间不足"]],
     "priority": "P0"},
    {"id": "COV-STG-PERM-01", "dim": "存储:权限", "scene": "未申请存储权限直接访问未覆盖",
     "context_involves": ["storage"],
     "must_exist_keywords": [["未申请", "首次申请", "首次授权"]],
     "priority": "P0"},
    {"id": "COV-STG-PERM-02", "dim": "存储:权限", "scene": "用户拒绝存储权限的行为未覆盖",
     "context_involves": ["storage"],
     "must_exist_keywords": [["拒绝权限", "拒绝授权", "权限拒绝"]],
     "priority": "P0"},
    {"id": "COV-STG-PERM-03", "dim": "存储:权限", "scene": "运行中权限被撤销未覆盖",
     "context_involves": ["storage"],
     "must_exist_keywords": [["撤销权限", "撤回授权", "权限被撤销"]],
     "priority": "P1"},
    {"id": "COV-STG-PATH-01", "dim": "存储:路径", "scene": "中文/空格路径未覆盖",
     "context_involves": ["storage"],
     "must_exist_keywords": [["中文路径", "空格路径", "含空格", "中文目录"]],
     "priority": "P0"},
    {"id": "COV-STG-PATH-02", "dim": "存储:路径", "scene": "超长路径（>260字符）未覆盖",
     "context_involves": ["storage"],
     "must_exist_keywords": [["超长路径", "MAX_PATH", "260"]],
     "priority": "P1"},
    {"id": "COV-STG-PATH-03", "dim": "存储:路径", "scene": "移动介质拔出场景未覆盖（U盘/SD卡）",
     "context_involves": ["storage"],
     "must_exist_keywords": [["U盘拔出", "SD卡", "移动介质", "外接硬盘"]],
     "priority": "P2"},
    {"id": "COV-STG-INTEG-01", "dim": "存储:完整性", "scene": "写入中断（断电/杀进程）数据完整性未覆盖",
     "context_involves": ["storage"],
     "must_exist_keywords": [["写入中断", "断电", "杀进程后", "临时文件"]],
     "priority": "P0"},
    {"id": "COV-STG-CLEAN-01", "dim": "存储:清理", "scene": "卸载后数据彻底清除未验证（合规）",
     "context_involves": ["storage"],
     "must_exist_keywords": [["卸载后", "清除彻底", "无残留"]],
     "priority": "P0"},
    {"id": "COV-STG-QUOTA-01", "dim": "存储:上限", "scene": "本地存储上限（localStorage/SP）未覆盖",
     "context_involves": ["storage"],
     "must_exist_keywords": [["存储上限", "QuotaExceeded", "localStorage满", "配额"]],
     "priority": "P1"},
    {"id": "COV-STG-MIGRATE-01", "dim": "存储:迁移", "scene": "升级时数据迁移未覆盖",
     "context_involves": ["storage"],
     "must_exist_keywords": [["数据迁移", "旧版本数据", "schema 升级", "schema升级"]],
     "priority": "P0"},
]


def check_completeness(cases: list[TestCase], context: dict) -> list[MissingScenario]:
    missing: list[MissingScenario] = []
    # 全量用例文本拼接
    all_text = "\n".join([c.title + c.given + c.when + c.then + c.method for c in cases])
    field_types = set(context.get("field_types", []))
    involves = set(context.get("involves", []))

    for rule in COMPLETENESS_RULES:
        # 前置条件过滤
        if "context_types" in rule and not (set(rule["context_types"]) & field_types):
            continue
        if "context_involves" in rule and not (set(rule["context_involves"]) & involves):
            continue

        # 检查每组关键词是否都能匹配到至少一条用例
        missing_subs: list[str] = []
        for group in rule["must_exist_keywords"]:
            if not any(kw.lower() in all_text.lower() for kw in group):
                missing_subs.append("/".join(group))

        if missing_subs:
            scene = rule["scene"]
            if len(missing_subs) > 1:
                scene = f"{rule['scene']}（缺失：{', '.join(missing_subs)}）"
            missing.append(MissingScenario(
                dimension=rule["dim"],
                rule_id=rule["id"],
                scenario=scene,
                suggestion=f"补充关键词覆盖：{', '.join(missing_subs)}",
                priority=rule["priority"],
            ))
    return missing


# ============================================================
# 维度三：耦合场景检查（COUP-*）
# ============================================================

COUPLING_RULES = [
    # 下载
    {"id": "COUP-D01", "dim": "耦合:下载", "scene": "下载状态页面一致性（首页/我的/下载盒子）未覆盖",
     "involves": ["download"],
     "must_exist_keywords": [["首页"], ["我的"], ["下载盒子"]],
     "priority": "P0"},
    {"id": "COUP-D02", "dim": "耦合:下载", "scene": "下载状态机（暂停/继续/失败重试）未覆盖",
     "involves": ["download"],
     "must_exist_keywords": [["暂停"], ["继续"], ["失败", "重试"]],
     "priority": "P0"},
    {"id": "COUP-D03", "dim": "耦合:下载", "scene": "下载中切换登录态未覆盖",
     "involves": ["download", "login"],
     "must_exist_keywords": [["切换账号", "切换登录"]],
     "priority": "P1"},
    {"id": "COUP-D04", "dim": "耦合:下载", "scene": "下载中断网/恢复未覆盖",
     "involves": ["download"],
     "must_exist_keywords": [["断网", "网络中断"]],
     "priority": "P0"},
    {"id": "COUP-D05", "dim": "耦合:下载", "scene": "并发下载/队列调度未覆盖",
     "involves": ["download"],
     "must_exist_keywords": [["并发", "多任务", "队列"]],
     "priority": "P1"},

    # 登录
    {"id": "COUP-L01", "dim": "耦合:登录", "scene": "QQ/微信账号切换后数据/权限重置未覆盖",
     "involves": ["login"],
     "must_exist_keywords": [["切换账号", "切换登录", "切账号"]],
     "priority": "P0"},
    {"id": "COUP-L02", "dim": "耦合:登录", "scene": "游客→登录后数据合并未覆盖",
     "involves": ["login"],
     "must_exist_keywords": [["游客", "未登录后登录", "游客转"]],
     "priority": "P1"},
    {"id": "COUP-L03", "dim": "耦合:登录", "scene": "退出登录后本地数据清理未覆盖",
     "involves": ["login"],
     "must_exist_keywords": [["退出登录", "登出"]],
     "priority": "P1"},
    {"id": "COUP-L04", "dim": "耦合:登录", "scene": "Token 过期/刷新未覆盖",
     "involves": ["login"],
     "must_exist_keywords": [["token", "过期", "重登"]],
     "priority": "P1"},

    # 窗口
    {"id": "COUP-W01", "dim": "耦合:窗口", "scene": "窗口大小调整未覆盖",
     "involves": ["window"],
     "must_exist_keywords": [["窗口", "拖拽", "最大化", "最小化"]],
     "priority": "P1"},
    {"id": "COUP-W02", "dim": "耦合:窗口", "scene": "多屏拖拽/跨屏DPI 未覆盖",
     "involves": ["window"],
     "must_exist_keywords": [["多屏", "副屏", "跨屏"]],
     "priority": "P2"},

    # 网络
    {"id": "COUP-N01", "dim": "耦合:网络", "scene": "弱网加载未覆盖",
     "involves": ["network"],
     "must_exist_keywords": [["弱网"]],
     "priority": "P1"},
    {"id": "COUP-N02", "dim": "耦合:网络", "scene": "断网/离线降级未覆盖",
     "involves": ["network"],
     "must_exist_keywords": [["断网", "离线"]],
     "priority": "P1"},
    {"id": "COUP-N03", "dim": "耦合:网络", "scene": "网络切换（Wi-Fi↔4G/有线）未覆盖",
     "involves": ["network"],
     "must_exist_keywords": [["切换网络", "Wi-Fi", "4G", "有线"]],
     "priority": "P2"},
    {"id": "COUP-N04", "dim": "耦合:网络", "scene": "请求超时/重试未覆盖",
     "involves": ["network"],
     "must_exist_keywords": [["超时"]],
     "priority": "P1"},

    # 兼容性
    {"id": "COUP-C01", "dim": "耦合:兼容", "scene": "系统版本兼容矩阵缺失",
     "involves": ["compatibility"],
     "must_exist_keywords": [["Win10", "Windows 10"], ["Win11", "Windows 11"]],
     "priority": "P1"},
    {"id": "COUP-C02", "dim": "耦合:兼容", "scene": "安装版本兼容（升级/降级/卸载重装）未覆盖",
     "involves": ["install", "compatibility"],
     "must_exist_keywords": [["升级"], ["卸载重装", "卸载后"]],
     "priority": "P1"},
    {"id": "COUP-C03", "dim": "耦合:兼容", "scene": "虚拟化/渲染引擎（VBox/Hyper-V/NEMU + OpenGL/Vulkan/DX）未覆盖",
     "involves": ["compatibility"],
     "must_exist_keywords": [["VBox", "VirtualBox"], ["Hyper-V"], ["NEMU"]],
     "priority": "P1"},

    # 频控
    {"id": "COUP-F01", "dim": "耦合:频控", "scene": "频次限制边界未覆盖",
     "involves": ["frequency"],
     "must_exist_keywords": [["频控", "频次", "次数限制"]],
     "priority": "P1"},
    {"id": "COUP-F02", "dim": "耦合:频控", "scene": "时间窗（跨天/窗口刚过）未覆盖",
     "involves": ["frequency"],
     "must_exist_keywords": [["时间窗", "跨天", "一天内"]],
     "priority": "P2"},

    # 存储耦合（需 context.involves 含 storage）
    {"id": "COUP-STG01", "dim": "耦合:存储", "scene": "下载中磁盘满/权限撤销未覆盖",
     "involves": ["storage", "download"],
     "must_exist_keywords": [["下载中磁盘满", "下载中空间不足", "下载中权限"]],
     "priority": "P0"},
    {"id": "COUP-STG02", "dim": "耦合:存储", "scene": "切账号后私有数据隔离未覆盖",
     "involves": ["storage", "login"],
     "must_exist_keywords": [["切账号", "切换账号"], ["数据隔离", "私有数据"]],
     "priority": "P1"},
    {"id": "COUP-STG03", "dim": "耦合:存储", "scene": "卸载重装后数据不串账号/残留清零未覆盖",
     "involves": ["storage", "install"],
     "must_exist_keywords": [["卸载重装", "残留"]],
     "priority": "P1"},
    {"id": "COUP-STG04", "dim": "耦合:存储", "scene": "升级后数据迁移（读取旧数据）未覆盖",
     "involves": ["storage"],
     "must_exist_keywords": [["升级后", "覆盖升级"], ["数据迁移", "旧数据可读"]],
     "priority": "P0"},
    {"id": "COUP-STG05", "dim": "耦合:存储", "scene": "杀进程/断电后未完成写入不留损坏文件未覆盖",
     "involves": ["storage"],
     "must_exist_keywords": [["杀进程", "断电"], ["损坏", "临时文件"]],
     "priority": "P1"},
]


def check_coupling(cases: list[TestCase], context: dict) -> list[MissingScenario]:
    missing: list[MissingScenario] = []
    involves = set(context.get("involves", []))
    if not involves:
        return missing  # 未提供耦合上下文则跳过
    all_text = "\n".join([c.title + c.given + c.when + c.then for c in cases])

    for rule in COUPLING_RULES:
        rule_involves = set(rule["involves"])
        if not rule_involves.issubset(involves):
            continue  # 上下文未声明此耦合场景
        missing_subs: list[str] = []
        for group in rule["must_exist_keywords"]:
            if not any(kw.lower() in all_text.lower() for kw in group):
                missing_subs.append("/".join(group))
        if missing_subs:
            missing.append(MissingScenario(
                dimension=rule["dim"],
                rule_id=rule["id"],
                scenario=rule["scene"],
                suggestion=f"补充用例覆盖：{', '.join(missing_subs)}",
                priority=rule["priority"],
            ))
    return missing


# ============================================================
# 评分与结论
# ============================================================

SEVERITY_WEIGHT = {"BLOCKER": 10, "CRITICAL": 5, "MAJOR": 2, "MINOR": 1}


def score_and_verdict(cases: list[TestCase], issues: list[Issue],
                      missing: list[MissingScenario]) -> dict:
    total = len(cases) or 1
    blockers = sum(1 for i in issues if i.severity == "BLOCKER")
    criticals = sum(1 for i in issues if i.severity == "CRITICAL")
    majors = sum(1 for i in issues if i.severity == "MAJOR")

    # 扣分：按严重度加权 / 用例数
    penalty = sum(SEVERITY_WEIGHT.get(i.severity, 1) for i in issues) / total
    missing_p0 = sum(1 for m in missing if m.priority == "P0")
    missing_penalty = missing_p0 * 8 + sum(1 for m in missing if m.priority == "P1") * 3

    score = max(0, round(100 - penalty * 10 - missing_penalty, 1))

    non_compliant_cases = len({i.tc_id for i in issues if i.tc_id != "-"})
    non_compliance_rate = non_compliant_cases / total

    if blockers == 0 and non_compliance_rate < 0.05 and missing_p0 == 0:
        verdict = "PASS"
        verdict_label = "✅ 通过"
    elif blockers == 0 and non_compliance_rate < 0.15 and missing_p0 <= 2:
        verdict = "CONDITIONAL_PASS"
        verdict_label = "⚠️ 有条件通过"
    else:
        verdict = "REJECT"
        verdict_label = "❌ 打回修订"

    return {
        "total_cases": total,
        "issues_total": len(issues),
        "blockers": blockers,
        "criticals": criticals,
        "majors": majors,
        "missing_total": len(missing),
        "missing_p0": missing_p0,
        "non_compliant_cases": non_compliant_cases,
        "non_compliance_rate": round(non_compliance_rate, 3),
        "score": score,
        "verdict": verdict,
        "verdict_label": verdict_label,
    }


# ============================================================
# 报告渲染
# ============================================================

def render_markdown(cases: list[TestCase], issues: list[Issue],
                    missing: list[MissingScenario], summary: dict,
                    context: dict) -> str:
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    module = context.get("module", "未指定")
    lines.append(f"# 测试用例评审报告")
    lines.append("")
    lines.append(f"> 评审时间：{now}")
    lines.append(f"> 模块：{module} | 用例总数：{len(cases)}")
    lines.append("")

    # 汇总
    lines.append("## 📊 评审汇总")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 用例总数 | {summary['total_cases']} |")
    lines.append(f"| 不规范用例数 | {summary['non_compliant_cases']}（占比 {summary['non_compliance_rate']*100:.1f}%） |")
    lines.append(f"| 🔴 BLOCKER 问题 | {summary['blockers']} |")
    lines.append(f"| 🟠 CRITICAL 问题 | {summary['criticals']} |")
    lines.append(f"| 🟡 MAJOR 问题 | {summary['majors']} |")
    lines.append(f"| 缺失场景数 | {summary['missing_total']}（P0 缺失 {summary['missing_p0']}） |")
    lines.append(f"| 质量评分 | **{summary['score']} / 100** |")
    lines.append(f"| **评审结论** | **{summary['verdict_label']}** |")
    lines.append("")

    # 优先级分布
    if cases:
        p0 = sum(1 for c in cases if c.priority.upper() == "P0")
        p1 = sum(1 for c in cases if c.priority.upper() == "P1")
        p2 = sum(1 for c in cases if c.priority.upper() == "P2")
        total = len(cases)
        lines.append("### 优先级分布")
        lines.append(f"- P0: {p0} 条（{p0/total*100:.0f}%）")
        lines.append(f"- P1: {p1} 条（{p1/total*100:.0f}%）")
        lines.append(f"- P2: {p2} 条（{p2/total*100:.0f}%）")
        lines.append("")

    # 一、不规范点表格
    lines.append("## 一、用例不规范点清单")
    lines.append("")
    if not issues:
        lines.append("✅ 未发现规范性问题")
        lines.append("")
    else:
        lines.append(f"共 **{len(issues)}** 项不规范点：")
        lines.append("")
        lines.append("| # | 用例编号 | 用例标题 | 违反规则 | 严重度 | 具体问题 | 修复建议 |")
        lines.append("|---|----------|----------|----------|--------|----------|----------|")
        # 按严重度排序
        sev_order = {"BLOCKER": 0, "CRITICAL": 1, "MAJOR": 2, "MINOR": 3}
        sorted_issues = sorted(issues, key=lambda x: sev_order.get(x.severity, 99))
        for idx, it in enumerate(sorted_issues, 1):
            sev_icon = {"BLOCKER": "🔴", "CRITICAL": "🟠", "MAJOR": "🟡", "MINOR": "🔵"}.get(it.severity, "")
            lines.append(f"| {idx} | {it.tc_id} | {_md_escape(it.tc_title)} | {it.rule_id} | {sev_icon} {it.severity} | {_md_escape(it.description)} | {_md_escape(it.suggestion)} |")
        lines.append("")

    # 二、缺失场景表格
    lines.append("## 二、用例缺失场景清单")
    lines.append("")
    if not missing:
        lines.append("✅ 未发现缺失场景（在当前上下文范围内）")
        lines.append("")
    else:
        lines.append(f"共 **{len(missing)}** 项缺失场景：")
        lines.append("")
        lines.append("| # | 缺失维度 | 触发规则 | 缺失场景 | 建议补充 | 优先级 |")
        lines.append("|---|----------|----------|----------|----------|--------|")
        pri_order = {"P0": 0, "P1": 1, "P2": 2}
        sorted_missing = sorted(missing, key=lambda m: pri_order.get(m.priority, 99))
        for idx, m in enumerate(sorted_missing, 1):
            lines.append(f"| {idx} | {m.dimension} | {m.rule_id} | {_md_escape(m.scenario)} | {_md_escape(m.suggestion)} | {m.priority} |")
        lines.append("")

    # 三、改进建议摘要
    lines.append("## 三、改进建议摘要")
    lines.append("")
    if summary["blockers"] > 0:
        lines.append(f"- 🔴 优先修复 {summary['blockers']} 项 BLOCKER 问题（阻塞用例执行）")
    if summary["missing_p0"] > 0:
        lines.append(f"- 🔴 优先补充 {summary['missing_p0']} 项 P0 缺失场景")
    if summary["criticals"] > 0:
        lines.append(f"- 🟠 修复 {summary['criticals']} 项 CRITICAL 问题")
    if summary["non_compliance_rate"] >= 0.15:
        lines.append(f"- 🟠 规范合格率低（{(1-summary['non_compliance_rate'])*100:.0f}%），建议集中培训")
    lines.append("")
    lines.append("详细规则说明参见 `references/testcase-review.md`。")
    return "\n".join(lines)


def _md_escape(s: str) -> str:
    return md_escape(s)


# ============================================================
# CLI
# ============================================================

def load_context(path: str | None) -> dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if path.endswith((".yaml", ".yml")) and HAS_YAML:
        return yaml.safe_load(content) or {}
    try:
        return json.loads(content)
    except Exception:
        if HAS_YAML:
            return yaml.safe_load(content) or {}
        return {}


def main():
    parser = argparse.ArgumentParser(description="Test Case Reviewer")
    parser.add_argument("testcases", help="测试用例 Markdown 文件")
    parser.add_argument("--context", "-c", help="上下文 YAML/JSON（模块/涉及耦合/字段类型）")
    parser.add_argument("--output-md", default="testcase-review-report.md", help="Markdown 报告输出")
    parser.add_argument("--output-json", default="testcase-review-report.json", help="JSON 报告输出")
    args = parser.parse_args()

    if not os.path.exists(args.testcases):
        print(f"[ERROR] 用例文件不存在: {args.testcases}", file=sys.stderr)
        sys.exit(1)

    with open(args.testcases, "r", encoding="utf-8") as f:
        content = f.read()

    context = load_context(args.context)

    # 解析
    cases = parse_markdown_cases(content)
    if not cases:
        print("[WARN] 未解析出任何用例，请检查用例格式是否以 '### TC-xxx:' 开头", file=sys.stderr)

    # 规范性检查
    issues: list[Issue] = []
    for tc in cases:
        issues.extend(check_form_rules(tc, cases))
    issues.extend(check_duplicates_and_priority(cases))

    # 标签合规性检查（LABEL-*），通过 context.labels_required=true 或 involves 含 pcyyb 激活
    labels_required = context.get("labels_required", False) or \
                      "pcyyb" in [x.lower() for x in context.get("involves", [])] or \
                      context.get("module", "").lower().find("pcyyb") >= 0 or \
                      context.get("module", "").find("应用宝") >= 0
    if labels_required:
        for tc in cases:
            issues.extend(check_label_rules(tc))

    # 完整性检查
    missing = check_completeness(cases, context)

    # 耦合场景检查
    missing.extend(check_coupling(cases, context))

    # 汇总
    summary = score_and_verdict(cases, issues, missing)

    # Markdown
    md = render_markdown(cases, issues, missing, summary, context)
    with open(args.output_md, "w", encoding="utf-8") as f:
        f.write(md)

    # JSON
    report = {
        "review_id": f"REVIEW-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "generated_at": datetime.now().isoformat(),
        "context": context,
        "summary": summary,
        "cases_count": len(cases),
        "issues": [asdict(i) for i in issues],
        "missing_scenarios": [asdict(m) for m in missing],
    }
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 终端摘要
    print("=" * 60)
    print(f"评审完成: {args.testcases}")
    print("=" * 60)
    print(f"  用例总数      : {summary['total_cases']}")
    print(f"  不规范点      : {summary['issues_total']}（BLOCKER={summary['blockers']} CRITICAL={summary['criticals']} MAJOR={summary['majors']}）")
    print(f"  缺失场景      : {summary['missing_total']}（P0={summary['missing_p0']}）")
    print(f"  质量评分      : {summary['score']} / 100")
    print(f"  评审结论      : {summary['verdict_label']}")
    print(f"  Markdown 报告 : {args.output_md}")
    print(f"  JSON 报告     : {args.output_json}")

    # 返回码：REJECT 返回非 0 以便 CI/CD 卡关
    sys.exit(0 if summary["verdict"] != "REJECT" else 1)


if __name__ == "__main__":
    main()
