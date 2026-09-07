#!/usr/bin/env python3
"""
agentic-coding-analysis-d1 快速运行脚本
基于 agentic-coding-analysis/run_trace_generation_plus.py 设计
适配 claude-code-proxy-p1 数据源

用法:
    python3 run_d1.py
"""
import os, sys, re, subprocess, glob, json
from pathlib import Path
from datetime import datetime

# ============================================================
# *** CONFIG: 配置参数 ***
# ============================================================
AGENTIC_DIR = "/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1"
DB          = "/mnt/nvme1n1/data/lmk/PROJECT/tmp/claude-code-proxy-p1/requests.db"

# JSONL 目录扫描根路径
JSONL_ROOT  = "/home/ai_lab/.claude/projects"

# 目录过滤（留空 = 不过滤）
JSONL_FILTER  = ["claude-code-proxy-p1"]  # 只处理 proxy-p1 的数据
JSONL_EXCLUDE = []

# 时间过滤（留空 = 不过滤）
TIME_AFTER  = ""
TIME_BEFORE = ""

# 输出路径
OUT_ROOT = "/mnt/nvme1n1/data/lmk/PROJECT/traces-d1"
LOG_DIR  = "/mnt/nvme1n1/data/lmk/PROJECT/logs-d1"

# trace 生成参数
BLOCK_SIZE       = 64
MIN_REQUESTS     = 1
INCLUDE_SUBAGENTS = True
INCLUDE_STREAMING = True
SPLIT_GAP        = None
DO_VALIDATE      = False  # 关闭验证以加快速度
LOCAL_HASH_IDS   = False   # True=local模式(每个会话独立), False=global模式(跨会话共享)

# 数据库时间过滤（根据 proxy-p1 的实际数据调整）
DB_START_TIME = "2026-09-06 02:00:00"
DB_END_TIME   = "2026-09-06 04:00:00"

# tiktoken 缓存
TIKTOKEN_CACHE_DIR = "/tmp/tiktoken-cache-d1"

# Python 解释器（使用虚拟环境）
PYTHON = os.path.join(AGENTIC_DIR, ".venv/bin/python3")
# ============================================================


def discover_jsonl_dirs(root, include=(), exclude=()):
    """扫描 root 的一级子目录，返回含 *.jsonl 的目录列表"""
    if not os.path.isdir(root):
        print(f"❌ JSONL_ROOT 不存在: {root}")
        return []
    dirs = []
    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if not os.path.isdir(full):
            continue
        if not glob.glob(os.path.join(full, "*.jsonl")):
            continue
        if include and not any(k in entry for k in include):
            continue
        if exclude and any(k in entry for k in exclude):
            continue
        dirs.append(full)
    return dirs


def get_folder_created_time(path):
    """返回目录创建时间"""
    try:
        out = subprocess.run(["stat", "-c", "%W|%Z", path],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        b_s, c_s = out.split("|")
        def dt(s):
            try:
                return datetime.fromtimestamp(int(s))
            except (ValueError, OSError):
                return None
        b = dt(b_s) if b_s not in ("0", "-") else None
        c = dt(c_s)
        if b is not None and c is not None and abs((b - c).total_seconds()) < 1:
            b = None
        return b if b is not None else c
    except Exception:
        return None


def parse_time(s):
    """解析时间字符串"""
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).strip().replace("/", "-"))
    except ValueError:
        print(f"⚠️ 无法解析时间: {s!r}")
        return None


def filter_by_created(dirs, after="", before=""):
    """按创建时间过滤目录"""
    a = parse_time(after)
    b = parse_time(before)
    kept = []
    for d in dirs:
        t = get_folder_created_time(d)
        if t is None:
            print(f"  (⚠️ 取不到创建时间, 保留) {d}")
            kept.append(d)
            continue
        if a is not None and t < a:
            print(f"  (跳过 创建 {t:%Y-%m-%d %H:%M} < {a:%Y-%m-%d %H:%M}) {d}")
            continue
        if b is not None and t > b:
            print(f"  (跳过 创建 {t:%Y-%m-%d %H:%M} > {b:%Y-%m-%d %H:%M}) {d}")
            continue
        kept.append(d)
    return kept


def sh(cmd, timeout=None):
    """执行 shell 命令"""
    print(f"\n>>> {cmd[:120]}")
    try:
        env = os.environ.copy()
        env["TIKTOKEN_CACHE_DIR"] = TIKTOKEN_CACHE_DIR
        r = subprocess.run(cmd, shell=True, cwd=AGENTIC_DIR,
                           capture_output=True, text=True, timeout=timeout,
                           env=env)
    except subprocess.TimeoutExpired:
        print(f"   ! 超时({timeout}s)")
        return False, ""
    out = (r.stdout or "").strip()
    if out: print(out)
    if r.stderr and r.stderr.strip():
        err = r.stderr.strip()
        if len(err) > 500:
            print(f"[stderr] {err[:500]}...")
        else:
            print(f"[stderr] {err}")
    return r.returncode == 0, out


def main():
    # 检查虚拟环境
    if not os.path.exists(PYTHON):
        print(f"❌ 虚拟环境不存在: {PYTHON}")
        print("请先运行: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt")
        sys.exit(1)

    # 生成时间戳
    run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR = os.path.join(OUT_ROOT, f"traces-{run_tag}") if OUT_ROOT else None
    LOG_FILE = os.path.join(LOG_DIR, f"run_{run_tag}.log") if LOG_DIR else ""

    # 发现 JSONL 目录
    JSONL_DIRS = discover_jsonl_dirs(JSONL_ROOT, JSONL_FILTER, JSONL_EXCLUDE)

    # 时间过滤
    if TIME_AFTER or TIME_BEFORE:
        print(f"\n按创建时间过滤: after={TIME_AFTER or '-'}  before={TIME_BEFORE or '-'}")
        JSONL_DIRS = filter_by_created(JSONL_DIRS, TIME_AFTER, TIME_BEFORE)
        print(f"  过滤后剩 {len(JSONL_DIRS)} 个目录")

    # 前置检查
    if not os.path.exists(DB):
        print(f"❌ 找不到数据库: {DB}")
        sys.exit(1)
    if not JSONL_DIRS:
        print(f"❌ 在 {JSONL_ROOT} 下没找到匹配的 JSONL 目录")
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TIKTOKEN_CACHE_DIR, exist_ok=True)

    # 日志记录
    if LOG_FILE:
        class _Tee:
            def __init__(self, *files):
                self.files = files
            def write(self, s):
                for f in self.files:
                    f.write(s)
            def flush(self):
                for f in self.files:
                    if hasattr(f, "flush"):
                        f.flush()
        os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)
        sys.stdout = _Tee(sys.stdout, open(LOG_FILE, "a", encoding="utf-8"))
        print(f"\n📝 日志: {LOG_FILE}")

    print("=" * 70)
    print("agentic-coding-analysis-d1 - Trace 生成")
    print(f"  DB     : {DB}")
    print(f"  JSONL  : {JSONL_ROOT}")
    print(f"  发现   : {len(JSONL_DIRS)} 个目录")
    for jd in JSONL_DIRS:
        print(f"            - {os.path.basename(jd)}")
    print(f"  输出   : {OUT_DIR}")
    print("=" * 70)

    # Step 1: 提取 message id
    print("\n=== Step 1: 提取 message IDs ===")
    ok1, out1 = sh(f'{PYTHON} build_message_index.py "{DB}"')
    if not ok1:
        print("❌ Step 1 失败")
        sys.exit(1)
    m1 = re.search(r"Extracted ([\d,]+) unique message IDs", out1)
    n_ids = int(m1.group(1).replace(",", "")) if m1 else 0
    print(f"  ✅ 提取 {n_ids} 个 message id")

    # Step 2: 会话关联
    print("\n=== Step 2: 会话关联 ===")
    mapped_total = 0
    for jd in JSONL_DIRS:
        ok2, out2 = sh(f'{PYTHON} build_conversation_index.py "{DB}" --projects-path "{jd}"')
        m2 = re.search(r"Mapped to requests\.db:\s*(\d+)", out2)
        mapped = int(m2.group(1)) if m2 else 0
        mapped_total += mapped
        print(f"  [{os.path.basename(jd)}] 关联: {mapped} 条")

    if mapped_total <= 0:
        print("  ⚠️ 无关联数据，继续...")

    # Step 3: 生成 trace
    print("\n=== Step 3: 生成 trace 文件 ===")
    extra = f"--block-size {BLOCK_SIZE} --min-requests {MIN_REQUESTS}"
    if INCLUDE_SUBAGENTS:
        extra += " --include-subagents"
    if LOCAL_HASH_IDS:
        extra += " --local-hash-ids"
    # 注意：此版本 build_minimal_traces.py 不支持 --include-streaming, --start-time, --end-time
    # 如需这些功能，请使用 agentic-coding-analysis 版本的脚本

    new = []
    for jd in JSONL_DIRS:
        ok3, out3 = sh(f'{PYTHON} build_minimal_traces.py '
                       f'--jsonl-dir "{jd}" --output-dir "{OUT_DIR}" {extra} "{DB}"')
        for f in glob.glob(os.path.join(OUT_DIR, "*.json")):
            if f not in new:
                new.append(f)

    print(f"\n  生成 {len(new)} 个 trace 文件:")
    if not new:
        print("  ❌ 未生成任何 trace")
        sys.exit(1)

    for f in new:
        try:
            d = json.load(open(f))
            reqs = len(d.get('requests', []))
            block = d.get('block_size')
            scope = d.get('hash_id_scope')
            print(f"    - {os.path.basename(f)}  (requests={reqs}, block={block}, scope={scope})")
        except Exception:
            print(f"    - {os.path.basename(f)}  ({os.path.getsize(f)} bytes)")

    # Step 4: 验证（可选）
    if DO_VALIDATE:
        print("\n=== Step 4: 验证 trace ===")
        for t in new:
            tid = os.path.basename(t)
            src_dir = JSONL_DIRS[0]
            for jd in JSONL_DIRS:
                if any(Path(p).stem.startswith(tid.split('.')[0][:12])
                       or tid.split('.')[0].startswith(Path(p).stem[:12])
                       for p in glob.glob(os.path.join(jd, "*.jsonl"))):
                    src_dir = jd
                    break
            sh(f'{PYTHON} validate_trace_cache.py "{t}" --db "{DB}" --jsonl-dir "{src_dir}"')

    print("\n" + "=" * 70)
    print(f"✅ 完成！输出目录: {OUT_DIR}")
    if LOG_FILE:
        print(f"📝 日志文件: {LOG_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
