#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared Utilities for Code Quality Gate Scripts
===============================================
公共工具函数，供 testcase-reviewer.py 和 testcase-mindmap-generator.py 共享。

包含：
  - 单值/多值标签字段提取
  - Markdown 段落/表格列提取
  - Given / When / Then 提取
"""

from __future__ import annotations
import re


# ============================================================
# 标签字段提取（testcase-labels.md 规范）
# ============================================================

def extract_single_label(body: str, labels: list[str]) -> str:
    """提取单值字段（所属测试方 / 自动化 / 优先级等），取一行。

    Args:
        body: 用例 Markdown 原文（单条用例范围）
        labels: 字段名候选列表，如 ["所属测试方", "测试方", "test_party"]

    Returns:
        提取到的值（已 strip），未匹配返回空字符串。
    """
    for lab in labels:
        pat = re.compile(
            rf"\*{{0,2}}{lab}\*{{0,2}}\s*[:：]\s*([^\n]*)",
            re.IGNORECASE,
        )
        m = pat.search(body)
        if m:
            val = m.group(1).strip().strip("*").strip()
            # 过滤"这行其实是下一个字段名被当成内容"的情况
            if val.startswith("-") or val.startswith("**"):
                return ""
            return val
    return ""


def extract_multi_label(body: str, labels: list[str]) -> list[str]:
    """提取多值字段（所属端 / 适用阶段），按中英文逗号/顿号/斜杠/空格分隔。

    Args:
        body: 用例 Markdown 原文（单条用例范围）
        labels: 字段名候选列表

    Returns:
        去重、去空后的值列表。
    """
    raw = extract_single_label(body, labels)
    if not raw:
        return []
    # 清理 Markdown 强调符号
    raw = raw.replace("*", "")
    # 去除括号说明，如 "PCYYB, ARM (多端)" → "PCYYB, ARM"
    raw = re.sub(r"\([^)]*\)", "", raw)
    raw = re.sub(r"（[^）]*）", "", raw)
    # 按常见分隔符切分
    items = re.split(r"[,，、/|\s]+", raw)
    return [i.strip() for i in items if i.strip()]


# ============================================================
# Markdown 段落/表格提取
# ============================================================

def extract_section(body: str, labels: list[str]) -> str:
    """提取 **前置条件(Given)** 等 Markdown 段落文本。

    Args:
        body: 用例 Markdown 原文
        labels: 段落标题候选列表

    Returns:
        段落正文（已 strip），未匹配返回空字符串。
    """
    for lab in labels:
        pat = re.compile(
            rf"\*{{0,2}}{lab}[^*]*\*{{0,2}}\s*[:：]\s*(.+?)(?=\n\s*-\s*\*|\n\|\s*步骤|\n##|\Z)",
            re.DOTALL,
        )
        m = pat.search(body)
        if m:
            return m.group(1).strip()
    return ""


def extract_table_column(body: str, col_keywords: list[str]) -> str:
    """从 Markdown 表格中提取指定列的所有单元格（拼接为一行）。

    Args:
        body: 用例 Markdown 原文
        col_keywords: 列头关键词列表

    Returns:
        " | " 拼接的所有单元格内容。
    """
    lines = body.splitlines()
    header_idx = -1
    col_idx = -1
    for i, ln in enumerate(lines):
        if "|" in ln and any(kw in ln for kw in col_keywords):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            for j, c in enumerate(cells):
                if any(kw in c for kw in col_keywords):
                    header_idx = i
                    col_idx = j
                    break
            if header_idx >= 0:
                break
    if header_idx < 0:
        return ""
    collected: list[str] = []
    for ln in lines[header_idx + 2:]:  # 跳过分隔行
        if "|" not in ln or ln.strip().startswith("#") or ln.strip().startswith("-"):
            if collected:
                break
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if col_idx < len(cells):
            val = cells[col_idx]
            if val and val != "-":
                collected.append(val)
    return " | ".join(collected)


# ============================================================
# Markdown 转义
# ============================================================

def md_escape(s: str) -> str:
    """转义 Markdown 表格中的特殊字符。"""
    return s.replace("|", "\\|").replace("\n", " ")
