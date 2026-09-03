#!/usr/bin/env python3
"""
Quality Gate Checker - 质量门禁检查器

读取 code-scanner.py 输出的扫描报告 JSON，判断是否通过质量门禁。
在 CI/CD 流水线中作为卡点使用。

Usage:
    python check_gate.py <report.json> [--strict] [--max-critical N]

Exit codes:
    0 - 通过质量门禁
    1 - 未通过质量门禁 (存在BLOCKER)
    2 - 报告文件错误
"""

import json
import sys
import argparse
from pathlib import Path


SEVERITY_COLORS = {
    "BLOCKER": "\033[91m",   # Red
    "CRITICAL": "\033[93m",  # Yellow
    "MAJOR": "\033[94m",     # Blue
    "MINOR": "\033[90m",     # Gray
}
RESET = "\033[0m"
BOLD = "\033[1m"


def load_report(path: str) -> dict:
    """加载扫描报告"""
    p = Path(path)
    if not p.exists():
        print(f"Error: Report file not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in report: {e}", file=sys.stderr)
        sys.exit(2)


def print_summary(report: dict):
    """打印扫描摘要"""
    summary = report.get("summary", {})
    
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Code Quality Gate Report{RESET}")
    print(f"{'='*60}")
    print(f"  Target:      {report.get('target_dir', 'N/A')}")
    print(f"  Language:     {report.get('language', 'auto')}")
    print(f"  Files:        {summary.get('scanned_files', 0)} scanned / {summary.get('total_files', 0)} total")
    print(f"  Total Issues: {summary.get('total_issues', 0)}")
    print()
    
    # 按严重程度显示
    blockers = summary.get("blockers", 0)
    criticals = summary.get("criticals", 0)
    majors = summary.get("majors", 0)
    minors = summary.get("minors", 0)
    
    print(f"  {SEVERITY_COLORS['BLOCKER']}BLOCKER:  {blockers:>4}{RESET}  {'██' * min(blockers, 20)}")
    print(f"  {SEVERITY_COLORS['CRITICAL']}CRITICAL: {criticals:>4}{RESET}  {'██' * min(criticals, 20)}")
    print(f"  {SEVERITY_COLORS['MAJOR']}MAJOR:    {majors:>4}{RESET}  {'██' * min(majors, 20)}")
    print(f"  {SEVERITY_COLORS['MINOR']}MINOR:    {minors:>4}{RESET}  {'██' * min(minors, 20)}")
    print()
    
    score = summary.get("overall_score", 0)
    print(f"  Risk Score:   {score}")
    print()


def print_issues(report: dict, max_display: int = 20):
    """打印问题列表(按严重程度排序)"""
    files = report.get("files", [])
    if not files:
        return
    
    all_issues = []
    for f in files:
        for issue in f.get("issues", []):
            all_issues.append(issue)
    
    # 按严重程度排序
    severity_order = {"BLOCKER": 0, "CRITICAL": 1, "MAJOR": 2, "MINOR": 3}
    all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "MINOR"), 99))
    
    displayed = 0
    for issue in all_issues:
        if displayed >= max_display:
            remaining = len(all_issues) - displayed
            print(f"\n  ... and {remaining} more issues (see full report)")
            break
        
        sev = issue.get("severity", "MINOR")
        color = SEVERITY_COLORS.get(sev, "")
        
        print(f"  {color}[{sev}]{RESET} {issue.get('rule_id', '?')}: {issue.get('description', '')}")
        print(f"         {issue.get('file_path', '')}:{issue.get('line_number', 0)}")
        print(f"         Suggestion: {issue.get('suggestion', '')}")
        print()
        displayed += 1


def check_gate(report: dict, strict: bool = False, max_critical: int = -1) -> bool:
    """
    检查是否通过质量门禁
    
    默认规则:
      - BLOCKER > 0 → 不通过
      - strict模式: CRITICAL > max_critical → 不通过
    """
    summary = report.get("summary", {})
    blockers = summary.get("blockers", 0)
    criticals = summary.get("criticals", 0)
    
    passed = True
    reasons = []
    
    # BLOCKER 必须为0
    if blockers > 0:
        passed = False
        reasons.append(f"Found {blockers} BLOCKER issue(s) - must be 0 to pass")
    
    # strict模式检查CRITICAL数量
    if strict and max_critical >= 0:
        if criticals > max_critical:
            passed = False
            reasons.append(f"Found {criticals} CRITICAL issue(s) - max allowed: {max_critical}")
    
    return passed, reasons


def main():
    parser = argparse.ArgumentParser(description="Quality Gate Checker")
    parser.add_argument("report", help="Path to scan report JSON file")
    parser.add_argument("--strict", action="store_true", help="Enable strict mode (also check CRITICAL count)")
    parser.add_argument("--max-critical", type=int, default=5, help="Max allowed CRITICAL issues in strict mode (default: 5)")
    parser.add_argument("--max-display", type=int, default=20, help="Max issues to display (default: 20)")
    parser.add_argument("--quiet", action="store_true", help="Only output pass/fail result")
    args = parser.parse_args()
    
    report = load_report(args.report)
    
    if not args.quiet:
        print_summary(report)
        print_issues(report, args.max_display)
    
    passed, reasons = check_gate(report, args.strict, args.max_critical)
    
    print(f"\n{'='*60}")
    if passed:
        print(f"  {BOLD}\033[92m✅ QUALITY GATE: PASSED{RESET}")
    else:
        print(f"  {BOLD}\033[91m❌ QUALITY GATE: FAILED{RESET}")
        for r in reasons:
            print(f"     Reason: {r}")
    print(f"{'='*60}\n")
    
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
