#!/usr/bin/env python3
"""
Document Organizer CLI
功能：按 config.yaml 的规则整理指定目录下的文件（移动或复制）
支持 dry-run、undo（基于日志）
"""
import argparse
import shutil
import sys
import yaml
import hashlib
from pathlib import Path
from datetime import datetime
import logging
import json
import re

LOGFILE = Path(".organize_history.jsonl")

logging.basicConfig(level=logging.INFO, format="%(message)s")


def load_config(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def safe_move(src: Path, dest: Path, move_or_copy="move"):
    dest.parent.mkdir(parents=True, exist_ok=True)
    base = dest
    if dest.exists():
        # avoid overwrite — add suffix
        i = 1
        while True:
            candidate = dest.with_name(f"{dest.stem}__{i}{dest.suffix}")
            if not candidate.exists():
                dest = candidate
                break
            i += 1
    if move_or_copy == "copy":
        shutil.copy2(src, dest)
    else:
        shutil.move(str(src), str(dest))
    return dest


def file_date_component(p: Path, which="mtime"):
    stat = p.stat()
    if which == "ctime":
        t = stat.st_ctime
    else:
        t = stat.st_mtime
    dt = datetime.fromtimestamp(t)
    return dt.year, dt.month


def matches_any_pattern(name: str, patterns):
    for pat in patterns or []:
        if re.search(pat, name):
            return True
    return False


def compute_sha1(p: Path):
    h = hashlib.sha1()
    with p.open("rb") as f:
        while True:
            b = f.read(8192)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def record_action(entry: dict):
    with LOGFILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def undo_last():
    if not LOGFILE.exists():
        logging.error("没有历史记录文件，无法撤销。")
        return
    # 读取最后一条 JSONL 记录
    lines = LOGFILE.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        logging.error("历史记录为空，无法撤销。")
        return
    last = json.loads(lines[-1])
    actions = last.get("actions", [])
    # 尝试逆序恢复
    for a in reversed(actions):
        try:
            src = Path(a["dest"])
            orig = Path(a["src"])
            if src.exists():
                orig.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(orig))
                logging.info(f"已撤销：{src} -> {orig}")
            else:
                logging.warning(f"目标不存在，跳过：{src}")
        except Exception as e:
            logging.error(f"撤销时出错：{e}")
    # truncate last line
    with LOGFILE.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines[:-1]) + ("\n" if len(lines) > 1 else ""))


def main():
    ap = argparse.ArgumentParser(description="Document Organizer")
    ap.add_argument("--config", "-c", required=False, default="config.yaml", help="配置文件路径")
    ap.add_argument("--src", "-s", required=False, default=".", help="要整理的源目录")
    ap.add_argument("--dry-run", action="store_true", help="只模拟，不做实际移动")
    ap.add_argument("--undo", action="store_true", help="撤销最后一次整理")
    args = ap.parse_args()

    if args.undo:
        undo_last()
        sys.exit(0)

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        logging.error(f"未找到配置文件：{cfg_path}")
        sys.exit(1)
    cfg = load_config(cfg_path)

    src_root = Path(args.src).expanduser().resolve()
    if not src_root.exists() or not src_root.is_dir():
        logging.error(f"源目录无效：{src_root}")
        sys.exit(1)

    move_or_copy = cfg.get("move_or_copy", "move")
    ignore_patterns = cfg.get("ignore_patterns", [])
    ext_map = cfg.get("extension_map", {})
    tag_rules = cfg.get("tag_rules", [])
    date_archive = cfg.get("date_archive", {}).get("enabled", False)
    date_field = cfg.get("date_archive", {}).get("field", "mtime")
    archive_root = cfg.get("date_archive", {}).get("archive_root", "Archive")

    actions = []
    logging.info(f"开始扫描：{src_root}")
    for p in src_root.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(src_root)
        name = str(rel)
        # skip hidden files or matches ignore
        if any(part.startswith(".") for part in rel.parts):
            continue
        if matches_any_pattern(name, ignore_patterns):
            logging.debug(f"忽略：{name}")
            continue

        target_sub = None
        lower_suf = p.suffix.lower().lstrip(".")
        # extension map
        if lower_suf in ext_map:
            target_sub = ext_map[lower_suf]
        # tag rules (list of dicts with 'pattern' and 'dest')
        if not target_sub and tag_rules:
            for tr in tag_rules:
                patt = tr.get("pattern")
                dest = tr.get("dest")
                flags = tr.get("flags", "")
                try:
                    if re.search(patt, p.name, flags=re.IGNORECASE if "i" in flags else 0):
                        target_sub = dest
                        break
                except re.error:
                    # treat patt as substring
                    if patt.lower() in p.name.lower():
                        target_sub = dest
                        break
        # date archive
        if not target_sub and date_archive:
            y, m = file_date_component(p, which=date_field)
            target_sub = str(Path(archive_root) / f"{y}" / f"{m:02d}")

        # default fallback
        if not target_sub:
            target_sub = cfg.get("default_dest", "Other")

        dest_path = src_root / target_sub / p.name
        if args.dry_run:
            logging.info(f"[DRY] {p} -> {dest_path}")
            actions.append({"src": str(p), "dest": str(dest_path), "sha1": compute_sha1(p)})
        else:
            try:
                real_dest = safe_move(p, dest_path, move_or_copy=move_or_copy)
                logging.info(f"{p} -> {real_dest}")
                actions.append({"src": str(p), "dest": str(real_dest), "sha1": compute_sha1(real_dest)})
            except Exception as e:
                logging.error(f"移动失败 {p} -> {dest_path} : {e}")

    # record actions
    meta = {
        "timestamp": datetime.now().isoformat(),
        "src_root": str(src_root),
        "config": str(cfg_path),
        "move_or_copy": move_or_copy,
        "dry_run": bool(args.dry_run),
        "actions": actions,
    }
    record_action(meta)
    logging.info("整理完成。历史已记录。")


if __name__ == "__main__":
    main()
