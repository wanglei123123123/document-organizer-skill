#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testcase Mindmap Generator
==========================
把 Markdown 格式的测试用例集（testcase-template.md 规范）
自动转换为脑图 Markdown 大纲（testcase-mindmap-format.md 规范）。

脑图结构：
  # 根：需求名称
  ## F：场景
  ### S：用例标题 [P0] [Android/iOS]
  - G：前置条件           ← 可选
    - W：操作步骤
      - T：预期结果

使用：
  python testcase-mindmap-generator.py cases.md \\
      [--requirement-name "需求名称"] \\
      [--group-by module|method|priority] \\
      [--output mindmap.md]

可直接把输出复制粘贴到 XMind / MindMaster / 幕布 生成脑图。
"""

from __future__ import annotations
import argparse
import os
import re
import sys
from dataclasses import dataclass, field

# 公共工具函数
try:
    from utils import extract_single_label, extract_multi_label, extract_section
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from utils import extract_single_label, extract_multi_label, extract_section

CASE_HEADING = re.compile(r"^#{2,4}\s*(TC[-_][\w\-]+)[:\s：]+(.+)$", re.MULTILINE)


@dataclass
class Case:
    id: str = ""
    title: str = ""
    priority: str = ""
    module: str = ""
    method: str = ""
    platforms: list[str] = field(default_factory=list)  # 所属端（多值）
    phases: list[str] = field(default_factory=list)     # 适用阶段（多值）
    test_party: str = ""                                 # 所属测试方
    automation: str = ""                                 # 自动化状态
    given: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)  # [{when, data, then}]
    raw: str = ""


# ---------------- 解析 ----------------

def parse_cases(content: str) -> list[Case]:
    cases: list[Case] = []
    matches = list(CASE_HEADING.finditer(content))
    for i, m in enumerate(matches):
        tc_id = m.group(1)
        title = m.group(2).strip().strip("*").strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end]

        c = Case(id=tc_id, title=title, raw=body)

        # 提取优先级
        pm = re.search(r"\*{0,2}优先级\*{0,2}\s*[:：]\s*(P[0-3])", body)
        if pm:
            c.priority = pm.group(1)

        # 提取所属模块
        mm = re.search(r"\*{0,2}所属模块\*{0,2}\s*[:：]\s*(.+)", body)
        if mm:
            c.module = mm.group(1).strip()

        # 提取测试方法
        mt = re.search(r"\*{0,2}测试方法\*{0,2}\s*[:：]\s*(.+)", body)
        if mt:
            c.method = mt.group(1).strip()

        # 提取标签字段（testcase-labels.md 规范）
        c.platforms = extract_multi_label(body, ["所属端", "端", "platforms", "platform"])
        c.phases = extract_multi_label(body, ["适用阶段", "阶段", "phase", "phases"])
        party = extract_single_label(body, ["所属测试方", "测试方"])
        c.test_party = party.strip() if party else ""
        auto = extract_single_label(body, ["自动化", "automation"])
        c.automation = auto.strip() if auto else ""

        # 提取 Given（支持多条）
        c.given = _extract_given(body)

        # 提取 When/Then 步骤（优先解析表格，否则解析段落）
        c.steps = _extract_steps(body)

        cases.append(c)
    return cases




def _extract_given(body: str) -> list[str]:
    """提取 Given 前置条件（支持编号列表）"""
    pat = re.compile(
        r"\*{0,2}前置条件[^*]*\*{0,2}\s*[:：]\s*(.+?)(?=\n\s*-\s*\*|\n\|\s*步骤|\n##|\Z)",
        re.DOTALL
    )
    m = pat.search(body)
    if not m:
        return []
    text = m.group(1).strip()
    # 拆分编号条目（1. xxx / 2. xxx）
    items = re.split(r"\n\s*\d+\.\s+", "\n" + text)
    items = [x.strip(" -\n") for x in items if x.strip(" -\n")]
    return items


def _extract_steps(body: str) -> list[dict]:
    """提取 When/Then 步骤：优先解析 Markdown 表格"""
    # 查找表格区域 | 步骤 | 操作(When) | 测试数据 | 预期结果(Then) |
    lines = body.splitlines()
    header_idx = -1
    cols = {}
    for i, ln in enumerate(lines):
        if "|" in ln and ("操作" in ln or "When" in ln) and ("预期" in ln or "Then" in ln):
            header_cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            for j, cell in enumerate(header_cells):
                if re.search(r"步骤|#", cell): cols["step"] = j
                elif re.search(r"操作|When", cell, re.IGNORECASE): cols["when"] = j
                elif re.search(r"数据|Data", cell, re.IGNORECASE): cols["data"] = j
                elif re.search(r"预期|Then", cell, re.IGNORECASE): cols["then"] = j
            header_idx = i
            break
    if header_idx < 0:
        return _extract_steps_paragraph(body)

    steps: list[dict] = []
    for ln in lines[header_idx + 2:]:
        if "|" not in ln or ln.strip().startswith("#"):
            break
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        when = cells[cols["when"]] if "when" in cols and cols["when"] < len(cells) else ""
        data = cells[cols.get("data", -1)] if "data" in cols and cols["data"] < len(cells) else ""
        then = cells[cols["then"]] if "then" in cols and cols["then"] < len(cells) else ""
        if not (when or then):
            continue
        # Then 按分号/顿号/换行拆为多条断言
        thens = _split_thens(then)
        steps.append({
            "when": when,
            "data": data if data and data != "-" else "",
            "thens": thens,
        })
    return steps


def _extract_steps_paragraph(body: str) -> list[dict]:
    """段落形式：**操作步骤(When)**: ...  **预期结果(Then)**: ..."""
    when_m = re.search(
        r"\*{0,2}操作步骤[^*]*\*{0,2}\s*[:：]\s*(.+?)(?=\n\s*-\s*\*|\n##|\Z)",
        body, re.DOTALL
    )
    then_m = re.search(
        r"\*{0,2}预期结果[^*]*\*{0,2}\s*[:：]\s*(.+?)(?=\n\s*-\s*\*|\n##|\Z)",
        body, re.DOTALL
    )
    if not when_m:
        return []
    when = when_m.group(1).strip()
    then = then_m.group(1).strip() if then_m else ""
    return [{"when": when, "data": "", "thens": _split_thens(then)}]


def _split_thens(then_text: str) -> list[str]:
    if not then_text:
        return []
    # 按 分号 / 中文分号 / 换行 / 多于2空格 拆分
    parts = re.split(r"[；;]|\n", then_text)
    # 进一步按编号 "1. 2." 拆
    result: list[str] = []
    for p in parts:
        p = p.strip(" -•\n")
        if not p:
            continue
        sub = re.split(r"\s*\d+[\.、]\s+", p)
        for s in sub:
            s = s.strip(" -•\n")
            if s:
                result.append(s)
    return result


# ---------------- 输出 ----------------

def build_mindmap(cases: list[Case], requirement_name: str,
                  group_by: str = "module") -> str:
    """生成脑图 Markdown 大纲"""
    lines: list[str] = []
    lines.append(f"# {requirement_name}")
    lines.append("")

    # 按 group_by 分组
    groups: dict[str, list[Case]] = {}
    for c in cases:
        key = _group_key(c, group_by)
        groups.setdefault(key, []).append(c)

    # 组内排序：P0 > P1 > P2
    prio_order = {"P0": 0, "P1": 1, "P2": 2, "": 3}

    for group_name, group_cases in groups.items():
        lines.append(f"## F：{group_name}")
        lines.append("")
        sorted_cases = sorted(group_cases, key=lambda x: prio_order.get(x.priority.upper(), 9))
        for c in sorted_cases:
            lines.extend(_render_case(c))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _group_key(c: Case, group_by: str) -> str:
    if group_by == "module":
        if c.module:
            # 取最后一级作为场景名
            parts = re.split(r"[>›→》／/]", c.module)
            return parts[-1].strip() or "未分组"
        return "未分组"
    elif group_by == "method":
        return c.method or "未分组"
    elif group_by == "priority":
        return c.priority or "未分级"
    return "未分组"


def _render_case(c: Case) -> list[str]:
    # S 标题 + [label]，顺序固定：[优先级] [所属端] [适用阶段] [所属测试方]? [自动化]?
    labels = []
    if c.priority:
        labels.append(f"[{c.priority}]")
    if c.platforms:
        labels.append(f"[{','.join(c.platforms)}]")
    elif c.method:
        labels.append(f"[{c.method.split('-')[0].strip()}]")
    if c.phases:
        labels.append(f"[{','.join(c.phases)}]")
    if c.test_party:
        labels.append(f"[{c.test_party}]")
    if c.automation and c.automation not in {"未填写", "未自动化", ""}:
        labels.append(f"[{c.automation}]")
    label_str = " " + " ".join(labels) if labels else ""

    lines: list[str] = []
    # 简短标题：去掉冒号后半或保持原标题
    short_title = c.title.strip()
    lines.append(f"### S：{short_title}{label_str}")

    # 判断是否有 G
    has_given = bool(c.given)

    if has_given:
        # 若有多个 G，合并为一行（用分号分隔），保持层级简洁
        given_str = "；".join(c.given)
        lines.append(f"- G：{given_str}")
        indent_when = "  "
    else:
        indent_when = ""

    # When / Then — 规范要求：一个 S 下只能有 1 个 W
    # 若原用例有多步骤，合并为一段 W 文案（内联编号），所有 T 汇总到这个 W 下
    if c.steps:
        when_parts: list[str] = []
        all_thens: list[str] = []
        for idx, step in enumerate(c.steps, 1):
            when = (step.get("when") or "").strip() or "-"
            data = (step.get("data") or "").strip()
            piece = when
            if data:
                piece = f"{when}（数据：{data}）"
            # 多步骤内联编号
            if len(c.steps) > 1:
                piece = f"{idx}){piece}"
            when_parts.append(piece)
            all_thens.extend(step.get("thens", []))

        # 合并成一个 W 节点
        merged_when = "；".join(when_parts) if len(c.steps) > 1 else when_parts[0]
        lines.append(f"{indent_when}- W：{merged_when}")
        indent_then = indent_when + "  "
        # 去重保序，每条 T 独立子节点
        seen: set[str] = set()
        for t in all_thens:
            t = (t or "").strip()
            if not t or t in seen:
                continue
            seen.add(t)
            lines.append(f"{indent_then}- T：{t}")
    return lines


# ---------------- CLI ----------------

def main():
    parser = argparse.ArgumentParser(description="Testcase → Mindmap Markdown Generator")
    parser.add_argument("testcases", help="测试用例 Markdown 文件")
    parser.add_argument("--requirement-name", "-r", default="",
                        help="根节点名称（默认：从文件名推断）")
    parser.add_argument("--group-by", default="module",
                        choices=["module", "method", "priority"],
                        help="F 层分组方式（默认按模块）")
    parser.add_argument("--output", "-o", default="mindmap.md",
                        help="输出脑图 Markdown 文件（默认 mindmap.md）")
    args = parser.parse_args()

    if not os.path.exists(args.testcases):
        print(f"[ERROR] 用例文件不存在: {args.testcases}", file=sys.stderr)
        sys.exit(1)

    with open(args.testcases, "r", encoding="utf-8") as f:
        content = f.read()

    cases = parse_cases(content)
    if not cases:
        print("[WARN] 未解析出任何用例", file=sys.stderr)
        sys.exit(1)

    req_name = args.requirement_name
    if not req_name:
        # 尝试从文件第一个 H1 提取
        m = re.search(r"^#\s+(.+?)(?:\n|$)", content, re.MULTILINE)
        if m:
            req_name = m.group(1).strip()
        else:
            req_name = os.path.splitext(os.path.basename(args.testcases))[0]

    mindmap = build_mindmap(cases, req_name, args.group_by)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(mindmap)

    print("=" * 60)
    print(f"脑图已生成: {args.output}")
    print(f"  - 用例总数: {len(cases)}")
    print(f"  - 根节点:   {req_name}")
    print(f"  - 分组方式: {args.group_by}")
    print(f"  - 提示: 复制内容粘贴到 XMind / MindMaster / 幕布 即可生成脑图")


if __name__ == "__main__":
    main()
