#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Strategy Generator
=======================
基于代码变更 + 需求内容 + 耦合场景，自动推导并输出测试策略。

输入：
  - 需求 YAML/JSON 文件（或命令行参数）
  - Git diff / PR 变更文件清单
  - 可选：耦合场景 YAML/JSON

输出：
  - Markdown 策略文档
  - JSON 结构化策略数据

使用：
  python test-strategy-generator.py \\
      --requirement req.yaml \\
      --diff-from main --diff-to HEAD \\
      [--coupling coupling.yaml] \\
      [--output-md strategy.md] \\
      [--output-json strategy.json]

  或直接从当前仓库推导:
  python test-strategy-generator.py --requirement req.yaml --repo .
"""

from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ============================================================
# 规则库
# ============================================================

# 新功能触发规则
NEW_FEATURE_RULES = {
    "NEW-01": {"desc": "新增功能类型", "keywords": ["new_feature"]},
    "NEW-02": {"desc": "新增字段/参数", "patterns": [r"\+\s*\w+\s*[:=]"]},
    "NEW-03": {"desc": "新增状态/枚举", "patterns": [r"enum\s+\w+", r"const\s+\w+\s*="]},
    "NEW-04": {"desc": "新增定时/异步流程", "patterns": [r"setInterval", r"setTimeout", r"cron", r"schedule"]},
    "NEW-05": {"desc": "新增前端组件", "file_patterns": [r"\.tsx?$", r"\.vue$", r"\.jsx?$"]},
}

# 存量影响触发规则
IMPACT_RULES = {
    "IMP-01": {"desc": "公共函数/工具类变更", "path_patterns": [r"utils?/", r"common/", r"helpers?/", r"lib/"]},
    "IMP-02": {"desc": "共享 Store/全局状态", "patterns": [r"redux", r"vuex", r"pinia", r"zustand", r"mobx", r"store"]},
    "IMP-03": {"desc": "接口出入参变更", "patterns": [r"@app\.route", r"router\.", r"@RequestMapping", r"fastapi"]},
    "IMP-04": {"desc": "数据库 schema 变更", "patterns": [r"CREATE\s+TABLE", r"ALTER\s+TABLE", r"migration", r"schema\."], "path_patterns": [r"migrations?/", r"schema/"]},
    "IMP-05": {"desc": "配置/开关变更", "file_patterns": [r"config", r"\.env", r"settings\.", r"feature.?flag"]},
    "IMP-06": {"desc": "路由/导航变更", "patterns": [r"router\.", r"Route\s*=", r"path:", r"navigate"]},
    "IMP-07": {"desc": "权限/登录逻辑变更", "patterns": [r"auth", r"login", r"permission", r"role", r"token"]},
    "IMP-08": {"desc": "埋点/日志变更", "patterns": [r"track\(", r"logger\.", r"analytics\.", r"reportEvent"]},
    "IMP-09": {"desc": "支付/结算变更", "patterns": [r"payment", r"pay\(", r"order", r"checkout", r"wx\.requestPayment"]},
    "IMP-10": {"desc": "引入新依赖", "file_patterns": [r"package\.json$", r"requirements\.txt$", r"go\.mod$", r"pom\.xml$", r"build\.gradle$"]},
}

# 兼容性触发规则
COMPAT_RULES = {
    "COMPAT-01": {"desc": "底层代码逻辑变更", "path_patterns": [r"sdk/", r"core/", r"engine/", r"native/"], "severity": "HIGH"},
    "COMPAT-02": {"desc": "系统 API 变更", "patterns": [r"android\.os\.", r"UIKit", r"Foundation", r"win32"], "severity": "HIGH"},
    "COMPAT-03": {"desc": "客户端原生层变更", "file_patterns": [r"\.swift$", r"\.m$", r"\.mm$", r"\.java$", r"\.kt$", r"\.cpp$", r"\.c$", r"\.h$"], "severity": "HIGH"},
    "COMPAT-04": {"desc": "渲染引擎/图形变更", "patterns": [r"OpenGL", r"Vulkan", r"DirectX", r"Metal", r"WebGL", r"canvas", r"GPU"], "severity": "HIGH"},
    "COMPAT-05": {"desc": "使用新系统 API", "patterns": [r"@available", r"Build\.VERSION_CODES\.[A-Z]"], "severity": "MEDIUM"},
    "COMPAT-06": {"desc": "浏览器新特性", "patterns": [r":has\(", r"container-type", r"view-transition", r"OptionalChaining"], "severity": "MEDIUM"},
    "COMPAT-07": {"desc": "引入新依赖/升级", "file_patterns": [r"package\.json$", r"yarn\.lock$", r"package-lock\.json$", r"Podfile", r"build\.gradle$"], "severity": "MEDIUM"},
    "COMPAT-08": {"desc": "分辨率/DPI 布局变更", "patterns": [r"@media", r"vw|vh", r"rem\b", r"dpi", r"pixelRatio"], "severity": "MEDIUM"},
    "COMPAT-09": {"desc": "虚拟化/模拟器相关", "patterns": [r"VirtualBox", r"Hyper-V", r"NEMU", r"emulator"], "severity": "HIGH"},
    "COMPAT-10": {"desc": "多语言/国际化变更", "patterns": [r"i18n", r"intl", r"locale", r"translate"], "severity": "MEDIUM"},
}

# 弱网触发规则
NET_RULES = {
    "NET-01": {"desc": "新增/修改网络请求", "patterns": [r"fetch\(", r"axios\.", r"XMLHttpRequest", r"requests\.", r"http\.Get", r"OkHttp", r"URLSession"]},
    "NET-02": {"desc": "大文件下载/上传", "patterns": [r"download", r"upload", r"multipart", r"stream"]},
    "NET-03": {"desc": "长连接/WebSocket/推送", "patterns": [r"WebSocket", r"SSE", r"EventSource", r"socket\.io", r"mqtt", r"push"]},
    "NET-04": {"desc": "支付/订单关键流程", "patterns": [r"payment", r"pay\(", r"order", r"checkout"]},
    "NET-05": {"desc": "首屏/关键业务路径", "path_patterns": [r"(home|index|main|landing)", r"splash"]},
    "NET-06": {"desc": "数据同步/云存储", "patterns": [r"sync\(", r"cloud", r"oss\.", r"cos\."]},
    "NET-07": {"desc": "直播/音视频", "patterns": [r"rtmp", r"hls", r"webrtc", r"live", r"video", r"audio"]},
    "NET-08": {"desc": "离线可用功能", "patterns": [r"offline", r"ServiceWorker", r"cache"]},
}

# 历史版本触发规则
HIST_RULES = {
    "HIST-01": {"desc": "DB schema/数据迁移", "patterns": [r"ALTER\s+TABLE", r"migration"], "severity": "HIGH"},
    "HIST-02": {"desc": "前端依赖客户端版本", "patterns": [r"client.?version", r"appVersion", r"Build\.VERSION"], "severity": "HIGH"},
    "HIST-03": {"desc": "协议新增字段（非破坏性）", "patterns": [r"@JsonProperty", r"@SerializedName", r"optional\s+\w+"], "severity": "LOW"},
    "HIST-04": {"desc": "协议破坏性变更", "manual_flag": "breaking_change", "severity": "HIGH"},
    "HIST-05": {"desc": "本地存储结构变更", "patterns": [r"localStorage", r"sessionStorage", r"SharedPreferences", r"UserDefaults", r"MMKV"], "severity": "HIGH"},
    "HIST-06": {"desc": "配置/开关默认值变更", "patterns": [r"default\s*[:=]", r"DEFAULT_"], "severity": "MEDIUM"},
    "HIST-07": {"desc": "业务规则变更", "manual_flag": "business_rule_change", "severity": "MEDIUM"},
    "HIST-08": {"desc": "强制升级/热更新", "patterns": [r"forceUpdate", r"hotfix", r"hot.?reload"], "severity": "HIGH"},
    "HIST-09": {"desc": "权限/隐私合规变更", "patterns": [r"permission", r"privacy", r"GDPR", r"consent"], "severity": "HIGH"},
    "HIST-10": {"desc": "登录态结构变更", "patterns": [r"token", r"session", r"cookie"], "severity": "HIGH"},
}

# 性能测试触发规则
PERF_RULES = {
    "PERF-01": {"desc": "新增后端接口/API",
                "patterns": [r"@app\.route", r"@(Get|Post|Put|Delete)Mapping", r"router\.(get|post|put|delete)\(",
                             r"app\.(get|post|put|delete)\(", r"fastapi", r"@RequestMapping"],
                "severity": "HIGH"},
    "PERF-02": {"desc": "接口入参/返回数据量显著增加",
                "manual_flag": "data_size_increase", "severity": "MEDIUM"},
    "PERF-03": {"desc": "新增/修改数据库查询",
                "patterns": [r"SELECT\s+", r"\.find\(", r"\.query\(", r"\.aggregate\(",
                             r"createQuery", r"@Query", r"Repository"],
                "severity": "HIGH"},
    "PERF-04": {"desc": "循环内 I/O 或 N+1 查询",
                "patterns": [r"for\s*\([^)]+\)\s*\{[^}]*(?:SELECT|query|fetch|findById)",
                             r"for\s+\w+\s+in\s+[^:]+:\s*\n\s*[^\n]*(?:query|find|fetch)"],
                "severity": "HIGH"},
    "PERF-05": {"desc": "新增/修改缓存",
                "patterns": [r"redis\.", r"@Cacheable", r"cache\.", r"Memcache", r"LRUCache"],
                "severity": "MEDIUM"},
    "PERF-06": {"desc": "大数据量处理（批处理/导出/搜索/推荐）",
                "patterns": [r"batch", r"bulk", r"export", r"elasticsearch", r"recommend"],
                "severity": "MEDIUM"},
    "PERF-07": {"desc": "首屏/关键路径渲染变更",
                "path_patterns": [r"(home|index|main|landing|splash)", r"App\.(tsx|vue|jsx)"],
                "severity": "HIGH"},
    "PERF-08": {"desc": "动画/复杂渲染/GPU操作",
                "patterns": [r"requestAnimationFrame", r"transform:", r"WebGL", r"canvas",
                             r"OpenGL", r"Vulkan", r"@keyframes"],
                "severity": "MEDIUM"},
    "PERF-09": {"desc": "定时/轮询/长连接/后台任务",
                "patterns": [r"setInterval", r"cron", r"schedule", r"WorkManager",
                             r"WebSocket", r"@Scheduled"],
                "severity": "MEDIUM"},
    "PERF-10": {"desc": "大文件读写/大量小文件 I/O",
                "patterns": [r"readFile", r"writeFile", r"FileOutputStream", r"multipart",
                             r"stream\.pipe"],
                "severity": "MEDIUM"},
    "PERF-11": {"desc": "引入新依赖库/SDK",
                "file_patterns": [r"package\.json$", r"yarn\.lock$", r"package-lock\.json$",
                                  r"Podfile", r"build\.gradle$", r"requirements\.txt$", r"go\.mod$"],
                "severity": "MEDIUM"},
    "PERF-12": {"desc": "算法/循环/排序复杂度变更",
                "patterns": [r"for\s*\([^)]*\)\s*\{[^}]*for\s*\(",  # 嵌套循环
                             r"\.sort\(", r"recursion", r"recursive"],
                "severity": "MEDIUM"},
    "PERF-13": {"desc": "并发/锁/线程池变更",
                "patterns": [r"synchronized", r"ReentrantLock", r"Mutex", r"ThreadPool",
                             r"ExecutorService", r"goroutine", r"async\s+", r"await\s+"],
                "severity": "MEDIUM"},
    "PERF-14": {"desc": "多端联调/分布式调用",
                "patterns": [r"grpc", r"rpc\.", r"micro.*service", r"dubbo", r"feign"],
                "severity": "MEDIUM"},
    "PERF-15": {"desc": "性能敏感业务（支付/直播/活动/高并发）",
                "manual_flag": "high_concurrency",
                "patterns": [r"payment", r"live", r"rtmp", r"hls", r"seckill", r"flash.?sale"],
                "severity": "HIGH"},
}


# ============================================================
# 数据类
# ============================================================

@dataclass
class CodeChange:
    changed_files: list[dict] = field(default_factory=list)
    changed_modules: set[str] = field(default_factory=set)
    total_added: int = 0
    total_deleted: int = 0
    has_native: bool = False
    has_db_schema: bool = False
    has_config: bool = False


@dataclass
class TriggeredRule:
    rule_id: str
    description: str
    evidence: list[str] = field(default_factory=list)
    severity: str = "MEDIUM"


@dataclass
class DimensionResult:
    dimension: str
    required: bool
    priority: str  # P0/P1/P2
    triggered_rules: list[TriggeredRule]
    details: dict[str, Any] = field(default_factory=dict)


# ============================================================
# 输入采集
# ============================================================

def load_yaml_or_json(path: str) -> dict:
    if not os.path.exists(path):
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
        raise


def collect_git_diff(repo: str, base: str, head: str) -> CodeChange:
    """从 git 仓库采集 diff 信息"""
    change = CodeChange()
    try:
        # 获取文件清单和 numstat
        result = subprocess.run(
            ["git", "-C", repo, "diff", "--numstat", f"{base}...{head}"],
            capture_output=True, text=True, check=True, encoding="utf-8"
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            added, deleted, path = parts[0], parts[1], parts[2]
            added_n = int(added) if added.isdigit() else 0
            deleted_n = int(deleted) if deleted.isdigit() else 0
            change.changed_files.append({
                "path": path,
                "added": added_n,
                "deleted": deleted_n,
                "change_type": "modify" if deleted_n > 0 else "new",
            })
            change.total_added += added_n
            change.total_deleted += deleted_n
            # 模块提取：取前两级目录
            mod = "/".join(path.split("/")[:2])
            change.changed_modules.add(mod)
            # 检测原生/schema/config
            lower = path.lower()
            if re.search(r"\.(swift|m|mm|java|kt|cpp|c|h)$", lower):
                change.has_native = True
            if "migration" in lower or "schema" in lower or lower.endswith(".sql"):
                change.has_db_schema = True
            if "config" in lower or lower.endswith(".env") or "feature" in lower:
                change.has_config = True
    except subprocess.CalledProcessError as e:
        print(f"[WARN] git diff 失败: {e.stderr}", file=sys.stderr)
    except FileNotFoundError:
        print(f"[WARN] 未检测到 git 命令或仓库", file=sys.stderr)
    return change


def get_diff_content(repo: str, base: str, head: str, max_size: int = 500_000) -> str:
    """获取完整 diff 文本用于正则匹配"""
    try:
        result = subprocess.run(
            ["git", "-C", repo, "diff", f"{base}...{head}"],
            capture_output=True, text=True, check=True, encoding="utf-8"
        )
        return result.stdout[:max_size]
    except Exception:
        return ""


# ============================================================
# 规则匹配引擎
# ============================================================

def match_rules(rules: dict, change: CodeChange, diff_text: str,
                requirement: dict, manual_flags: dict) -> list[TriggeredRule]:
    triggered: list[TriggeredRule] = []
    for rid, rule in rules.items():
        evidence: list[str] = []

        # keywords（需求类型匹配）
        if "keywords" in rule:
            req_type = requirement.get("type", "")
            for kw in rule["keywords"]:
                if kw in req_type:
                    evidence.append(f"需求类型: {req_type}")

        # 文件路径模式
        if "path_patterns" in rule:
            for fp in change.changed_files:
                for pat in rule["path_patterns"]:
                    if re.search(pat, fp["path"], re.IGNORECASE):
                        evidence.append(f"路径匹配: {fp['path']}")
                        break

        # 文件名模式
        if "file_patterns" in rule:
            for fp in change.changed_files:
                for pat in rule["file_patterns"]:
                    if re.search(pat, fp["path"], re.IGNORECASE):
                        evidence.append(f"文件匹配: {fp['path']}")
                        break

        # diff 正文模式
        if "patterns" in rule and diff_text:
            for pat in rule["patterns"]:
                matches = re.findall(pat, diff_text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    evidence.append(f"代码匹配 {pat}: {len(matches)} 处")

        # 手动标志
        if "manual_flag" in rule:
            flag = rule["manual_flag"]
            if manual_flags.get(flag):
                evidence.append(f"手动标注: {flag}=true")

        if evidence:
            triggered.append(TriggeredRule(
                rule_id=rid,
                description=rule.get("desc", ""),
                evidence=evidence[:5],  # 限制证据数量
                severity=rule.get("severity", "MEDIUM"),
            ))
    return triggered


# ============================================================
# 五维决策引擎
# ============================================================

def decide_new_feature(requirement: dict, change: CodeChange, diff: str) -> DimensionResult:
    triggered = match_rules(NEW_FEATURE_RULES, change, diff, requirement, {})
    req_type = requirement.get("type", "")
    required = req_type in ("new_feature", "modify") or len(triggered) > 0
    priority = "P0" if req_type == "new_feature" else ("P1" if triggered else "P2")

    items = []
    for ac in requirement.get("acceptance_criteria", []):
        items.append({"point": ac, "source": requirement.get("id", "REQ"), "priority": priority})

    return DimensionResult(
        dimension="new_feature_scope",
        required=required,
        priority=priority,
        triggered_rules=triggered,
        details={
            "items": items,
            "test_types": ["正向功能", "反向功能", "边界值", "异常场景", "UI 状态"],
            "modules": list(change.changed_modules),
        },
    )


def decide_regression(requirement: dict, change: CodeChange, diff: str, coupling: dict) -> DimensionResult:
    triggered = match_rules(IMPACT_RULES, change, diff, requirement, {})
    upstream = coupling.get("upstream_callers", [])
    downstream = coupling.get("downstream_deps", [])
    shared_state = coupling.get("shared_state", [])
    cross_flows = coupling.get("cross_module_flows", [])

    required = bool(triggered) or bool(upstream) or bool(shared_state)
    # 高危规则触发 P0
    high_rules = {"IMP-01", "IMP-02", "IMP-03", "IMP-04", "IMP-07", "IMP-09"}
    priority = "P0" if any(t.rule_id in high_rules for t in triggered) else ("P1" if triggered else "P2")

    return DimensionResult(
        dimension="regression_scope",
        required=required,
        priority=priority,
        triggered_rules=triggered,
        details={
            "affected_modules": list(change.changed_modules),
            "upstream_callers": upstream,
            "downstream_deps": downstream,
            "shared_state": shared_state,
            "cross_flows": cross_flows,
        },
    )


def decide_compatibility(requirement: dict, change: CodeChange, diff: str) -> DimensionResult:
    triggered = match_rules(COMPAT_RULES, change, diff, requirement, {})
    high_rules = {"COMPAT-01", "COMPAT-03", "COMPAT-04", "COMPAT-09"}
    required = any(t.rule_id in high_rules for t in triggered) or change.has_native
    priority = "P0" if required else ("P1" if triggered else "P2")

    platforms = requirement.get("platforms", [])
    matrix = {}
    if "Android" in platforms:
        matrix["android"] = ["8.0", "10", "13", "14"]
    if "iOS" in platforms:
        matrix["ios"] = ["15", "16", "17"]
    if "PC" in platforms:
        matrix["pc_os"] = ["Win10", "Win11", "macOS 13"]
        matrix["resolution"] = ["1080P", "2K", "4K"]
        matrix["gpu"] = ["NVIDIA", "AMD", "Intel"]
    if "H5" in platforms:
        matrix["browser"] = ["Chrome", "Safari", "Firefox", "Edge"]

    return DimensionResult(
        dimension="compatibility_test",
        required=required,
        priority=priority,
        triggered_rules=triggered,
        details={"matrix": matrix, "has_native_change": change.has_native},
    )


def decide_weak_network(requirement: dict, change: CodeChange, diff: str) -> DimensionResult:
    triggered = match_rules(NET_RULES, change, diff, requirement, {})
    critical_rules = {"NET-01", "NET-04", "NET-05"}
    required = any(t.rule_id in critical_rules for t in triggered)
    priority = "P0" if any(t.rule_id in {"NET-04"} for t in triggered) else ("P1" if required else "P2")

    scenarios = []
    rule_ids = {t.rule_id for t in triggered}
    if rule_ids & {"NET-01", "NET-05"}:
        scenarios.extend(["2G (50Kbps/500ms/5%丢包)", "请求超时", "断网"])
    if rule_ids & {"NET-02"}:
        scenarios.extend(["下载暂停", "续传", "网络切换"])
    if rule_ids & {"NET-03"}:
        scenarios.extend(["断连重连", "消息不丢失", "间歇性断网"])
    if rule_ids & {"NET-04"}:
        scenarios.extend(["支付中断网", "订单一致性", "幂等性验证"])
    if rule_ids & {"NET-07"}:
        scenarios.extend(["弱网卡顿", "降码率", "切流"])

    return DimensionResult(
        dimension="weak_network_test",
        required=required,
        priority=priority,
        triggered_rules=triggered,
        details={"scenarios": list(dict.fromkeys(scenarios))},  # 去重保序
    )


def decide_historical_version(requirement: dict, change: CodeChange, diff: str, manual_flags: dict) -> DimensionResult:
    triggered = match_rules(HIST_RULES, change, diff, requirement, manual_flags)
    high_rules = {"HIST-01", "HIST-02", "HIST-04", "HIST-05", "HIST-08", "HIST-09", "HIST-10"}
    required = any(t.rule_id in high_rules for t in triggered) or change.has_db_schema
    priority = "P0" if any(t.rule_id in {"HIST-01", "HIST-04"} for t in triggered) else ("P1" if required else "P2")

    versions = []
    rule_ids = {t.rule_id for t in triggered}
    if rule_ids & {"HIST-04"}:
        versions.extend(["N-1", "N-2", "N-3", "最低支持版本"])
    elif rule_ids & {"HIST-02", "HIST-05", "HIST-10"}:
        versions.extend(["N-1", "N-2", "最低支持版本"])
    elif required:
        versions.append("N-1")

    client_min = requirement.get("dependencies", {}).get("client_min_version", "")
    if client_min:
        versions.append(f"客户端 {client_min} 及更早版本")

    return DimensionResult(
        dimension="historical_version_test",
        required=required,
        priority=priority,
        triggered_rules=triggered,
        details={
            "versions": versions,
            "data_migration": change.has_db_schema or manual_flags.get("data_migration", False),
        },
    )


def decide_performance(requirement: dict, change: CodeChange, diff: str,
                        manual_flags: dict) -> DimensionResult:
    triggered = match_rules(PERF_RULES, change, diff, requirement, manual_flags)
    # 高危触发 P0：新接口/DB/首屏/高并发业务
    high_rules = {"PERF-01", "PERF-03", "PERF-04", "PERF-07", "PERF-15"}
    is_high = any(t.rule_id in high_rules for t in triggered) or \
              manual_flags.get("high_concurrency", False)
    # 只要触发了任何 PERF 规则，就至少"建议测"
    required = bool(triggered) or is_high
    if manual_flags.get("high_concurrency", False) or any(t.rule_id == "PERF-15" for t in triggered):
        priority = "P0"
    elif is_high:
        priority = "P0"
    elif triggered:
        priority = "P1"
    else:
        priority = "P2"

    # 组装测试范围
    scope: list[str] = []
    rule_ids = {t.rule_id for t in triggered}
    if rule_ids & {"PERF-01"}:
        scope.append("接口性能测试（P95<200ms / QPS ≥ 基线 / 错误率<0.1%）")
    if rule_ids & {"PERF-03", "PERF-04"}:
        scope.append("SQL 慢查询 + 索引命中基准测试")
    if rule_ids & {"PERF-05"}:
        scope.append("缓存命中率 + 穿透/雪崩预案验证")
    if rule_ids & {"PERF-06", "PERF-12"}:
        scope.append("算法/大数据量基准测试（时间复杂度）")
    if rule_ids & {"PERF-07"}:
        scope.append("首屏性能（LCP<2.5s / TTI<3.8s）")
    if rule_ids & {"PERF-08"}:
        scope.append("动画帧率（FPS≥58 / 卡顿率<1%）")
    if rule_ids & {"PERF-09"}:
        scope.append("CPU/电量/后台唤醒检测")
    if rule_ids & {"PERF-10"}:
        scope.append("文件 I/O 吞吐 + 主线程阻塞检测")
    if rule_ids & {"PERF-11"}:
        scope.append("包体积变化 + 启动耗时对比")
    if rule_ids & {"PERF-13"}:
        scope.append("并发吞吐 + 锁竞争/死锁检测")
    if rule_ids & {"PERF-14"}:
        scope.append("端到端链路时延 + 跨服务 RT")
    if rule_ids & {"PERF-15"}:
        scope.append("🔴 全链路压测 + 极限容量（建议 2~10x 峰值）")

    # 风险提示
    risks: list[str] = []
    if manual_flags.get("high_concurrency"):
        risks.append("高并发业务，需确认数据库/缓存容量")
    if rule_ids & {"PERF-04"}:
        risks.append("检测到循环内 I/O/查询，存在 N+1 放大效应")
    if rule_ids & {"PERF-11"}:
        risks.append("引入新依赖，包体积/启动耗时可能劣化")
    if rule_ids & {"PERF-12"}:
        risks.append("检测到嵌套循环/排序，复杂度可能升至 O(n²)")

    return DimensionResult(
        dimension="performance_test",
        required=required,
        priority=priority,
        triggered_rules=triggered,
        details={
            "scope": scope,
            "risks": risks,
            "baselines": {
                "api_p95_ms": 200,
                "api_p99_ms": 500,
                "api_error_rate": 0.001,
                "lcp_s": 2.5,
                "tti_s": 3.8,
                "fps_min": 58,
                "cold_start_s": 2,
                "package_size_increase_pct": 5,
            },
        },
    )


# ============================================================
# 工作量估算
# ============================================================

def estimate_effort(dims: dict[str, DimensionResult], change: CodeChange) -> dict:
    new_cases = 0
    regression_cases = 0
    special_days = 0.0

    if dims["new_feature_scope"].required:
        # 每个验收标准 ~4 条用例（正向+反向+边界+异常）
        ac_count = len(dims["new_feature_scope"].details.get("items", []))
        new_cases = max(10, ac_count * 5)

    if dims["regression_scope"].required:
        mod_count = len(dims["regression_scope"].details.get("affected_modules", []))
        regression_cases = max(10, mod_count * 8)

    if dims["compatibility_test"].required:
        matrix = dims["compatibility_test"].details.get("matrix", {})
        total_cells = sum(len(v) for v in matrix.values() if isinstance(v, list))
        special_days += max(1.0, total_cells * 0.3)

    if dims["weak_network_test"].required:
        scn = len(dims["weak_network_test"].details.get("scenarios", []))
        special_days += max(0.5, scn * 0.25)

    if dims["historical_version_test"].required:
        vers = len(dims["historical_version_test"].details.get("versions", []))
        special_days += max(0.5, vers * 0.5)

    if dims["performance_test"].required:
        scope_count = len(dims["performance_test"].details.get("scope", []))
        # 全链路压测（PERF-15）单独计 2 人日
        has_full_stress = any("全链路压测" in s for s in dims["performance_test"].details.get("scope", []))
        base_days = max(1.0, scope_count * 0.5)
        special_days += base_days + (2.0 if has_full_stress else 0)

    # 用例执行效率 ~15 条/人日
    case_days = round((new_cases + regression_cases) / 15.0, 1)
    total = round(case_days + special_days, 1)

    return {
        "new_feature_cases": new_cases,
        "regression_cases": regression_cases,
        "case_execution_days": case_days,
        "special_test_days": round(special_days, 1),
        "total_person_days": total,
    }


# ============================================================
# 报告渲染
# ============================================================

def render_markdown(requirement: dict, change: CodeChange,
                    dims: dict[str, DimensionResult], effort: dict) -> str:
    def flag(req: bool, prio: str) -> str:
        if not req:
            return "⚪ 不涉及"
        icon = {"P0": "🔴 必测", "P1": "🟠 建议测", "P2": "🟡 可选"}.get(prio, "🟡")
        return f"{icon}（{prio}）"

    title = requirement.get("title", "未命名需求")
    rid = requirement.get("id", "REQ-XXX")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append(f"# 测试策略：{title}")
    lines.append("")
    lines.append(f"> 生成时间：{now}")
    lines.append(f"> 需求ID：{rid} | 变更文件数：{len(change.changed_files)} | +{change.total_added}/-{change.total_deleted} 行")
    lines.append("")

    lines.append("## 📋 基本信息")
    lines.append(f"- 需求类型：{requirement.get('type', '未指定')}")
    lines.append(f"- 涉及模块：{', '.join(requirement.get('modules', [])) or '未指定'}")
    lines.append(f"- 涉及端：{', '.join(requirement.get('platforms', [])) or '未指定'}")
    lines.append(f"- 涉及用户分群：{', '.join(requirement.get('user_groups', [])) or '全体用户'}")
    lines.append("")

    lines.append("## 🎯 策略总览（TL;DR）")
    lines.append("| 维度 | 结论 | 优先级 | 触发规则 |")
    lines.append("|------|------|--------|----------|")
    dim_titles = {
        "new_feature_scope": "新增功能测试",
        "regression_scope": "存量功能回归",
        "compatibility_test": "兼容性测试",
        "weak_network_test": "弱网测试",
        "historical_version_test": "历史版本验证",
        "performance_test": "性能测试",
    }
    for key, name in dim_titles.items():
        d = dims[key]
        rules_str = ", ".join(t.rule_id for t in d.triggered_rules) or "-"
        lines.append(f"| {name} | {flag(d.required, d.priority)} | {d.priority} | {rules_str} |")
    lines.append("")

    # 一、新增功能
    d = dims["new_feature_scope"]
    lines.append("## 一、新增功能测试范围")
    lines.append(f"**结论：{flag(d.required, d.priority)}**")
    lines.append("")
    if d.triggered_rules:
        lines.append("### 触发规则")
        for t in d.triggered_rules:
            lines.append(f"- **{t.rule_id}** {t.description}")
            for ev in t.evidence:
                lines.append(f"  - 证据：{ev}")
        lines.append("")
    if d.details.get("items"):
        lines.append("### 新增功能清单")
        lines.append("| 功能点 | 来源 | 优先级 |")
        lines.append("|--------|------|--------|")
        for it in d.details["items"]:
            lines.append(f"| {it['point']} | {it['source']} | {it['priority']} |")
        lines.append("")
    if d.required:
        lines.append("### 测试覆盖要求")
        for tt in d.details.get("test_types", []):
            lines.append(f"- {tt}")
        lines.append("")

    # 二、存量影响
    d = dims["regression_scope"]
    lines.append("## 二、存量功能影响范围")
    lines.append(f"**结论：{flag(d.required, d.priority)}**")
    lines.append("")
    if d.triggered_rules:
        lines.append("### 触发规则")
        for t in d.triggered_rules:
            lines.append(f"- **{t.rule_id}** {t.description}")
            for ev in t.evidence:
                lines.append(f"  - 证据：{ev}")
        lines.append("")
    if d.details.get("affected_modules"):
        lines.append("### 影响模块")
        for m in d.details["affected_modules"]:
            lines.append(f"- {m}")
        lines.append("")
    if d.details.get("upstream_callers"):
        lines.append("### 上游调用方（需回归）")
        for u in d.details["upstream_callers"]:
            lines.append(f"- {u}")
        lines.append("")
    if d.details.get("shared_state"):
        lines.append("### 共享状态消费方（需回归）")
        for s in d.details["shared_state"]:
            lines.append(f"- {s}")
        lines.append("")

    # 三、兼容性
    d = dims["compatibility_test"]
    lines.append("## 三、兼容性测试决策")
    lines.append(f"**结论：{flag(d.required, d.priority)}**")
    lines.append("")
    if d.triggered_rules:
        lines.append("### 触发规则")
        for t in d.triggered_rules:
            lines.append(f"- **{t.rule_id}** {t.description}")
            for ev in t.evidence:
                lines.append(f"  - 证据：{ev}")
        lines.append("")
    if d.required and d.details.get("matrix"):
        lines.append("### 兼容性矩阵")
        lines.append("| 维度 | 覆盖范围 |")
        lines.append("|------|----------|")
        for k, v in d.details["matrix"].items():
            lines.append(f"| {k} | {', '.join(v) if isinstance(v, list) else v} |")
        lines.append("")

    # 四、弱网
    d = dims["weak_network_test"]
    lines.append("## 四、弱网测试决策")
    lines.append(f"**结论：{flag(d.required, d.priority)}**")
    lines.append("")
    if d.triggered_rules:
        lines.append("### 触发规则")
        for t in d.triggered_rules:
            lines.append(f"- **{t.rule_id}** {t.description}")
            for ev in t.evidence:
                lines.append(f"  - 证据：{ev}")
        lines.append("")
    if d.required and d.details.get("scenarios"):
        lines.append("### 弱网场景覆盖")
        for s in d.details["scenarios"]:
            lines.append(f"- {s}")
        lines.append("")

    # 五、历史版本
    d = dims["historical_version_test"]
    lines.append("## 五、历史版本验证决策")
    lines.append(f"**结论：{flag(d.required, d.priority)}**")
    lines.append("")
    if d.triggered_rules:
        lines.append("### 触发规则")
        for t in d.triggered_rules:
            lines.append(f"- **{t.rule_id}** {t.description}")
            for ev in t.evidence:
                lines.append(f"  - 证据：{ev}")
        lines.append("")
    if d.required and d.details.get("versions"):
        lines.append("### 历史版本测试范围")
        for v in d.details["versions"]:
            lines.append(f"- {v}")
        lines.append("")
    if d.details.get("data_migration"):
        lines.append("- ⚠️ **涉及数据迁移：升级前后数据一致性 + 回滚路径必测**")
        lines.append("")

    # 六、性能测试
    d = dims["performance_test"]
    lines.append("## 六、性能测试决策")
    lines.append(f"**结论：{flag(d.required, d.priority)}**")
    lines.append("")
    if d.triggered_rules:
        lines.append("### 触发规则")
        for t in d.triggered_rules:
            lines.append(f"- **{t.rule_id}** {t.description}")
            for ev in t.evidence:
                lines.append(f"  - 证据：{ev}")
        lines.append("")
    if d.required and d.details.get("scope"):
        lines.append("### 性能测试范围")
        for s in d.details["scope"]:
            lines.append(f"- {s}")
        lines.append("")
    if d.details.get("risks"):
        lines.append("### ⚠️ 性能风险")
        for r in d.details["risks"]:
            lines.append(f"- {r}")
        lines.append("")
    if d.required and d.details.get("baselines"):
        lines.append("### 性能基线（默认值，可按项目定制）")
        baselines = d.details["baselines"]
        lines.append("| 维度 | 基线/红线 |")
        lines.append("|------|-----------|")
        lines.append(f"| API P95 | < {baselines.get('api_p95_ms')}ms |")
        lines.append(f"| API P99 | < {baselines.get('api_p99_ms')}ms |")
        lines.append(f"| API 错误率 | < {baselines.get('api_error_rate', 0)*100:.1f}% |")
        lines.append(f"| 首屏 LCP | < {baselines.get('lcp_s')}s |")
        lines.append(f"| 交互 TTI | < {baselines.get('tti_s')}s |")
        lines.append(f"| 帧率 FPS | ≥ {baselines.get('fps_min')} |")
        lines.append(f"| 冷启动 | < {baselines.get('cold_start_s')}s |")
        lines.append(f"| 包体积增量 | < {baselines.get('package_size_increase_pct')}% |")
        lines.append("")

    # 工作量
    lines.append("## 📊 工作量估算")
    lines.append(f"- 新功能用例：~{effort['new_feature_cases']} 条")
    lines.append(f"- 回归用例：~{effort['regression_cases']} 条")
    lines.append(f"- 用例执行：约 {effort['case_execution_days']} 人日")
    lines.append(f"- 专项测试（兼容/弱网/历史版本/性能）：约 {effort['special_test_days']} 人日")
    lines.append(f"- **总计：{effort['total_person_days']} 人日**")
    lines.append("")

    lines.append("## 🔗 下一步")
    lines.append("- 依据本策略确定的范围，使用 `references/testcase-template.md` 生成具体测试用例")
    lines.append("- 测试用例需关联本策略 ID 以便追溯")
    return "\n".join(lines)


def dimension_to_dict(d: DimensionResult) -> dict:
    return {
        "dimension": d.dimension,
        "required": d.required,
        "priority": d.priority,
        "triggered_rules": [
            {"rule_id": t.rule_id, "description": t.description,
             "evidence": t.evidence, "severity": t.severity}
            for t in d.triggered_rules
        ],
        "details": d.details,
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Test Strategy Generator")
    parser.add_argument("--requirement", "-r", required=True, help="需求 YAML/JSON 文件")
    parser.add_argument("--repo", default=".", help="Git 仓库路径（默认当前目录）")
    parser.add_argument("--diff-from", default="HEAD~1", help="diff 起点（默认 HEAD~1）")
    parser.add_argument("--diff-to", default="HEAD", help="diff 终点（默认 HEAD）")
    parser.add_argument("--coupling", help="耦合场景 YAML/JSON 文件（可选）")
    parser.add_argument("--manual-flags", help="手动标志 YAML/JSON（breaking_change/data_migration 等）")
    parser.add_argument("--changed-files", help="直接提供变更文件清单 JSON（跳过 git diff）")
    parser.add_argument("--output-md", default="test-strategy.md", help="Markdown 输出路径")
    parser.add_argument("--output-json", default="test-strategy.json", help="JSON 输出路径")
    args = parser.parse_args()

    # 加载输入
    requirement = load_yaml_or_json(args.requirement)
    if not requirement:
        print(f"[ERROR] 需求文件无法解析：{args.requirement}", file=sys.stderr)
        sys.exit(1)

    coupling = load_yaml_or_json(args.coupling) if args.coupling else {}
    manual_flags = load_yaml_or_json(args.manual_flags) if args.manual_flags else {}

    # 代码变更
    if args.changed_files:
        data = load_yaml_or_json(args.changed_files)
        change = CodeChange()
        for f in data.get("files", data if isinstance(data, list) else []):
            change.changed_files.append(f)
            change.total_added += f.get("added", 0)
            change.total_deleted += f.get("deleted", 0)
            path = f.get("path", "")
            mod = "/".join(path.split("/")[:2])
            if mod:
                change.changed_modules.add(mod)
            lower = path.lower()
            if re.search(r"\.(swift|m|mm|java|kt|cpp|c|h)$", lower):
                change.has_native = True
            if "migration" in lower or "schema" in lower or lower.endswith(".sql"):
                change.has_db_schema = True
        diff_text = ""
    else:
        change = collect_git_diff(args.repo, args.diff_from, args.diff_to)
        diff_text = get_diff_content(args.repo, args.diff_from, args.diff_to)

    # 五维决策
    dims = {
        "new_feature_scope": decide_new_feature(requirement, change, diff_text),
        "regression_scope": decide_regression(requirement, change, diff_text, coupling),
        "compatibility_test": decide_compatibility(requirement, change, diff_text),
        "weak_network_test": decide_weak_network(requirement, change, diff_text),
        "historical_version_test": decide_historical_version(requirement, change, diff_text, manual_flags),
        "performance_test": decide_performance(requirement, change, diff_text, manual_flags),
    }

    # 工作量
    effort = estimate_effort(dims, change)

    # 渲染 Markdown
    md_content = render_markdown(requirement, change, dims, effort)
    with open(args.output_md, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 渲染 JSON
    json_content = {
        "strategy_id": f"STRAT-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "requirement_id": requirement.get("id"),
        "generated_at": datetime.now().isoformat(),
        "inputs": {
            "requirement": requirement,
            "code_change_summary": {
                "files_count": len(change.changed_files),
                "total_added": change.total_added,
                "total_deleted": change.total_deleted,
                "changed_modules": list(change.changed_modules),
                "has_native": change.has_native,
                "has_db_schema": change.has_db_schema,
            },
            "coupling": coupling,
        },
        "dimensions": {k: dimension_to_dict(v) for k, v in dims.items()},
        "effort_estimation": effort,
    }
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(json_content, f, ensure_ascii=False, indent=2)

    print(f"[OK] 测试策略已生成：")
    print(f"  - Markdown: {args.output_md}")
    print(f"  - JSON:     {args.output_json}")
    print(f"  - 工作量估算：{effort['total_person_days']} 人日")


if __name__ == "__main__":
    main()
