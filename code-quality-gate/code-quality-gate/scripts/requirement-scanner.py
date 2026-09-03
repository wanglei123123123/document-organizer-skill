#!/usr/bin/env python3
"""
Requirement Document Quality Scanner - 需求文档质量检测器

基于测试方法论(边界值、等价类、因果图、错误推测)对文本需求文档进行质量检测。
支持 .md / .txt 格式, 可扩展 .docx。

Usage:
    python requirement-scanner.py <target_file_or_dir> [--mode text|figma] [--output json|html|console]
Examples:
    python requirement-scanner.py ./docs/PRD.md
    python requirement-scanner.py ./requirements/ --batch
"""

import os, re, sys, json, argparse, hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Tuple


# ============================================================
# 数据模型
# ============================================================

class Severity(Enum):
    BLOCKER = "BLOCKER"
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"

SEVERITY_SCORE = {Severity.BLOCKER: 10, Severity.CRITICAL: 5, Severity.MAJOR: 2, Severity.MINOR: 0.5}


@dataclass
class ReqIssue:
    rule_id: str; rule_name: str; category: str; severity: str
    file_path: str; line_number: int; line_content: str
    description: str; suggestion: str; method_source: str; evidence: str
    def to_dict(self): return asdict(self)


@dataclass
class ReqScanResult:
    file_path: str; file_type: str; total_lines: int; total_chars: int
    issues: List[ReqIssue] = field(default_factory=list)
    @property
    def blocker_count(self): return sum(1 for i in self.issues if i.severity == "BLOCKER")
    @property
    def critical_count(self): return sum(1 for i in self.issues if i.severity == "CRITICAL")
    @property
    def major_count(self): return sum(1 for i in self.issues if i.severity == "MAJOR")
    @property
    def minor_count(self): return sum(1 for i in self.issues if i.severity == "MINOR")
    @property
    def score(self): return round(sum(SEVERITY_SCORE.get(Severity(i.s), 0) for i in self.issues), 1)
    @property
    def pass_gate(self): return self.blocker_count == 0
    def count_by_category(self, cat): return sum(1 for i in self.issues if i.category == cat)


@dataclass
class ReqScanReport:
    target: str; mode: str; total_files: int = 0; total_issues: int = 0
    results: List[ReqScanResult] = field(default_factory=list)
    @property
    def total_blockers(self): return sum(r.blocker_count for r in self.results)
    @property
    def total_criticals(self): return sum(r.critical_count for r in self.results)
    @property
    def total_majors(self): return sum(r.major_count for r in self.results)
    @property
    def total_minors(self): return sum(r.minor_count for r in self.results)
    @property
    def overall_score(self): return round(sum(r.score for r in self.results), 1)
    @property
    def pass_gate(self): return all(r.pass_gate for r in self.results)

    def to_dict(self):
        grade = "A" if self.overall_score >= 85 else ("B" if self.overall_score >= 70 else ("C" if self.overall_score >= 55 else "D"))
        return {
            "scan_type": f"requirement-{self.mode}", "target": self.target,
            "summary": {"total_files": self.total_files, "total_issues": self.total_issues,
                       "blockers": self.total_blockers, "criticals": self.total_criticals,
                       "majors": self.total_majors, "minors": self.total_minors,
                       "overall_score": self.overall_score, "pass_gate": self.pass_gate,
                       "grade": grade},
            "files": [{"file_path": r.file_path, "file_type": r.file_type,
                      "total_lines": r.total_lines, "score": r.score, "pass_gate": r.pass_gate,
                      "issue_counts": {"BLOCKER": r.blocker_count, "CRITICAL": r.critical_count,
                                      "MAJOR": r.major_count, "MINOR": r.minor_count},
                      "category_breakdown": {"COMPLETENESS": r.count_by_category("COMP"),
                                           "CLARITY": r.count_by_category("CLAR"),
                                           "TESTABILITY": r.count_by_category("TEST"),
                                           "SECURITY": r.count_by_category("SEC")},
                      "issues": [i.to_dict() for i in r.issues]} for r in self.results]
        }


# ============================================================
# 规则引擎
# ============================================================

def build_rules():
    return [
        # COMP 完整性
        {'id':'REQ-COMP-01','name':'核心业务流程缺失','category':'COMP',
         'severity':Severity.BLOCKER,'source':'因果图法',
         'check':_check_flow_missing,
         'desc':'主流程/Happy Path描述缺失或不完整',
         'suggest':'补充完整主流程描述,使用编号步骤或Given-When-Then'},
        {'id':'REQ-COMP-02','name':'边界值场景未定义','category':'COMP',
         'severity':Severity.CRITICAL,'source':'边界值分析法',
         'check':_check_boundary_missing,
         'desc':'数值/长度/容量等参数缺少[min,max]约束定义',
         'suggest':'为每个数值参数建立约束表'},
        {'id':'REQ-COMP-03','name':'异常流程未描述','category':'COMP',
         'severity':Severity.CRITICAL,'source':'错误推测法',
         'check':_check_exception_missing,
         'desc':'只有正常流程,缺少异常/错误处理描述',
         'suggest':'补充3类异常:输入+系统+业务'},
        {'id':'REQ-COMP-05','name':'NFR缺失或模糊','category':'COMP',
         'severity':Severity.MAJOR,'source':'错误推测法',
         'check':_check_nfr_missing,
         'desc':'非功能需求缺失或过于简略("要求快速"等)',
         'suggest':'建立NFR章节,所有指标量化'},
        {'id':'REQ-COMP-06','name':'数据字段定义不完备','category':'COMP',
         'severity':Severity.CRITICAL,'source':'等价类划分法',
         'check':_check_data_fields,
         'desc':'数据实体缺少字段类型/约束/必填定义',
         'suggest':'创建完整数据字典'},
        # CLAR 清晰度
        {'id':'REQ-CLAR-01','name':'AC模糊或缺失','category':'CLAR',
         'severity':Severity.BLOCKER,'source':'边界值分析法',
         'check':_check_ac_vague,
         'desc':'验收标准主观/不可验证或缺失',
         'suggest':'用Gherkin Given-When-Then,避免主观词'},
        {'id':'REQ-CLAR-02','name':'存在歧义/多义词','category':'CLAR',
         'severity':Severity.CRITICAL,'source':'等价类划分法',
         'check':_check_ambiguous,
         'desc':'使用了可能多解的词汇(可以/应该/适当/尽量/快速)',
         'suggest':'建立术语表,用具体值替换模糊词'},
        {'id':'REQ-CLAR-03','name':'需求矛盾风险','category':'CLAR',
         'severity':Severity.BLOCKER,'source':'因果图法',
         'check':_check_contradiction,
         'desc':'不同段落间可能有矛盾的约束/流程描述',
         'suggest':'集中定义可变值,添加交叉引用'},
        {'id':'REQ-CLAR-04','name':'依赖关系未声明','category':'CLAR',
         'severity':Severity.CRITICAL,'source':'因果图法',
         'check':_check_dependency,
         'desc':'内部功能依赖或外部系统依赖未声明',
         'suggest':'建立依赖矩阵:需求→依赖对象→类型→状态'},
        # TEST 可测试性
        {'id':'REQ-TEST-01','name':'无法验证的需求','category':'TEST',
         'severity':Severity.CRITICAL,'source':'错误推测法',
         'check':_check_unverifiable,
         'desc':'使用了主观形容词,无法设计PASS/FAIL用例',
         'suggest':'转换为可度量指标'},
        {'id':'REQ-TEST-02','name':'缺少量化指标','category':'TEST',
         'severity':Severity.MAJOR,'source':'边界值分析法',
         'check':_check_no_quantify,
         'desc':'性能/容量描述缺少数值+单位',
         'suggest':'附带数值+单位+测量条件'},
        # SEC 安全
        {'id':'REQ-SEC-01','name':'权限角色不完整','category':'SEC',
         'severity':Severity.BLOCKER,'source':'等价类划分法',
         'check':_check_permission,
         'desc':'角色权限矩阵不完整,部分功能权限未分配',
         'suggest':'列出全部角色,建立角色-功能权限矩阵'},
        {'id':'REQ-SEC-02','name':'敏感数据规则缺失','category':'SEC',
         'severity':Severity.CRITICAL,'source':'错误推测法',
         'check':_check_sensitive_data,
         'desc':'隐私/敏感数据的收集/存储/展示/销毁规则未定义',
         'suggest':'按生命周期定义各环节规则'},
        # AI专项
        {'id':'REQ-AI-01','name':'可能的幻觉内容','category':'AI',
         'severity':Severity.BLOCKER,'source':'AI缺陷模式(#2幻觉)',
         'check':_check_ai_hallucination,
         'desc':'AI生成需求中可能含不存在/未确认的功能/集成/技术细节',
         'suggest':'逐条与Po确认,对照架构核实'},
        {'id':'REQ-AI-02','name':'内容空洞模板化','category':'AI',
         'severity':Severity.CRITICAL,'source':'AI缺陷模式(#3过度自信)',
         'check':_check_ai_shallow,
         'desc':'结构完整但缺乏项目特有业务洞察和具体细节',
         'suggest':'补充具体业务上下文,避免通用套话'},
    ]


def _find_kw_lines(content, lines, keywords, ctx=2):
    results = []
    for i, line in enumerate(lines):
        if any(kw.lower() in line.lower() for kw in keywords):
            s, e = max(0,i-ctx), min(len(lines),i+ctx+1)
            results.append((i+1, ''.join(lines[s:e]).strip()))
    return results


def _issue(rule, fp, ln, content, detail="", ev=""):
    return ReqIssue(
        rule_id=rule['id'], rule_name=rule['name'], category=rule['category'],
        severity=rule['severity'].value, file_path=str(fp), line_number=ln,
        line_content=content[:200], description=f"{rule['desc']}: {detail}" if detail else rule['desc'],
        suggestion=rule['suggest'], method_source=rule['source'], evidence=ev or content[:200])


# ---- 规则检查函数 ----

def _check_flow_missing(fp, c, ls, r):
    issues = []
    flow_kws = ['流程','步骤','flow','process','主流程','正常流程','scenario:']
    step_pats = [r'^\d+\.', r'^\d+\)', r'step\s*\d', r'given.*when.*then']
    has_flow = any(kw in c.lower() for kw in flow_kws)
    has_step = any(re.search(p, c, re.I|re.M) for p in step_pats)
    has_us = bool(re.search(r'(?:as a|i want to|so that)', c, re.I))
    is_data = any(kw in c.lower() for kw in ['数据字典','api reference','schema'])
    if not has_flow and not has_step and not has_us and not is_data and len(ls) > 20:
        issues.append(_issue(r, fp, 0, "", "文档无流程描述"))
    return issues

def _check_boundary_missing(fp, c, ls, r):
    issues = []
    vague = [('若干','数量不明'),('多个','数量不明'),('大量','无上限'),
             ('适当','标准不明'),('合理','标准不明')]
    for v, m in vague:
        for ln, ctx in _find_kw_lines(c, ls, [v]):
            issues.append(_issue(r, fp, ln, ctx, f"模糊量词'{v}'({m})"))
    
    nums = list(re.finditer(r'\b\d{2,}\b', c))
    range_kws = ['~','-','至','到','范围内','不超过','最大','最小']
    has_range = any(rc in c for rc in range_kws)
    if len(nums) >= 3 and not has_range:
        issues.append(_issue(r, fp, 0, "", f"{len(nums)}处数值但无限定词", 
                            evidence=f"示例: {[n.group() for n in nums[:5]]}"))
    return issues

def _check_exception_missing(fp, c, ls, r):
    issues = []
    exc_kws = ['异常','错误','失败','超时','空状态','冲突','权限不足']
    alt_kws = ['extend','alternative','替代','异常流程','边界情况','error handling']
    flow_kws = ['流程','步骤','process','scenario']
    has_exc = any(kw in c.lower() for kw in exc_kws)
    has_alt = any(kw in c.lower() for kw in alt_kws)
    has_flow = any(kw in c.lower() for kw in flow_kws)
    if has_flow and not has_exc and not has_alt:
        issues.append(_issue(r, fp, 0, "", "有流程但缺异常场景"))
    elif has_flow and has_exc:
        m = _find_kw_lines(c, ls, exc_kws[:4])
        if len(m) <= 1:
            loc = m[0] if m else (0,"")
            issues.append(_issue(r, fp, loc[0], loc[1], f"异常提及过少({len(m)}处)"))
    return issues

def _check_nfr_missing(fp, c, ls, r):
    issues = []
    nfr_kws = ['非功能需求','性能指标','sla','响应时间','并发','兼容','安全要求']
    has_nfr = any(kw in c.lower() for kw in nfr_kws)
    quant = bool(re.search(r'\b(?:p50|p95|p99)\s*[<>=]+[\d.]+\s*(ms|s)?', c, re.I))
    if not has_nfr and len(ls) > 30:
        issues.append(_issue(r, fp, 0, "", "无NFR章节"))
    elif has_nfr and not quant:
        loc = _find_kw_lines(c, ls, nfr_kws[:3])
        l = loc[0] if loc else (0,"")
        issues.append(_issue(r, fp, l[0], l[1], "NFR缺量化指标"))
    return issues

def _check_data_fields(fp, c, ls, r):
    issues = []
    entities = re.findall(r'(?:用户|商品|订单|消息|评论|文件|支付|日志)[\u4e00-\u9fa5]*(?:信息|数据|表|实体)', c)
    unique = set(e.lower() for e in entities)
    has_table = bool(re.search(r'^\|?\s*(字段|field|名称|属性)\s*\|', c, re.I | re.M))
    if len(unique) >= 2 and not has_table:
        issues.append(_issue(r, fp, 0, "", f"{len(unique)}个实体但无字段定义表",
                            evidence=f"实体: {list(unique)[:5]}"))
    return issues

def _check_ac_vague(fp, c, ls, r):
    issues = []
    ac_kws = ['acceptance criteria','验收标准','ac:','验证标准','done definition']
    subj = [('良好','主观'),('美观','主观'),('流畅','主观'),('便捷','主观'),
            ('友好','主观'),('稳定','主观'),('快速','主观')]
    has_ac = any(kw in c.lower() for kw in ac_kws)
    is_ticket = any(kw in c.lower() for kw in ['user story','story:','ticket','任务','需求:'])
    if not has_ac and is_ticket:
        issues.append(_issue(r, fp, 0, "", "User Story/Ticket缺少AC"))

    for adj, meaning in subj:
        for ln, ctx in _find_kw_lines(c, ls, [adj]):
            issues.append(_issue(r, fp, ln, ctx, f"主观描述'{adj}'({meaning})"))
    return issues

def _check_ambiguous(fp, c, ls, r):
    issues = []
    amb = [('可以', '应为"必须"或"支持"'),('应该', '建议改为"必须"'),
           ('适当', '需给出具体标准'),('尽量', '做不到怎么办?'),
           ('快速', '需要量化'),('等等', '范围不明'),('类似', '需举例'),
           ('常规', '定义是什么?'),('偶尔', '频率是多少?')]
    for word, note in amb:
        for ln, ctx in _find_kw_lines(c, ls, [word]):
            issues.append(_issue(r, fp, ln, ctx, f"歧义词'{word}': {note}"))
    return issues

def _check_contradiction(fp, c, ls, r):
    issues = []
    # 简化版: 检测明显的数值矛盾
    num_constraints = re.findall(
        r'(\w{2,10}(?:长度|大小|数量|位数|密码|年龄))\s*(?:为|是|=|:)?\s*(\d+)\s*[-~至到]*\s*(\d*)', c)
    # 收集同类约束的不同定义
    constraint_map = {}
    for name, val1, val2 in num_constraints:
        key = name.lower()
        val = f"{val1}-{val2}" if val2 else val1
        if key in constraint_map and constraint_map[key] != val:
            issues.append(_issue(r, fp, 0, "", 
                f"'{name}'在不同位置有不同约束: '{constraint_map[key]}' vs '{val}'"))
            break
        constraint_map[key] = val
    return issues

def _check_dependency(fp, c, ls, r):
    issues = []
    dep_signals = ['依赖','对接','集成','调用','前置条件','prerequisite','depends on','integration']
    has_dep_mention = any(kw in c.lower() for kw in dep_signals)
    # 如果文档提到外部系统/API但没有明确的依赖声明格式
    external_sys = re.findall(r'([A-Z][a-zA-Z]+(?:系统|API|平台|服务|接口))', c)
    has_dep_table = bool(re.search(r'依赖|depend', c, re.I)) and ':' in c[c.lower().find('依赖'):c.lower().find('依赖')+50] if '依赖' in c.lower() else False
    
    if len(external_sys) >= 2 and not has_dep_table:
        issues.append(_issue(r, fp, 0, "",
            f"提到{len(external_sys)}个外部系统({', '.join(external_sys[:5])})但无正式依赖声明表"))
    return issues

def _check_unverifiable(fp, c, ls, r):
    issues = []
    unverifiable = [('用户体验好', 'P95操作步数≤5'),('界面美观', '设计评审通过vX.Y'),
                    ('运行流畅', '帧率≥60FPS/P95<100ms'),('系统稳定', 'MTTR<1h/可用率≥99.9%'),
                    ('易于使用', '新手完成核心任务≤3步'),('专业感强', '通过品牌规范审核')]
    for phrase, fix in unverifiable:
        for ln, ctx in _find_kw_lines(c, ls, [phrase]):
            issues.append(_issue(r, fp, ln, ctx, f"主观描述'{phrase}'", f"建议: {fix}"))
    return issues

def _check_no_quantify(fp, c, ls, r):
    issues = []
    vague_perf = [(r'(?<!\d)(?:响应|加载|查询|请求).*(?:快|迅速|及时|慢)', '应量化如P95<Xms>'),
                   (r'(?:支持|允许|最多|最大).*(?:多人|大量|并发|同时)', '应量化如<N>并发'),
                   (r'(?:高.?准确|高.?精度|高.?可用)', '应量化如≥99%')]
    for pat, fix in vague_perf:
        for m in re.finditer(pat, c, re.I):
            ln = c[:m.start()].count('\n')
            issues.append(_issue(r, fp, ln+1, ls[ln].strip(), "性能/容量描述未量化", fix))
    return issues

def _check_permission(fp, c, ls, r):
    issues = []
    role_kws = ['角色','role','管理员','普通用户','访客','guest','admin','user','权限','permission']
    has_role_section = any(kw in c.lower() for kw in role_kws)
    perm_matrix = bool(re.search(r'(权限|permission).*(?:矩阵|matrix|表格|table|分配|assign)', c, re.I))
    
    if has_role_section and not perm_matrix:
        roles_found = set()
        for kw in ['管理员','admin','用户','user','访客','guest','运营','operator']:
            if kw in c.lower(): roles_found.add(kw)
        if len(roles_found) >= 2:
            issues.append(_issue(r, fp, 0, "", 
                f"提到{len(roles_found)}种角色({', '.join(roles_found)})但无权限矩阵"))
    return issues

def _check_sensitive_data(fp, c, ls, r):
    issues = []
    sensitive_kws = ['隐私','privacy','gdpr','个人信息','敏感数据','加密','脱敏','匿名','销毁','保留期限']
    has_privacy = any(kw in c.lower() for kw in sensitive_kws)
    # 检查是否涉及用户个人信息
    personal_data = any(kw in c.lower() for kw in ['手机号','身份证','银行卡','密码','住址','实名'])
    
    if personal_data and not has_privacy:
        issues.append(_issue(r, fp, 0, "", "涉及个人隐私信息但无数据处理规则说明"))
    return issues

def _check_ai_hallucination(fp, c, ls, r):
    issues = []
    hallucination_patterns = [
        (r'(?:对接|集成|调用)\s*(?:支付宝|微信支付?|钉钉|飞书|企业微信|AWS|Azure|GCP)\s*(?:API|接口|平台|SDK)', '第三方集成声明'),
        (r'(?:遵循|符合|满足|按照)\s*(?:GDPR|SOX|PCI-DSS|HIPAA|等保|ISO27001|SOC2)', '合规引用'),
        (r'(?:版本|version)\s*v?(?:\d+\.){2,}\d+', '具体版本号'),
    ]
    for pat, desc in hallucination_patterns:
        matches = re.findall(pat, c, re.I)
        if matches:
            # 标记供人工确认
            for m in matches[:2]:
                ln = c[:c.find(m)].count('\n') if c.find(m) >= 0 else 0
                issues.append(_issue(r, fp, ln+1, (ls[ln] if ln < len(ls) else ""), 
                    f"AI可能编造的内容需确认: [{m}] ({desc})", "请与产品经理确认此项是否属实"))
    return issues

def _check_ai_shallow(fp, c, ls, r):
    issues = []
    shallow_indicators = [
        ('本系统旨在提供良好的用户体验', '过于通用的目标描述'),
        ('本模块遵循业界最佳实践', '空洞的套话'),
        ('具体实现细节将在后续迭代中确定', '推迟关键决策'),
        ('该功能将显著提升工作效率', '无可衡量的效果声称'),
    ]
    for pattern, note in shallow_indicators:
        if pattern.lower() in c.lower():
            ln = c.lower().index(pattern.lower())
            line_num = c[:ln].count('\n')
            issues.append(_issue(r, fp, line_num+1, ls[line_num].strip(), 
                f"AI套话模式: '{pattern[:30]}'", note))
    
    # 检查: NFR章节是否全是通用内容
    nfr_generic_phrases = ['高性能','高可用','高安全性','易扩展','易维护','用户体验好']
    generic_count = sum(1 for p in nfr_generic_phrases if p in c)
    if generic_count >= 3:
        issues.append(_issue(r, fp, 0, "",
            f"NFR章节包含{generic_count}处通用描述,缺乏项目特有的量化指标"))
    return issues


# ============================================================
# 扫描引擎
# ============================================================

def scan_file(filepath: Path, rules: list) -> ReqScanResult:
    """扫描单个文件"""
    content = filepath.read_text(encoding='utf-8', errors='ignore')
    lines = content.splitlines()
    
    ext = filepath.suffix.lower()
    file_type = 'markdown' if ext == '.md' else ('text' if ext in ('.txt','.rst') else ext.strip('.'))
    
    result = ReqScanResult(file_path=str(filepath), file_type=file_type,
                             total_lines=len(lines), total_chars=len(content))
    
    for rule in rules:
        try:
            found_issues = rule['check'](filepath, content, lines, rule)
            result.issues.extend(found_issues)
        except Exception as e:
            # 规则执行出错不影响其他规则
            pass
    
    return result


def scan_directory(dirpath: Path, rules: list) -> ReqScanReport:
    """批量扫描目录"""
    report = ReqScanReport(target=str(dirpath), mode='text')
    
    supported_ext = {'.md', '.txt', '.rst'}
    files = []
    for ext in supported_ext:
        files.extend(dirpath.rglob(f'*{ext}'))
    
    # 排除隐藏文件和大型文件
    files = [f for f in files if not f.name.startswith('.') and f.stat().st_size < 500*1024]
    files.sort()
    
    for f in files:
        result = scan_file(f, rules)
        report.results.append(result)
        report.total_files += 1
        report.total_issues += len(result.issues)
    
    return report


# ============================================================
# 输出格式化
# ============================================================

def format_console_report(report: ReqScanReport):
    """控制台输出"""
    print("\n" + "=" * 70)
    print(f"   需求文档质量检测报告  |  扫描目标: {report.target}")
    print("=" * 70)
    
    grade = "A(优秀)" if report.overall_score >= 85 else ("B(良好)" if report.overall_score >= 70 else ("C(合格)" if report.overall_score >= 55 else "D(不合格)"))
    gate_icon = "✅ PASS" if report.pass_gate else "🔴 BLOCK"
    
    print(f"\n  总体评分: {report.overall_score}/100  |  等级: {grade}  |  门禁: {gate_icon}")
    print(f"  文件数: {report.total_files}  |  问题数: {report.total_issues}")
    print(f"  🔴阻断: {report.total_blockers}  🟠严重: {report.total_criticals}  🟡一般: {report.total_majors}  🔵轻微: {report.total_minors}")
    
    for r in report.results:
        icon = "✅" if r.pass_gate else "🔴"
        print(f"\n{'─'*60}")
        print(f"  {icon} {Path(r.file_path).name}  ({r.file_type}, {r.total_lines}行, 得分: {r.score})")
        
        if not r.issues:
            print("     未发现问题 ✨")
            continue
        
        # 按严重程度排序显示
        sorted_issues = sorted(r.issues, key=lambda x: SEVERITY_SCORE.get(Severity(x.severity), 0), reverse=True)
        
        for issue in sorted_issues:
            sev_icon = {"BLOCKER":"🔴","CRITICAL":"🟠","MAJOR":"🟡","MINOR":"🔵"}.get(issue.severity, "⚪")
            loc = f":L{issue.line_number}" if issue.line_number > 0 else ""
            print(f"     {sev_icon} [{issue.rule_id}] {issue.rule_name}{loc}")
            print(f"        {issue.description[:120]}")
            if issue.evidence and len(issue.evidence) > 10:
                print(f"        证据: {issue.evidence[:80]}...")
            print(f"        → {issue.suggestion[:100]}")
    
    print(f"\n{'='*70}")
    
    # 方法覆盖统计
    method_stats = {}
    all_issues = [i for r in report.results for i in r.issues]
    for i in all_issues:
        src = i.method_source.split('(')[0].strip() if '(' in i.method_source else i.method_source
        method_stats[src] = method_stats.get(src, 0) + 1
    
    if method_stats:
        print(f"\n  测试方法覆盖 (问题分布):")
        for method, count in sorted(method_stats.items(), key=lambda x:-x[1]):
            print(f"    • {method}: {count} 个问题")


def format_html_report(report: ReqScanReport) -> str:
    """HTML报告输出"""
    grade_color = "#22c55e" if report.overall_score >= 85 else ("#f59e0b" if report.overall_score >= 70 else ("#f97316" if report.overall_score >= 55 else "#ef4444"))
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>需求质量检测报告</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:1200px;margin:0 auto;padding:20px;color:#1f2937;background:#f8fafc}}
.header{{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:24px;border-radius:12px;margin-bottom:24px}}
.summary-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin:20px 0}}
.stat-card{{background:white;padding:20px;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.1);text-align:center}}
.stat-value{{font-size:28px;font-weight:700}}
.stat-label{{font-size:13px;color:#6b7280;margin-top:4px}}
.issue-table{{width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.issue-table th{{background:#f1f5f9;text-align:left;padding:12px;font-size:13px;color:#475569}}
.issue-table td{{padding:10px 12px;border-top:1px solid #e2e8f0;font-size:13px;vertical-align:top}}
.blocker{{background:#fef2f2;border-left:4px solid #ef4444}}
.critical{{background:#fffbeb;border-left:4px solid #f59e0b}}
.major{{background:#fefce8;border-left:4px solid #eab308}}
.minor{{background:#f0fdf4;border-left:4px solid #22c55e}}
.rule-id{{font-family:monospace;font-size:12px;background:#e2e8f0;padding:2px 6px;border-radius:4px}}
.file-card{{background:white;border-radius:10px;padding:16px;margin:12px 0;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600}}
.badge-blocker{{background:#fecaca;color:#991b1b}}.badge-critical{{background:#fef3c7','#92400e'}
.badge-major{{background:#fef9c3','#854d0e'} .badge-minor{{background:#dcfce7','#166534}}
</style></head><body>
<div class="header">
<h1 style="margin:0">📋 需求文档质量检测报告</h1>
<p style="margin:8px 0 0;opacity:.9">目标: {report.target} | 文件数: {report.total_files}</p>
</div>

<div class="summary-grid">
<div class="stat-card"><div class="stat-value" style="color:{grade_color}">{report.overall_score}</div><div class="stat-label">质量得分</div></div>
<div class="stat-card"><div class="stat-value">{"✅" if report.pass_gate else "🔴"}</div><div class="stat-label">门禁结果</div></div>
<div class="stat-card"><div class="stat-value">{report.total_blockers}</div><div class="stat-label">阻断问题</div></div>
<div class="stat-card"><div class="stat-value">{report.total_criticals}</div><div class="stat-label">严重问题</div></div>
<div class="stat-card"><div class="stat-value">{report.total_majors}</div><div class="stat-label">一般问题</div></div>
<div class="stat-card"><div class="stat-value">{report.total_minors}</div><div class="stat-label">轻微问题</div></div>
</div>
"""
    
    for r in report.results:
        fname = Path(r.file_path).name
        html += f'<div class="file-card"><h3 style="margin:0 0 12px">📄 {fname}'
        html += f' <span style="font-size:13px;color:#6b7280">({r.total_lines}行 | 得分:{r.score})</span>'
        html += f' {"✅ PASS" if r.pass_gate else "⚠️ ISSUES"}</h3>'
        
        if r.issues:
            sorted_issues = sorted(r.issues, key=lambda x: SEVERITY_SCORE.get(Severity(x.severity), 0), reverse=True)
            html += '<table class="issue-table"><tr><th>级别</th><th>规则</th><th>描述</th><th>建议</th></tr>'
            for iss in sorted_issues:
                sev_class = iss.severity.lower()
                html += f'<tr class="{sev_class}">'
                html += f'<td><span class="badge badge-{sev_class}">{iss.severity}</span></td>'
                html += f'<td><span class="rule-id">{iss.rule_id}</span> {iss.rule_name}</td>'
                html += f'<td>{iss.description[:150]}</td>'
                html += f'<td>{iss.suggestion[:150]}</td></tr>'
            html += '</table>'
        else:
            html += '<p style="color:#22c55e">✨ 未发现问题</p>'
        html += '</div>'
    
    html += "</body></html>"
    return html


# ============================================================
# CLI入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='需求文档质量检测器 - 基于测试方法论')
    parser.add_argument('target', help='目标文件或目录')
    parser.add_argument('--mode', choices=['text','figma'], default='text', help='扫描模式 (default: text)')
    parser.add_argument('--output', choices=['json','html','console'], default='console', help='输出格式')
    parser.add_argument('--batch', action='store_true', help='批量扫描目录')
    
    args = parser.parse_args()
    
    target = Path(args.target)
    if not target.exists():
        print(f"❌ 目标不存在: {target}")
        sys.exit(1)
    
    rules = build_rules()
    
    if target.is_dir() or args.batch:
        if target.is_file():
            target = target.parent
        report = scan_directory(target, rules)
    else:
        result = scan_file(target, rules)
        report = ReqScanReport(target=str(target), mode=args.mode)
        report.total_files = 1
        report.total_issues = len(result.issues)
        report.results = [result]
    
    if args.output == 'json':
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    elif args.output == 'html':
        print(format_html_report(report))
    else:
        format_console_report(report)
    
    sys.exit(0 if report.pass_gate else 1)


if __name__ == '__main__':
    main()
