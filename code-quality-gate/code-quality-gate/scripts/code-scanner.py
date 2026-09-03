#!/usr/bin/env python3
"""
Code Quality Gate Scanner - 代码质量测试卡点扫描器

将经典测试方法论(边界值、等价类、因果图、错误推测等)固化为可执行的
代码扫描规则，作为研发提测前的自动化质量门禁。

Usage:
    python code-scanner.py <target_directory> [--lang LANGUAGE] [--output FORMAT] [--config CONFIG_FILE]

Examples:
    python code-scanner.py ./src --lang python
    python code-scanner.py ./src --lang java --output json
    python code-scanner.py ./src --lang javascript --config rules-config.yaml
"""

import os
import re
import sys
import json
import argparse
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Tuple, Set
from collections import defaultdict


# ============================================================
# 数据模型定义
# ============================================================

class Severity(Enum):
    BLOCKER = "BLOCKER"
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class RuleCategory(Enum):
    INPUT = "INPUT"
    NULL = "NULL"
    BOUNDARY = "BOUNDARY"
    EXCEPTION = "EXCEPTION"
    LOGIC = "LOGIC"
    RESOURCE = "RESOURCE"
    STORAGE = "STORAGE"
    CONCURRENT = "CONCURRENT"
    SECURITY = "SECURITY"
    AI_CODE = "AI-CODE"
    PERF = "PERF"


SEVERITY_ORDER = {Severity.BLOCKER: 0, Severity.CRITICAL: 1, Severity.MAJOR: 2, Severity.MINOR: 3}
SEVERITY_SCORE = {Severity.BLOCKER: 10, Severity.CRITICAL: 5, Severity.MAJOR: 2, Severity.MINOR: 0.5}


@dataclass
class ScanIssue:
    rule_id: str
    rule_name: str
    category: str
    severity: str
    file_path: str
    line_number: int
    line_content: str
    description: str
    suggestion: str
    method_source: str
    language: str

    def to_dict(self):
        return asdict(self)


@dataclass
class FileScanResult:
    file_path: str
    language: str
    total_lines: int
    issues: List[ScanIssue] = field(default_factory=list)

    @property
    def blocker_count(self): return sum(1 for i in self.issues if i.severity == "BLOCKER")
    @property
    def critical_count(self): return sum(1 for i in self.issues if i.severity == "CRITICAL")
    @property
    def major_count(self): return sum(1 for i in self.issues if i.severity == "MAJOR")
    @property
    def minor_count(self): return sum(1 for i in self.issues if i.severity == "MINOR")
    @property
    def score(self):
        return sum(SEVERITY_SCORE.get(Severity(i.severity), 0) for i in self.issues)
    @property
    def has_blocker(self): return self.blocker_count > 0


@dataclass
class ScanReport:
    target_dir: str
    language: str
    total_files: int = 0
    scanned_files: int = 0
    skipped_files: int = 0
    total_issues: int = 0
    file_results: List[FileScanResult] = field(default_factory=list)
    
    @property
    def total_blockers(self): return sum(r.blocker_count for r in self.file_results)
    @property
    def total_criticals(self): return sum(r.critical_count for r in self.file_results)
    @property
    def total_majors(self): return sum(r.major_count for r in self.file_results)
    @property
    def total_minors(self): return sum(r.minor_count for r in self.file_results)
    @property
    def overall_score(self): return sum(r.score for r in self.file_results)
    @property
    def pass_gate(self): return self.total_blockers == 0
    
    def to_dict(self):
        return {
            "target_dir": self.target_dir,
            "language": self.language,
            "summary": {
                "total_files": self.total_files,
                "scanned_files": self.scanned_files,
                "skipped_files": self.skipped_files,
                "total_issues": self.total_issues,
                "blockers": self.total_blockers,
                "criticals": self.total_criticals,
                "majors": self.total_majors,
                "minors": self.total_minors,
                "overall_score": round(self.overall_score, 1),
                "pass_gate": self.pass_gate
            },
            "files": [
                {
                    "file_path": r.file_path,
                    "language": r.language,
                    "total_lines": r.total_lines,
                    "issue_counts": {
                        "BLOCKER": r.blocker_count,
                        "CRITICAL": r.critical_count,
                        "MAJOR": r.major_count,
                        "MINOR": r.minor_count
                    },
                    "score": round(r.score, 1),
                    "issues": [i.to_dict() for i in r.issues]
                }
                for r in self.file_results if r.issues
            ]
        }


# ============================================================
# 语言检测与文件过滤
# ============================================================

LANG_EXTENSIONS = {
    'python': {'.py'},
    'java': {'.java'},
    'javascript': {'.js'},
    'typescript': {'.ts', '.tsx'},
    'go': {'.go'},
    'c': {'.c', '.h'},
    'cpp': {'.cpp', '.cc', '.cxx', '.hpp'},
    'rust': {'.rs'},
    'swift': {'.swift'},
    'ruby': {'.rb'},
    'kotlin': {'.kt', '.kts'},
    'scala': {'.scala'},
}

def detect_language(file_path: Path) -> Optional[str]:
    ext = file_path.suffix.lower()
    for lang, extensions in LANG_EXTENSIONS.items():
        if ext in extensions:
            return lang
    return None


def should_scan(file_path: Path, lang: Optional[str] = None) -> bool:
    """判断文件是否应该被扫描"""
    # 跳过非代码文件
    detected = detect_language(file_path)
    if not detected:
        return False
    
    # 如果指定了语言，只扫描匹配的文件
    if lang and detected != lang:
        return False
    
    # 跳过生成的文件、vendor、node_modules等
    skip_patterns = [
        '/node_modules/', '/venv/', '/__pycache__/', '/.git/',
        '/vendor/', '/third_party/', '/dist/', '/build/',
        '/.next/', '/.cache/',
        '/migrations/',  # 通常不扫描迁移文件
    ]
    fp_str = str(file_path).replace('\\', '/')
    for pattern in skip_patterns:
        if pattern in fp_str:
            return False
    
    # 跳过过大的文件 (>200KB)
    if file_path.stat().st_size > 200 * 1024:
        return False
    
    return True


# ============================================================
# 规则定义 - 每条规则对应测试方法论中的一个具体检查点
# ============================================================

class Rule:
    """单条扫描规则"""
    def __init__(self, rule_id: str, name: str, category: RuleCategory,
                 severity: Severity, method_source: str, languages: Set[str],
                 description: str, suggestion: str,
                 pattern: re.Pattern | None = None, check_func=None):
        self.rule_id = rule_id
        self.name = name
        self.category = category
        self.severity = severity
        self.method_source = method_source
        self.languages = languages
        self.pattern = pattern
        self.check_func = check_func
        self.description = description
        self.suggestion = suggestion
    
    def applies_to(self, lang: str) -> bool:
        return 'ALL' in self.languages or lang.lower() in self.languages


def build_rules() -> List[Rule]:
    """构建所有扫描规则库"""
    rules = []
    ALL_LANGS = {'ALL'}
    DYNAMIC_LANGS = {'ALL', 'python', 'javascript', 'typescript'}
    STATIC_LANGS = {'ALL', 'java', 'c', 'cpp', 'go', 'rust', 'kotlin'}

    # ========================================
    # INPUT 组 - 输入验证规则 (等价类划分 + 边界值分析)
    # ========================================

    rules.append(Rule(
        rule_id="INPUT-01", name="外部输入类型校验缺失",
        category=RuleCategory.INPUT, severity=Severity.BLOCKER,
        method_source="等价类划分", languages=DYNAMIC_LANGS,
        description="来自外部的输入在使用前未进行类型检查",
        suggestion="添加 isinstance()/typeof 类型校验",
        check_func=_check_input_type_validation
    ))

    rules.append(Rule(
        rule_id="INPUT-02", name="参数范围校验缺失",
        category=RuleCategory.INPUT, severity=Severity.BLOCKER,
        method_source="边界值分析", languages=ALL_LANGS,
        description="数值型参数参与运算前无范围合法性校验",
        suggestion="使用前添加 if value < MIN or value > MAX 检查",
        check_func=_check_numeric_range_validation
    ))

    rules.append(Rule(
        rule_id="INPUT-03", name="枚举/状态处理不完备",
        category=RuleCategory.INPUT, severity=Severity.CRITICAL,
        method_source="等价类划分", languages=ALL_LANGS,
        description="switch/if-elif 未覆盖所有已知的状态值或缺少default/else兜底",
        suggestion="补全所有case分支并添加default抛出异常",
        check_func=_check_enum_completeness
    ))

    rules.append(Rule(
        rule_id="INPUT-04", name="字符串长度未限制",
        category=RuleCategory.INPUT, severity=Severity.CRITICAL,
        method_source="边界值分析", languages=ALL_LANGS,
        description="外部字符串未经截断直接用于DB/文件/网络写入",
        suggestion="使用 value[:MAX_LEN] 截断后再使用",
        check_func=_check_string_length_limit
    ))

    # ========================================
    # NULL 组 - 空值安全规则 (错误推测法)
    # ========================================

    rules.append(Rule(
        rule_id="NULL-01", name="可能空值的解引用风险",
        category=RuleCategory.NULL, severity=Severity.BLOCKER,
        method_source="错误推测法", languages=DYNAMIC_LANGS,
        description="对可能为None/null/undefined的对象进行属性访问或方法调用",
        suggestion="使用前添加 if obj is not None 或可选链 obj?.method()",
        check_func=_check_null_dereference
    ))

    rules.append(Rule(
        rule_id="NULL-02", name="集合/数组越界访问",
        category=RuleCategory.NULL, severity=Severity.BLOCKER,
        method_source="边界值分析", languages=ALL_LANGS,
        description="通过索引访问集合元素时未检查索引有效性和集合非空",
        suggestion="访问前检查 len(arr)>index 和 arr 非空; 使用 .get(index, default)",
        check_func=_check_array_bounds
    ))

    rules.append(Rule(
        rule_id="NULL-03", name="链式调用空指针风险",
        category=RuleCategory.NULL, severity=Severity.CRITICAL,
        method_source="错误推测法", languages=DYNAMIC_LANGS,
        description="多级方法链(a.b.c.d)中间环节可能返回null导致NPE",
        suggestion="拆分为多步并每步检查,或使用Optional/可选链",
        check_func=_check_chain_call_npe
    ))

    # ========================================
    # BOUNDARY 组 - 边界处理规则 (边界值分析法)
    # ========================================

    rules.append(Rule(
        rule_id="BOUND-04", name="除法运算除零保护缺失",
        category=RuleCategory.BOUNDARY, severity=Severity.BLOCKER,
        method_source="错误推测法", languages=ALL_LANGS,
        description="除法(/, //, %)的除数可能是零且未做零值检查",
        suggestion="添加 if divisor == 0 保护, 使用 safe_divide 工具函数",
        check_func=_check_division_by_zero
    ))

    # ========================================
    # EXCEPTION 组 - 异常处理规则 (错误推测法)
    # ========================================

    rules.append(Rule(
        rule_id="EXCP-01", name="空catch块（异常被静默吞掉）",
        category=RuleCategory.EXCEPTION, severity=Severity.CRITICAL,
        method_source="错误推测法", languages={'ALL', 'python', 'java', 'javascript', 'typescript'},
        description="catch块为空或仅有注释,异常被完全忽略导致问题难以排查",
        suggestion="至少记录日志 logger.error(e),或重新抛出,或返回明确错误码",
        check_func=_check_empty_catch
    ))

    rules.append(Rule(
        rule_id="EXCP-02", name="宽泛异常捕获(Exception/e/Throwable)",
        category=RuleCategory.EXCEPTION, severity=Severity.MAJOR,
        method_source="错误推测法", languages={'ALL', 'python', 'java'},
        description="使用过于宽泛的异常类型捕获,可能掩盖真正的程序错误",
        suggestion="替换为具体的异常类型(FileNotFoundError, ValueError等)",
        check_func=_check_broad_exception
    ))

    rules.append(Rule(
        rule_id="EXCP-03", name="异常后资源未释放",
        category=RuleCategory.EXCEPTION, severity=Severity.CRITICAL,
        method_source="错误推测法", languages={'ALL', 'python', 'java', 'csharp'},
        description="打开的资源在异常发生时未能关闭(无try-with/with/using)",
        suggestion="Python用 with statement, Java用 try-with-resources, C#用 using",
        check_func=_check_resource_not_released
    ))

    # ========================================
    # LOGIC 组 - 逻辑完整性规则 (因果图 + 错误推测)
    # ========================================

    rules.append(Rule(
        rule_id="LOGIC-02", name="switch语句缺少default分支",
        category=RuleCategory.LOGIC, severity=Severity.CRITICAL,
        method_source="等价类划分", languages={'ALL', 'java', 'c', 'cpp', 'go', 'swift', 'kotlin'},
        description="switch/case缺少default分支,无法处理意外值",
        suggestion='添加 default: throw new IllegalArgumentException("Unexpected")',
        check_func=_check_switch_no_default
    ))

    rules.append(Rule(
        rule_id="LOGIC-05", name="条件判断永真/永假(死代码)",
        category=RuleCategory.LOGIC, severity=Severity.CRITICAL,
        method_source="错误推测法", languages=ALL_LANGS,
        description="if条件恒为true或false,说明存在逻辑错误或死代码",
        suggestion="检查是否==误写为=(赋值),移除死代码,修正逻辑表达式",
        check_func=_check_always_true_false
    ))

    # ========================================
    # RESOURCE 组 - 资源管理规则 (错误推测法)
    # ========================================

    rules.append(Rule(
        rule_id="RESC-01", name="IO资源未使用安全释放模式",
        category=RuleCategory.RESOURCE, severity=Severity.CRITICAL,
        method_source="错误推测法", languages={'ALL', 'python', 'java', 'csharp'},
        description="文件/连接/流资源未使用with/try-with/using安全释放模式",
        suggestion="Python: with open(...) as f:, Java: try (... is = ...)",
        check_func=_check_unsafe_resource
    ))

    # ========================================
    # SECURITY 组 - 安全规则 (AI缺陷模式 + 缺陷库)
    # ========================================

    rules.append(Rule(
        rule_id="SECU-01", name="SQL注入风险(字符串拼接)",
        category=RuleCategory.SECURITY, severity=Severity.BLOCKER,
        method_source="AI缺陷模式(#1)", languages=ALL_LANGS,
        description="使用字符串拼接构建SQL查询,用户输入可直接注入SQL",
        suggestion="全部改为参数化查询: ? / :param / #{param}",
        check_func=_check_sql_injection
    ))

    rules.append(Rule(
        rule_id="SECU-02", name="XSS风险(用户输入直接渲染HTML)",
        category=RuleCategory.SECURITY, severity=Severity.BLOCKER,
        method_source="AI缺陷模式(#3)", languages={'ALL', 'javascript', 'typescript', 'java', 'python'},
        description="用户输入不经转义直接innerHTML/dangerouslySetInnerHTML渲染",
        suggestion="使用textContent替代innerHTML;模板引擎开启auto-escape",
        check_func=_check_xss_risk
    ))

    rules.append(Rule(
        rule_id="SECU-03", name="硬编码密钥/凭证",
        category=RuleCategory.SECURITY, severity=Severity.CRITICAL,
        method_source="AI缺陷模式(#4)", languages=ALL_LANGS,
        description="API Key/密码/Token以明文硬编码在源码中",
        suggestion="改用环境变量 os.getenv('SECRET_KEY') 或密钥管理系统",
        check_func=_check_hardcoded_secrets
    ))

    rules.append(Rule(
        rule_id="SECU-07", name="敏感信息日志输出",
        category=RuleCategory.SECURITY, severity=Severity.CRITICAL,
        method_source="AI缺陷模式(#4)", languages=ALL_LANGS,
        description="日志中打印了password/token/身份证号/银行卡号等敏感数据",
        suggestion="密码绝对不出现在任何日志中;使用脱敏函数mask_sensitive()",
        check_func=_check_sensitive_logging
    ))

    # ========================================
    # AI-CODE 组 - AI代码专项规则 (AI缺陷模式库)
    # ========================================

    rules.append(Rule(
        rule_id="AICD-02", name="只处理happy path无异常路径",
        category=RuleCategory.AI_CODE, severity=Severity.CRITICAL,
        method_source="AI缺陷模式(#1 出现率35%)", languages=DYNAMIC_LANGS,
        description="函数只实现了正常流程,缺少异常/边缘情况处理(AI典型问题)",
        suggestion="为每个I/O/网络/DB操作添加try-except和fallback",
        check_func=_check_happy_path_only
    ))

    rules.append(Rule(
        rule_id="AICD-06", name="魔法数字(Magic Number)未提取常量",
        category=RuleCategory.AI_CODE, severity=Severity.MAJOR,
        method_source="AI缺陷模式", languages=ALL_LANGS,
        description="代码中出现含义不明的数字字面量,影响可读性和维护性",
        suggestion="定义命名常量 MAX_RETRY=3, TIMEOUT=30 等",
        check_func=_check_magic_numbers
    ))

    # ========================================
    # PERF 组 - 性能规则 (缺陷模式 + 边界值)
    # ========================================

    rules.append(Rule(
        rule_id="PERF-01", name="N+1查询问题(循环内数据库操作)",
        category=RuleCategory.PERF, severity=Severity.CRITICAL,
        method_source="缺陷模式库", languages=ALL_LANGS,
        description="循环体内执行DB查询,N条数据触发N+1次查询",
        suggestion="改为批量查询 WHERE IN (...) / batch_get / eager loading",
        check_func=_check_n_plus_one_query
    ))

    rules.append(Rule(
        rule_id="PERF-04", name="字符串循环拼接(O(n²)复杂度)",
        category=RuleCategory.PERF, severity=Severity.MAJOR,
        method_source="边界值分析", languages={'ALL', 'python', 'java', 'javascript'},
        description="循环中使用+=拼接字符串,时间复杂度为O(n²)",
        suggestion="Python用join(),Java用StringBuilder,JS用Array.join()",
        check_func=_check_string_loop_concat
    ))

    return rules


# ============================================================
# 规则检查函数实现
# ============================================================

def _get_lines_content(lines: List[str], start: int, context: int = 3) -> str:
    """获取指定行附近的代码内容"""
    begin = max(0, start - context)
    end = min(len(lines), start + context + 1)
    return ''.join(f"{i+1}:{lines[i]}" for i in range(begin, end))


# --- INPUT-01: 外部输入类型校验 ---
def _check_input_type_validation(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    if lang not in ('python', 'javascript', 'typescript'):
        return issues
    
    # Python: 检测使用了外部输入但无isinstance/type检查的函数
    if lang == 'python':
        func_pattern = re.compile(r'^\s*def\s+(\w+)\s*\([^)]*\)\s*:', re.MULTILINE)
        input_patterns = [
            (r'request\.(args|form|json|data|values)', 'Flask/Django request'),
            (r'input\s*\(', 'user input'),
            (r'os\.getenv|os\.environ', 'environment variable'),
            (r'sys\.argv', 'command line arg'),
        ]
        
        for match in func_pattern.finditer(content):
            func_start = content[:match.start()].count('\n')
            # 找到函数体结束位置(简化:找下一个同级def/class或文件末尾)
            func_end = len(lines)
            for i in range(match.end(), len(content)):
                m = re.match(r'^(\s*)def |^(\s*)class ', content[i:], re.MULTILINE)
                if m and len(m.group(1) or m.group(2)) <= len(re.match(r'^(\s*)', lines[func_start]).group(1)):
                    func_end = content[:i].count('\n')
                    break
            
            func_body = '\n'.join(lines[func_start:min(func_end, func_start+80)])
            
            for pat, desc in input_patterns:
                if re.search(pat, func_body):
                    if not re.search(r'isinstance|type\s*[\(\[]|typing\.', func_body):
                        issues.append(ScanIssue(
                            rule_id="INPUT-01", rule_name="外部输入类型校验缺失",
                            category="INPUT", severity="BLOCKER",
                            file_path=str(filepath), line_number=func_start + 1,
                            line_content=lines[func_start].strip(),
                            description=f"函数 '{match.group(1)}' 使用了{desc}但缺少类型校验(isinstance/type)",
                            suggestion="添加: if not isinstance(value, expected_type): raise TypeError(...)",
                            method_source="等价类划分", language=lang
                        ))
                        break
    
    elif lang in ('javascript', 'typescript'):
        # JS/TS: 检测 req.body/req.query 等无 typeof 检查
        func_pattern = re.compile(r'(?:function\s+\w+|(?:const|let|var)\s+\w+\s*=|(?:async\s+)?\([^)]*\)\s*=>)')
        for match in func_pattern.finditer(content):
            line_num = content[:match.start()].count('\n')
            # 简化的函数体范围查找(向后50行)
            end_line = min(len(lines), line_num + 50)
            func_body = '\n'.join(lines[line_num:end_line])
            
            if re.search(r'req\.(body|query|params)', func_body):
                if not re.search(r'typeof\s+', func_body):
                    issues.append(ScanIssue(
                        rule_id="INPUT-01", rule_name="外部输入类型校验缺失",
                        category="INPUT", severity="BLOCKER",
                        file_path=str(filepath), line_number=line_num + 1,
                        line_content=lines[line_num].strip(),
                        description=f"函数使用了request对象属性但缺少typeof类型校验",
                        suggestion="添加: if (typeof value !== 'expected') throw new TypeError(...)",
                        method_source="等价类划分", language=lang
                    ))
    
    return issues


# --- INPUT-02: 参数范围校验 ---
def _check_numeric_range_validation(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    
    if lang == 'python':
        func_pattern = re.compile(r'^\s*def\s+(\w+)\s*\(([^)]*)\)', re.MULTILINE)
        for match in func_pattern.finditer(content):
            params = match.group(2)
            # 找到数值型参数
            numeric_params = re.findall(r'(\w+)\s*(?::\s*(int|float))?', params)
            
            func_start = content[:match.start()].count('\n')
            end_line = min(len(lines), func_start + 100)
            func_body = '\n'.join(lines[func_start:end_line])
            
            for pname, ptype in numeric_params:
                if pname in ('self', 'cls', '*args', '**kwargs'):
                    continue
                # 检查参数是否参与了运算
                param_in_op = re.search(rf'\b{pname}\s*[+\-*/%=<>]', func_body)
                if not param_in_op:
                    continue
                # 检查是否有范围校验
                has_range_check = re.search(
                    rf'(if\s+.*\b{pname}\s*[<>=]|'
                    rf'max\s*\(\s*.*\b{pname}|min\s*\(\s*.*\b{pname}|'
                    rf'clamp|range_check|validate.*\b{pname})',
                    func_body
                )
                if not has_range_check and ptype in ('int', 'float') or (not ptype and param_in_op):
                    issues.append(ScanIssue(
                        rule_id="INPUT-02", rule_name="参数范围校验缺失",
                        category="INPUT", severity="BLOCKER",
                        file_path=str(filepath), line_number=func_start + 1,
                        line_content=lines[func_start].strip(),
                        description=f"数值型参数 '{pname}' 参与运算但缺少范围合法性校验(>= / <= / clamp)",
                        suggestion="添加: if {pname} < MIN or {pname} > MAX: raise ValueError(...)",
                        method_source="边界值分析", language=lang
                    ))
                    break  # 每个函数只报一次
    
    return issues


# --- INPUT-03: 枚举/状态完备性 ---
def _check_enum_completeness(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    
    if lang in ('java', 'kotlin'):
        # switch without default
        switch_pattern = re.compile(r'switch\s*\([^)]+\)\s*\{', re.MULTILINE)
        for match in switch_pattern.finditer(content):
            block_start = match.end()
            # 找switch块的结束
            brace_count = 1
            pos = block_start
            while pos < len(content) and brace_count > 0:
                if content[pos] == '{':
                    brace_count += 1
                elif content[pos] == '}':
                    brace_count -= 1
                pos += 1
            block_content = content[block_start:pos]
            
            if not re.search(r'\bdefault\s*:', block_content):
                line_num = content[:match.start()].count('\n')
                issues.append(ScanIssue(
                    rule_id="INPUT-03", rule_name="枚举/状态处理不完备(switch缺default)",
                    category="INPUT", severity="CRITICAL",
                    file_path=str(filepath), line_number=line_num + 1,
                    line_content=lines[line_num].strip(),
                    description="switch语句缺少default分支,无法处理意外枚举值",
                    suggestion='添加 default: throw new IllegalArgumentException("Unknown: " + value)',
                    method_source="等价类划分", language=lang
                ))
    
    elif lang == 'python':
        # if/elif chain without else
        # 查找连续的 if/elif 块
        if_elif_pattern = re.compile(
            r'^(\s*)(?:if|elif)\s+\(.+\):\s*$', re.MULTILINE
        )
        matches = list(if_elif_pattern.finditer(content))
        
        # 检查连续的 if/elif 序列
        i = 0
        while i < len(matches):
            chain_start = i
            indent = matches[i].group(1)
            
            while i + 1 < len(matches):
                next_indent = matches[i + 1].group(1)
                if len(next_indent) >= len(indent):
                    # 检查是否有 else 在它们之间
                    between = content[matches[i].end():matches[i + 1].start()]
                    if re.search(rf'^{re.escape(indent)}else\s*:', between, re.MULTILINE):
                        break
                    i += 1
                else:
                    break
            
            chain_length = i - chain_start + 1
            if chain_length >= 2:
                last_match = matches[i]
                after_last = content[last_match.end():last_match.end() + 500]
                if not re.search(rf'^{re.escape(indent)}else\s*:', after_last, re.MULTILINE):
                    line_num = content[:last_match.start()].count('\n')
                    issues.append(ScanIssue(
                        rule_id="INPUT-03", rule_name="枚举/状态处理不完备(if/elif缺else)",
                        category="INPUT", severity="CRITICAL",
                        file_path=str(filepath), line_number=line_num + 1,
                        line_content=lines[line_num].strip(),
                        description=f"包含{chain_length}个分支的if/elif链条缺少else兜底处理",
                        suggestion="添加 else 分支处理意外值或 raise ValueError",
                        method_source="等价类划分", language=lang
                    ))
            i += 1
    
    elif lang == 'javascript':
        # switch without default
        switch_matches = re.findall(r'switch\s*\([^)]+\)\s*\{', content)
        for match_str in re.finditer(r'switch\s*\([^)]+\)\s*\{', content):
            start_pos = match_str.end()
            brace_count = 1
            pos = start_pos
            while pos < len(content) and brace_count > 0:
                if content[pos] == '{': brace_count += 1
                elif content[pos] == '}': brace_count -= 1
                pos += 1
            block_content = content[start_pos:pos]
            if not re.search(r'\bdefault\s*:', block_content):
                line_num = content[:match_str.start()].count('\n')
                issues.append(ScanIssue(
                    rule_id="INPUT-03", rule_name="枚举/状态处理不完备(switch缺default)",
                    category="INPUT", severity="CRITICAL",
                    file_path=str(filepath), line_number=line_num + 1,
                    line_content=lines[line_num].strip(),
                    description="switch语句缺少default分支",
                    suggestion='添加 default: throw new Error("Unexpected: " + value)',
                    method_source="等价类划分", language=lang
                ))
    
    return issues


# --- INPUT-04: 字符串长度限制 ---
def _check_string_length_limit(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    
    # DB插入/更新的模式
    db_patterns = [
        (r'\.(insert|update|execute|save|create)\s*\(', 'DB operation'),
        (r'redis\.(set|hset|lpush|rpush)\s*\(', 'Redis write'),
        (r'requests?\.(post|put|patch)\s*\(', 'HTTP request'),
        (r'fetch\s*\(', 'Fetch API'),
    ]
    
    if lang == 'python':
        var_assign = re.compile(r'(\w+)\s*=\s*(input\(|request\.[a-z]+|os\.getenv|sys\.argv|user_|raw_)', re.IGNORECASE)
        for match in var_assign.finditer(content):
            var_name = match.group(1)
            assign_line = content[:match.start()].count('\n')
            
            # 检查后续是否用于DB/网络写操作且无截断
            search_area = content[match.start():match.start()+2000]
            
            for db_pat, db_desc in db_patterns:
                if re.search(db_pat, search_area) and var_name in search_area:
                    # 检查是否有截断 [:N] or [0:N]
                    truncated = bool(re.search(rf'{var_name}\s*\[:\d+\]|{var_name}\s*\[\d+:\d+\]|slice\s*\(\s*{var_name}', search_area))
                    if not truncated:
                        issues.append(ScanIssue(
                            rule_id="INPUT-04", rule_name="字符串长度未限制",
                            category="INPUT", severity="CRITICAL",
                            file_path=str(filepath), line_number=assign_line + 1,
                            line_content=lines[assign_line].strip(),
                            description=f"变量 '{var_name}' 来自外部输入且用于{db_desc}但未做长度截断",
                            suggestion=f"使用 {var_name} = {var_name}[:MAX_LENGTH] 截断后再使用",
                            method_source="边界值分析", language=lang
                        ))
                        break
    
    return issues


# --- NULL-01: 空值解引用 ---
def _check_null_dereference(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    
    if lang == 'python':
        # 模式: 可能为None的对象调用方法/属性
        # 可能返回None的模式
        none_sources = re.compile(
            r'(\w+)\s*=\s*(?:'
            r'\w+\.get\(|'           # dict.get()
            r'\w+\.query\(|'          # DB query
            r'session\.get\(|'       # session.get()
            r'requests?\.(get|post)\(|' # HTTP request
            r'\w+\.find(?:_one)?\(|'   # ORM find
            r')',
            re.MULTILINE
        )
        
        for match in none_sources.finditer(content):
            var_name = match.group(1)
            line_num = content[:match.start()].count('\n')
            
            # 向下搜索该变量被解引用的地方
            search_after = content[match.end():match.end()+1500]
            deref_pattern = re.compile(rf'{var_name}\.\w+\s*\(')
            if deref_pattern.search(search_after):
                # 检查是否有None保护
                protect_area = content[match.start():match.end()+1500]
                if not re.search(rf'if\s+(?:not\s+)?{var_name}\s+(?:is\s+(?:not\s+)?None)|if\s+{var_name}(?:\s+and|\s+is\s+not\s+None)?', protect_area):
                    issues.append(ScanIssue(
                        rule_id="NULL-01", rule_name="可能空值的解引用风险",
                        category="NULL", severity="BLOCKER",
                        file_path=str(filepath), line_number=line_num + 1,
                        line_content=lines[line_num].strip(),
                        description=f"变量 '{var_name}' 可能返回None但后续直接调用了其方法/属性",
                        suggestion=f"添加: if {var_name} is not None: ... 或使用 getattr({var_name}, 'attr', default)",
                        method_source="错误推测法", language=lang
                    ))
    
    elif lang in ('javascript', 'typescript'):
        # 类似逻辑检测JS中的可选链缺失
        null_sources = re.compile(
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:'
            r'\w+\.find\(|'
            r'\w+\.querySelector\(|'
            r'\w+\.getItem\(|'
            r'await\s+\w+\.(?:get|post|fetch)\(|'
            r'fetch\s*\(|'
            r'document\.(getElementById|querySelector)'
            r')'
        )
        
        for match in null_sources.finditer(content):
            var_name = match.group(1)
            line_num = content[:match.start()].count('\n')
            search_after = content[match.end():match.end()+1500]
            
            if re.search(rf'{var_name}\.', search_after) and not re.search(rf'{var_name}\?\.', search_after):
                if not re.search(rf'if\s*\(\s*{var_name}\s*\)', content[match.start():match.end()+1500]):
                    issues.append(ScanIssue(
                        rule_id="NULL-01", rule_name="可能空值的解引用风险(null/undefined)",
                        category="NULL", severity="BLOCKER",
                        file_path=str(filepath), line_number=line_num + 1,
                        line_content=lines[line_num].strip(),
                        description=f"变量 '{var_name}' 可能为null/undefined但使用了点操作符而非可选链(?.)",
                        suggestion=f"将 {var_name}.xxx 改为 {var_name}?.xxx 或添加 if ({var_name}) 检查",
                        method_source="错误推测法", language=lang
                    ))
    
    return issues


# --- NULL-02: 数组越界访问 ---
def _check_array_bounds(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    
    # 通用的索引访问模式
    index_access = re.compile(r'(\w[\w]*)\[([^\]]+)\]')
    
    if lang == 'python':
        for match in index_access.finditer(content):
            arr_name = match.group(1)
            index_expr = match.group(2)
            line_num = content[:match.start()].count('\n')
            
            # 字面量索引如 [0], [1]
            if index_expr.strip().isdigit() or (index_expr.strip().startswith('-') and index_expr.strip()[1:].digit()):
                idx_val = int(index_expr.strip())
                if idx_val >= 0:
                    # 向上搜索该变量的来源
                    before_line = max(0, line_num - 30)
                    above_code = '\n'.join(lines[before_line:line_num+1])
                    
                    # 变量来自外部或函数参数
                    is_external = bool(re.search(
                        rf'{arr_name}\s*=\s*(?:'
                        r'|request\.|input\(|'
                        r'\.get\(|\.findall\(|\.query\(|'
                        rf'def\s+.*\b{arr_name}\b'
                        r')', above_code
                    ))
                    
                    if is_external:
                        # 检查是否有保护
                        protect = bool(re.search(
                            rf'(if\s+(?:not\s+)?{arr_name}|'
                            rf'{arr_name}\s+and\s|'
                            rf'len\s*\(\s*{arr_name}\s*\)\s*>\s*{index_expr}',
                            content[max(0, match.start()-300):match.start()]
                        ))
                        
                        if not protect:
                            issues.append(ScanIssue(
                                rule_id="NULL-02", rule_name="集合/数组越界访问",
                                category="NULL", severity="BLOCKER",
                                file_path=str(filepath), line_number=line_num + 1,
                                line_content=lines[line_num].strip(),
                                description=f"对 '{arr_name}[{index_expr}]' 进行索引访问但未检查集合非空和索引有效性",
                                suggestion=f"添加: if not {arr_name}: return None; if {index_expr} >= len({arr_name}): ...",
                                method_source="边界值分析", language=lang
                            ))
    
    return issues


# --- NULL-03: 链式调用NPE ---
def _check_chain_call_npe(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    
    # 检测3级及以上的链式调用
    chain_pattern = re.compile(r'(\w[\w.]*)\.\w+\([^)]*\)\.\w+\(')
    
    for match in chain_pattern.finditer(content):
        chain = match.group(1)
        dots = chain.count('.')
        if dots >= 2:
            line_num = content[:match.start()].count('\n')
            # 检查是否已使用可选链或Optional
            full_expr = content[match.start():match.start()+len(match.group(0))+50]
            has_optional = '?' in full_expr or 'Optional' in full_expr or 'orElse' in full_expr
            
            if not has_optional:
                issues.append(ScanIssue(
                    rule_id="NULL-03", rule_name="链式调用空指针风险",
                    category="NULL", severity="CRITICAL",
                    file_path=str(filepath), line_number=line_num + 1,
                    line_content=lines[line_num].strip(),
                    description=f"发现{dots+1}级方法链调用,中间任一环节返回null都会导致异常",
                    suggestion="拆分为多步并每步检查,或使用Optional链式调用/可选链(?.)",
                    method_source="错误推测法", language=lang
                ))
                break  # 每个文件最多报一个代表性问题
    
    return issues


# --- BOUND-04: 除零保护 ---
def _check_division_by_zero(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    
    div_pattern = re.compile(r'(?<![=\w])(\w[\w.]*)\s*/\s*(\w[\w.]*)\s*')
    
    for match in div_pattern.finditer(content):
        divisor = match.group(2).rstrip('.')
        line_num = content[:match.start()].count('\n')
        
        # 排除常量字面量除数
        if divisor.isdigit() or re.match(r'^-?\d+\.?\d*$', divisor):
            continue
        
        # 除数是变量或表达式 — 需要检查是否有零值保护
        before_context = content[max(0, match.start()-400):match.start()]
        has_protection = bool(re.search(
            rf'(if\s+.*\b{re.escape(divisor)}\b.*(?:!=\s*0|>\s*0|==\s*0)|'
            rf'{re.escape(divisor)}\s*!=\s*0|'
            rf'safe_divide|zero_check|div_zero)',
            before_context
        ))
        
        if not has_protection:
            issues.append(ScanIssue(
                rule_id="BOUND-04", rule_name="除法运算除零保护缺失",
                category="BOUNDARY", severity="BLOCKER",
                file_path=str(filepath), line_number=line_num + 1,
                line_content=lines[line_num].strip(),
                description=f"除数变量 '{divisor}' 可能是零且无前置零值检查,存在ZeroDivisionError风险",
                suggestion=f"添加: if {divisor} == 0: return safe_default; result = a / {divisor}",
                method_source="错误推测法", language=lang
            ))
            break  # 每个文件最多报一次
    
    return issues


# --- EXCP-01: 空catch块 ---
def _check_empty_catch(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []

    if lang == 'python':
        # except: 后跟 pass 或只有注释
        for match in re.finditer(r'except\s+(?:[\w,\s]+)?\s*:', content):
            line_num = content[:match.start()].count('\n')
            # 获取except块体
            after_except = content[match.end():]
            # 简化: 检查接下来几行是否只有pass/注释/空行
            body_lines = []
            for l in after_except.split('\n')[:5]:
                s = l.strip()
                if not s or s.startswith('#') or s == 'pass':
                    body_lines.append(s)
                else:
                    break
            effective = [l for l in body_lines if l and l != 'pass' and not l.startswith('#')]
            if not effective:
                issues.append(ScanIssue(
                    rule_id="EXCP-01", rule_name="空catch块（异常被静默吞掉）",
                    category="EXCEPTION", severity="CRITICAL",
                    file_path=str(filepath), line_number=line_num + 1,
                    line_content=lines[line_num].strip(),
                    description="发现空except块或仅有pass，异常被完全忽略",
                    suggestion="至少记录日志 logger.error(e, exc_info=True) 或重新抛出或返回错误码",
                    method_source="错误推测法", language=lang
                ))

    elif lang in ('java', 'javascript', 'typescript'):
        for match in re.finditer(r'catch\s*\([^)]*\)\s*\{\s*\}', content):
            line_num = content[:match.start()].count('\n')
            issues.append(ScanIssue(
                rule_id="EXCP-01", rule_name="空catch块（异常被静默吞掉）",
                category="EXCEPTION", severity="CRITICAL",
                file_path=str(filepath), line_number=line_num + 1,
                line_content=lines[line_num].strip(),
                description="发现空的catch块{}，异常被静默吞掉",
                suggestion="添加 e.printStackTrace() / logger.error(e) 至少记录异常信息",
                method_source="错误推测法", language=lang
            ))

    return issues


# --- EXCP-02: 宽泛异常捕获 ---
def _check_broad_exception(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    if lang == 'python':
        for match in re.finditer(r'except\s+(Exception|BaseException)\s*:', content):
            line_num = content[:match.start()].count('\n')
            before = content[max(0, match.start()-200):match.start()]
            has_specific = bool(re.search(r'except\s+\w+Error\s*:', before))
            if not has_specific:
                issues.append(ScanIssue(
                    rule_id="EXCP-02", rule_name="宽泛异常捕获(Exception)",
                    category="EXCEPTION", severity="MAJOR",
                    file_path=str(filepath), line_number=line_num + 1,
                    line_content=lines[line_num].strip(),
                    description=f"使用宽泛的{match.group(1)}捕获可能掩盖真正错误",
                    suggestion="替换为具体异常类型(FileNotFoundError, ValueError等)",
                    method_source="错误推测法", language=lang
                ))
    elif lang == 'java':
        for match in re.finditer(r'catch\s*\(\s*(?:Exception|Throwable)\s+', content):
            line_num = content[:match.start()].count('\n')
            issues.append(ScanIssue(
                rule_id="EXCP-02", rule_name="宽泛异常捕获(Exception/Throwable)",
                category="EXCEPTION", severity="MAJOR",
                file_path=str(filepath), line_number=line_num + 1,
                line_content=lines[line_num].strip(),
                description="使用宽泛异常捕获，可能掩盖真正的程序错误",
                suggestion="替换为具体异常(IOException, SQLException等)",
                method_source="错误推测法", language=lang
            ))
    return issues


# --- EXCP-03: 资源未释放 ---
def _check_resource_not_released(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    if lang == 'python':
        for match in re.finditer(r'(\w+)\s*=\s*open\s*\(', content):
            var, line_num = match.group(1), content[:match.start()].count('\n')
            before = content[max(0, match.start()-100):match.end()+20]
            if 'with open' not in before:
                after = content[match.end():match.end()+2000]
                has_close_or_try = f'{var}.close()' in after or 'try:' in after
                if not has_close_or_try:
                    issues.append(ScanIssue(
                        rule_id="EXCP-03", rule_name="资源未安全释放(open无with)",
                        category="EXCEPTION", severity="CRITICAL",
                        file_path=str(filepath), line_number=line_num + 1,
                        line_content=lines[line_num].strip(),
                        description=f"open()赋值给'{var}'但未使用with statement",
                        suggestion="改为 with open(...) as {var}: ...",
                        method_source="错误推测法", language=lang
                    ))
    elif lang == 'java':
        unsafe_pats = [
            (r'new\s+(FileInputStream|FileOutputStream|BufferedReader|BufferedWriter|Scanner)', 'IO'),
            (r'(DataSource|DriverManager|ConnectionPool)\.getConnection\(\)', 'DB'),
        ]
        for pat, desc in unsafe_pats:
            for m in re.finditer(pat, content):
                ln = content[:m.start()].count('\n')
                before = content[max(0,m.start()-300):m.start()]
                if 'try (' not in before and 'try(' not in before:
                    issues.append(ScanIssue(
                        rule_id="EXCP-03", rule_name=f"资源未安全释放({desc})",
                        category="EXCEPTION", severity="CRITICAL",
                        file_path=str(filepath), line_number=ln + 1,
                        line_content=lines[ln].strip(),
                        description=f"{desc}资源创建但未使用try-with-resources(TWR)",
                        suggestion="改为 try (Resource res = new ...) {{ ... }} 自动关闭",
                        method_source="错误推测法", language=lang
                    ))
    return issues


# --- LOGIC-02: switch缺default (复用INPUT-03) ---
def _check_switch_no_default(fp, c, ls, ln):
    return _check_enum_completeness(fp, c, ls, ln)


# --- LOGIC-05: 条件永真/永假 ---
def _check_always_true_false(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    patterns = [
        (r'\bif\s*\(\s*(\w+)\s*=\s*(?:true|false|\d+|"[^"]*")\s*\)', "赋值=误作比较=="),
        (r'\bif\s*\(\s*(\w+)\s*[<>=]+\s*\1\s*\)', "自身比较永远为假(>)或真(<)"),
        (r'\bif\s*\(\s*(\w+)\s*&&\s*!\s*\1\s*\)', "x && !x 永远为false"),
        (r'\bif\s*\(\s*(\w+)\s*\|\|\s*!\s*\1\s*\)', "x || !x 永远为true"),
    ]
    for pat, desc in patterns:
        for m in re.finditer(pat, content):
            ln = content[:m.start()].count('\n')
            issues.append(ScanIssue(
                rule_id="LOGIC-05", rule_name="条件判断永真/永假(死代码)",
                category="LOGIC", severity="CRITICAL",
                file_path=str(filepath), line_number=ln + 1,
                line_content=lines[ln].strip(),
                description=f"检测到可能的恒定条件: {desc}",
                suggestion="检查是否==误写为=(赋值); 移除死代码; 修正逻辑",
                method_source="错误推测法", language=lang
            ))
    return issues


# --- RESC-01 (复用EXCP-03) ---
def _check_unsafe_resource(fp, c, ls, ln):
    return _check_resource_not_released(fp, c, ls, ln)


# --- SECU-01: SQL注入 ---
def _check_sql_injection(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    patterns = [
        (r'(f["\'].*(?:SELECT|INSERT|UPDATE|DELETE).*\{[^}]*\})', "Python f-string SQL拼接"),
        (r'"(?:SELECT|INSERT|UPDATE|DELETE)[^"]*"\s*\+\s*\w+', "Java字符串拼接SQL"),
        (r'\.(execute|executeQuery|raw|rawsql)\s*\(\s*f["\']', "ORM raw查询f-string"),
        (r'"(?:SELECT|INSERT|UPDATE|DELETE)[^"]*".format\s*\(', "Python .format() SQL拼接"),
    ]
    for pat, desc in patterns:
        for m in re.finditer(pat, content, re.IGNORECASE):
            ln = content[:m.start()].count('\n')
            issues.append(ScanIssue(
                rule_id="SECU-01", rule_name=f"SQL注入风险({desc})",
                category="SECURITY", severity="BLOCKER",
                file_path=str(filepath), line_number=ln + 1,
                line_content=lines[ln].strip(),
                description="字符串拼接构建SQL，存在SQL注入风险",
                suggestion="改为参数化查询: ? / :param / #{param} 占位符传参",
                method_source="AI缺陷模式(#1)", language=lang
            ))
            break
    return issues


# --- SECU-02: XSS风险 ---
def _check_xss_risk(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    xss_patterns = [
        (r'innerHTML\s*=', "innerHTML直接赋值"),
        (r'dangerouslySetInnerHTML\s*=', "React dangerouslySetInnerHTML"),
        (r'\$\([^)]+\)\.html\s*\(', "jQuery .html()方法"),
        (r'response\.write\s*\(', "response.write输出"),
        (r'v-html\s*=', "Vue v-html指令"),
    ]
    for pat, desc in xss_patterns:
        for m in re.finditer(pat, content):
            ln = content[:m.start()].count('\n')
            area = content[m.end():m.end()+200]
            escapes = ['escape(', 'escapeHtml(', 'sanitize(', 'DOMPurify', '.text(',
                       'textContent', 'htmlspecialchars', 'encodeURI']
            if not any(e in area for e in escapes):
                issues.append(ScanIssue(
                    rule_id="SECU-02", rule_name=f"XSS风险({desc})",
                    category="SECURITY", severity="BLOCKER",
                    file_path=str(filepath), line_number=ln + 1,
                    line_content=lines[ln].strip(),
                    description=f"用户输入不经HTML编码直接渲染({desc}),存在XSS风险",
                    suggestion="用textContent替代innerHTML;开启auto-escape;使用DOMPurify净化",
                    method_source="AI缺陷模式(#3)", language=lang
                ))
                break
    return issues


# --- SECU-03: 硬编码密钥 ---
def _check_hardcoded_secrets(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    patterns = [
        (r'(?:api_key|apikey|API_KEY|secret|SECRET|password|PASSWORD|token|TOKEN)\s*=\s*["\'][a-zA-Z0-9_-]{16,}["\']', "硬编码密钥/Token"),
        (r'(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{30,}|AKIA[A-Z0-9]{16}|xox[bps]-[a-zA-Z0-9-]{20,})', "已知格式凭证硬编码"),
    ]
    samples = ['your-api-key','your-secret','your-token','xxx','REPLACE_ME','changeme','<your']
    for pat, desc in patterns:
        for m in re.finditer(pat, content):
            val = m.group()
            if any(s.lower() in val.lower() for s in samples):
                continue
            ln = content[:m.start()].count('\n')
            masked = val[:20] + '*' * 8 if len(val) > 28 else '*' * min(len(val), 8)
            issues.append(ScanIssue(
                rule_id="SECU-03", rule_name=desc,
                category="SECURITY", severity="CRITICAL",
                file_path=str(filepath), line_number=ln + 1,
                line_content=lines[ln].strip(),
                description=f"疑似硬编码敏感信息({desc}): {masked}",
                suggestion="改用环境变量 os.getenv('SECRET_KEY') 或密钥管理服务",
                method_source="AI缺陷模式(#4)", language=lang
            ))
            break
    return issues


# --- SECU-07: 敏感日志 ---
def _check_sensitive_logging(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    keywords = ['password','passwd','pwd','secret','token','credit_card','ssn','id_card']
    log_funcs = [r'logger\.\w+\(', r'logging\.\w+\(', r'console\.\w+\(', r'print\s*\(']
    log_re = '|'.join(log_funcs)
    for kw in keywords:
        for i, line in enumerate(lines):
            low = line.lower().strip()
            if kw in low and any(re.search(lf, line, re.I) for lf in log_funcs):
                issues.append(ScanIssue(
                    rule_id="SECU-07", rule_name="敏感信息日志输出",
                    category="SECURITY", severity="CRITICAL",
                    file_path=str(filepath), line_number=i+1,
                    line_content=line.strip(),
                    description=f"日志中出现敏感关键词 '{kw}'，有泄露风险",
                    suggestion="密码/Token绝不入日志; 使用 mask_sensitive(value) 脱敏",
                    method_source="AI缺陷模式(#4)", language=lang
                ))
                return issues
    return issues


# --- AICD-02: happy path only ---
def _check_happy_path_only(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    if lang == 'python':
        for m in re.finditer(r'^\s*def\s+(\w+)\s*\([^)]*\)\s*:', content, re.M):
            start = content[:m.start()].count('\n')
            body = '\n'.join(lines[start:min(start+80,len(lines))])
            ios = [r'requests?\.',r'open\s*\(',r'\.query\(',r'session\.',r'redis\.',r'fetch',r'json\.loads',r'pd\.read_']
            has_io = any(re.search(p,body) for p in ios)
            no_try = not re.search(r'try\s*:|except\s+|raise\s+', body)
            if has_io and no_try:
                issues.append(ScanIssue(
                    rule_id="AICD-02", rule_name="只处理happy path无异常路径",
                    category="AI-CODE", severity="CRITICAL",
                    file_path=str(filepath), line_number=start+1,
                    line_content=lines[start].strip(),
                    description=f"函数'{m.group(1)}'含I/O操作但缺try-except(AI典型问题)",
                    suggestion="为每个I/O操作添加 try-except 和 fallback/default value",
                    method_source="AI缺陷模式(#1 出现率35%)", language=lang
                ))
    elif lang in ('javascript','typescript'):
        for m in re.finditer(r'(?:function\s+\w+|(?:const|let|var|async)\s+\w+\s*[=(]|=>)', content):
            ln = content[:m.start()].count('\n')
            body = '\n'.join(lines[ln:min(ln+60,len(lines))])
            ios = [r'fetch\s*\(',r'\.(get|post|put|delete)\s*\(',r'fs\.',r'axios\.']
            has_io = any(re.search(p,body) for p in ios)
            no_try = 'try{' not in body.replace(' ','') and 'try {' not in body
            if has_io and no_try:
                issues.append(ScanIssue(
                    rule_id="AICD-02", rule_name="只处理happy path无异常路径",
                    category="AI-CODE", severity="CRITICAL",
                    file_path=str(filepath), line_number=ln+1,
                    line_content=lines[ln].strip(),
                    description="含I/O操作的函数缺少try-catch(AI典型问题)",
                    suggestion="添加 try { ... } catch (e) { ... } 处理",
                    method_source="AI缺陷模式(#1 出现率35%)", language=lang
                ))
    return issues


# --- AICD-06: 魔法数字 ---
def _check_magic_numbers(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    count = 0
    for m in re.finditer(r'(?<![\w."\'`])(?!0|1|-1)(\d{2,})(?![\w."\`\]])', content):
        num = m.group(1)
        ln = content[:m.start()].count('\n')
        line = lines[ln]
        if line.strip().startswith(('#','//','*','/*')):
            continue
        if re.match(r'^\s*[A-Z_]+\s*=' + num, line):
            continue
        val = int(num)
        reasonable = {1000,1024,2048,4096,8192,60,3600,24,7,30,31,365,100,500,256,512}
        if val <= 12 or val in reasonable:
            continue
        if re.search(r'(?::|port|version)\s*=\s*' + num, line, re.I):
            continue
        if count < 3:
            issues.append(ScanIssue(
                rule_id="AICD-06", rule_name="魔法数字(Magic Number)",
                category="AI-CODE", severity="MAJOR",
                file_path=str(filepath), line_number=ln+1,
                line_content=line.strip(),
                description=f"含义不明的魔法数字 '{num}'",
                suggestion=f"提取常量: {'MAX_' + num if val < 100 else f'MAGIC_{num}'} = {num}",
                method_source="AI缺陷模式", language=lang
            ))
            count += 1
    return issues


# --- PERF-01: N+1查询 ---
def _check_n_plus_one_query(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    loop_map = {
        'python': r'for\s+\w+\s+in\s+\w[\w.]*\s*:',
        'java': r'for\s*\([^)]+\w[\w.]*\s*:\s*\w[\w.]*\)',
        'javascript': r'for(?:Each)?\s*\([^)]*\w[\w.]*(?:of|in)\s+\w[\w.]*\)',
        'go': r'range\s+.*:=\s*range\(',
    }
    db_pats = [r'\.(query|get|find|first|all|filter|select|execute)\s*\(',
               r'Session\.query\(','\.objects\.(get|filter|all)\s*\(',
               r'connection\.execute\(','cursor\.execute\(',
               r'\.(findOne|findMany|findUnique)\s*\(']
    
    lp = loop_map.get(lang)
    if not lp:
        return issues
    
    for lm in re.finditer(lp, content, re.M):
        sln = content[:lm.start()].count('\n')
        end_ln = min(len(lines), sln + 50)
        body = '\n'.join(lines[sln:end_ln])
        for dp in db_pats:
            if re.search(dp, body):
                issues.append(ScanIssue(
                    rule_id="PERF-01", rule_name="N+1查询问题(循环内DB操作)",
                    category="PERF", severity="CRITICAL",
                    file_path=str(filepath), line_number=sln+1,
                    line_content=lines[sln].strip(),
                    description="循环体内执行DB查询,N条数据触发N+1次访问",
                    suggestion="改为批量查询: WHERE IN(...) / batch_get / joinedload / prefetch_related",
                    method_source="缺陷模式库", language=lang
                ))
                return issues
    return issues


# --- PERF-04: 字符串循环拼接 ---
def _check_string_loop_concat(filepath: Path, content: str, lines: List[str], lang: str) -> List[ScanIssue]:
    issues = []
    loop_map = {
        'python': r'for\s+',
        'java': r'for\s*\(',
        'javascript': r'for\s*\(|forEach',
    }
    lp = loop_map.get(lang)
    if not lp:
        return issues

    concat_pat = {
        'python': r'\w+\s*\+=\s*',
        'java': r'\w+\s*\+=\s*"',
        'javascript': r'\w+\s*\+=\s*',
    }
    cp = concat_pat.get(lang, r'\w+\s*\+=')

    for lm in re.finditer(lp, content):
        sln = content[:lm.start()].count('\n')
        end_ln = min(len(lines), sln + 40)
        body = '\n'.join(lines[sln:end_ln])

        if re.search(cp, body):
            # 排除已优化的情况
            optimized = ['join(', 'StringBuilder', 'append(', 'StringIO(', 'Array.join(']
            if not any(o in body for o in optimized):
                issues.append(ScanIssue(
                    rule_id="PERF-04", rule_name="字符串循环拼接(O(n²))",
                    category="PERF", severity="MAJOR",
                    file_path=str(filepath), line_number=sln+1,
                    line_content=lines[sln].strip(),
                    description="循环中使用+=拼接字符串,时间复杂度O(n²)",
                    suggestion={
                        'python': "用 ''.join(list) 或 io.StringIO",
                        'java': "用 StringBuilder sb = new StringBuilder(); sb.append()",
                        'javascript': "用 Array.push() + Array.join()",
                    }.get(lang, "改用高效的字符串构建方式"),
                    method_source="边界值分析", language=lang
                ))
                return issues
    return issues


# ============================================================
# 扫描引擎核心
# ============================================================

class CodeScanner:
    """代码质量扫描引擎"""

    def __init__(self, lang: Optional[str] = None, req_rules_path: Optional[str] = None):
        self.lang = lang
        self.rules = build_rules()
        self.req_rules = self._load_req_rules(req_rules_path) if req_rules_path else None

    def _load_req_rules(self, path: str) -> Optional[dict]:
        """加载需求规则文件(requirement_rules.json)"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load requirement rules: {e}", file=sys.stderr)
            return None

    def scan_file(self, filepath: Path) -> Optional[FileScanResult]:
        """扫描单个文件"""
        lang = detect_language(filepath)
        if not lang:
            return None

        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)
            return None

        lines = content.split('\n')
        result = FileScanResult(
            file_path=str(filepath),
            language=lang,
            total_lines=len(lines)
        )

        for rule in self.rules:
            if not rule.applies_to(lang):
                continue
            if rule.check_func is None:
                continue
            try:
                issues = rule.check_func(filepath, content, lines, lang)
                result.issues.extend(issues)
            except Exception as e:
                print(f"Warning: Rule {rule.rule_id} failed on {filepath}: {e}", file=sys.stderr)

        return result

    def scan_directory(self, target_dir: Path) -> ScanReport:
        """扫描整个目录"""
        report = ScanReport(
            target_dir=str(target_dir),
            language=self.lang or "auto"
        )

        all_files = list(target_dir.rglob("*"))
        report.total_files = len([f for f in all_files if f.is_file()])

        for filepath in all_files:
            if not filepath.is_file():
                continue
            if not should_scan(filepath, self.lang):
                report.skipped_files += 1
                continue

            result = self.scan_file(filepath)
            if result:
                report.scanned_files += 1
                report.total_issues += len(result.issues)
                report.file_results.append(result)
            else:
                report.skipped_files += 1

        report.file_results.sort(key=lambda r: len(r.issues), reverse=True)
        return report


# ============================================================
# 输出格式化
# ============================================================

def output_json(report: ScanReport, output_path: Optional[str] = None):
    """输出JSON格式报告"""
    data = report.to_dict()
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    if output_path:
        Path(output_path).write_text(json_str, encoding='utf-8')
        print(f"Report written to: {output_path}")
    else:
        print(json_str)


def output_text(report: ScanReport):
    """输出文本格式报告"""
    BOLD, RED, YELLOW, BLUE, GRAY, GREEN, RESET = (
        "\033[1m", "\033[91m", "\033[93m", "\033[94m", "\033[90m", "\033[92m", "\033[0m")
    SEV_COLOR = {"BLOCKER": RED, "CRITICAL": YELLOW, "MAJOR": BLUE, "MINOR": GRAY}

    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}  Code Quality Gate Scanner Report{RESET}")
    print(f"{'='*70}")
    print(f"  Target:    {report.target_dir}")
    print(f"  Language:  {report.language}")
    print(f"  Scanned:   {report.scanned_files} files ({report.skipped_files} skipped)")
    print(f"  Issues:    {report.total_issues}")
    print()
    print(f"  {RED}BLOCKER:  {report.total_blockers:>4}{RESET}")
    print(f"  {YELLOW}CRITICAL: {report.total_criticals:>4}{RESET}")
    print(f"  {BLUE}MAJOR:    {report.total_majors:>4}{RESET}")
    print(f"  {GRAY}MINOR:    {report.total_minors:>4}{RESET}")
    print()

    if report.pass_gate:
        print(f"  {GREEN}{BOLD}Gate: PASSED (no blockers){RESET}")
    else:
        print(f"  {RED}{BOLD}Gate: FAILED ({report.total_blockers} blocker(s)){RESET}")
    print(f"{'='*70}\n")

    for fr in report.file_results:
        if not fr.issues:
            continue
        print(f"\n{BOLD}  {fr.file_path}{RESET} ({len(fr.issues)} issues)")
        print(f"  {'-'*60}")
        for issue in sorted(fr.issues, key=lambda i: (
                {"BLOCKER": 0, "CRITICAL": 1, "MAJOR": 2, "MINOR": 3}.get(i.severity, 9),
                i.line_number)):
            color = SEV_COLOR.get(issue.severity, "")
            print(f"    {color}[{issue.severity:>8}]{RESET} L{issue.line_number:<5} "
                  f"{issue.rule_id}: {issue.description}")
            if issue.suggestion:
                print(f"              Fix: {issue.suggestion}")
        print()


def output_html(report: ScanReport, output_path: str):
    """输出HTML格式报告"""
    sev_colors = {"BLOCKER": "#dc3545", "CRITICAL": "#fd7e14",
                  "MAJOR": "#0d6efd", "MINOR": "#6c757d"}
    parts = [
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
        '<title>Code Quality Gate Report</title>',
        '<style>body{font-family:sans-serif;max-width:1200px;margin:0 auto;padding:20px;background:#f8f9fa}',
        '.summary{display:flex;gap:20px;margin:20px 0}',
        '.card{background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.1);flex:1}',
        '.count{font-size:2em;font-weight:700}',
        '.file{background:#fff;border-radius:8px;padding:15px;margin:10px 0;box-shadow:0 1px 3px rgba(0,0,0,.1)}',
        '.issue{padding:8px;margin:4px 0;border-left:3px solid;border-radius:4px;background:#f8f9fa}',
        '.tag{display:inline-block;padding:2px 8px;border-radius:4px;color:#fff;font-size:.8em;font-weight:700;margin-right:8px}',
        '.pass{background:#198754;color:#fff;padding:10px;border-radius:8px;font-size:1.2em;text-align:center}',
        '.fail{background:#dc3545;color:#fff;padding:10px;border-radius:8px;font-size:1.2em;text-align:center}',
        '</style></head><body>',
        '<h1>Code Quality Gate Report</h1>',
    ]

    if report.pass_gate:
        parts.append('<div class="pass">PASSED</div>')
    else:
        parts.append(f'<div class="fail">FAILED - {report.total_blockers} Blocker(s)</div>')

    parts.append(f'<div class="summary">'
                 f'<div class="card"><h3>Target</h3>{report.target_dir}<br>{report.language}</div>'
                 f'<div class="card"><h3>Files</h3><span class="count">{report.scanned_files}</span> scanned</div>'
                 f'<div class="card"><h3>Issues</h3>'
                 f'<span class="count" style="color:#dc3545">{report.total_blockers}</span> BLOCKER '
                 f'<span class="count" style="color:#fd7e14">{report.total_criticals}</span> CRITICAL '
                 f'<span class="count" style="color:#0d6efd">{report.total_majors}</span> MAJOR '
                 f'<span class="count" style="color:#6c757d">{report.total_minors}</span> MINOR</div></div>')

    for fr in report.file_results:
        if not fr.issues:
            continue
        parts.append(f'<div class="file"><h4>{fr.file_path} ({len(fr.issues)} issues)</h4>')
        for issue in sorted(fr.issues, key=lambda i: {"BLOCKER": 0, "CRITICAL": 1, "MAJOR": 2, "MINOR": 3}.get(i.severity, 9)):
            c = sev_colors.get(issue.severity, "#6c757d")
            parts.append(f'<div class="issue" style="border-color:{c}">'
                         f'<span class="tag" style="background:{c}">{issue.severity}</span>'
                         f'<strong>{issue.rule_id}</strong> (L{issue.line_number}) '
                         f'{issue.description}<br>'
                         f'<small style="color:#666">{issue.method_source} | {issue.suggestion}</small></div>')
        parts.append('</div>')

    parts.append("</body></html>")
    Path(output_path).write_text('\n'.join(parts), encoding='utf-8')
    print(f"HTML report: {output_path}")


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Code Quality Gate Scanner",
        epilog="Examples:\n  %(prog)s ./src --lang python\n  %(prog)s ./src --output json > report.json",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", help="Target directory to scan")
    parser.add_argument("--lang", choices=list(LANG_EXTENSIONS.keys()), help="Language filter (auto-detect if omitted)")
    parser.add_argument("--output", choices=["text", "json", "html"], default="text", help="Output format")
    parser.add_argument("--html-path", default="quality-report.html", help="HTML output path")
    parser.add_argument("--json-path", default=None, help="JSON output path (stdout if omitted)")
    parser.add_argument("--requirements", default=None, help="requirement_rules.json for req-code alignment")
    args = parser.parse_args()

    target = Path(args.target)
    if not target.exists() or not target.is_dir():
        print(f"Error: Invalid target directory: {args.target}", file=sys.stderr)
        sys.exit(2)

    scanner = CodeScanner(lang=args.lang, req_rules_path=args.requirements)
    report = scanner.scan_directory(target)

    if args.output == "json":
        output_json(report, args.json_path)
    elif args.output == "html":
        output_html(report, args.html_path)
    else:
        output_text(report)

    sys.exit(0 if report.pass_gate else 1)


if __name__ == "__main__":
    main()