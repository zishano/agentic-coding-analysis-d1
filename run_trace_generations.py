#!/usr/bin/env python3
"""
agentic-coding-analysis 一键执行脚本 —— JSONL 目录自动发现版
============================================================
从 requests.db 生成带 hash_ids 的 trace 四步流程，封装成一次命令。
区别：JSONL_DIRS 不再手动枚举，而是【自动扫描指定根目录下的一级子目录】
     (每个一级子目录 = 一个 Claude Code 会话/项目的 jsonl 目录)。

用法:
    python3 run_trace_generation_auto.py
"""
import os, sys, re, subprocess, glob, json
from pathlib import Path
from datetime import datetime

# ============================================================
# *** CONFIG: 你要改的参数 ***
# ============================================================
AGENTIC_DIR = "/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1"
# DB          = "/home/lmk/claude-code-proxy/requests.db"
DB         = "/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/requests_20260828.db"

# JSONL 的一级目录的【父目录】：脚本会自动收集它下面所有直接子目录中“含 *.jsonl”的目录
JSONL_ROOT  = "/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/projects"

# 可选过滤(都是一级目录名的子串关键字，用文件名匹配)：
#   JSONL_FILTER  : 只保留名字里含这些关键字的目录 (空列表=全部保留)
#   JSONL_EXCLUDE : 剔除名字里含这些关键字的目录 (空=不剔除)
#   先按 FILTER 白名单，再按 EXCLUDE 黑名单。
#   ⚠️ 注意: 目标会话目录名不含 "candidates", 若设了该关键字会一个目录都选不中。
#   这里留空=全部保留, 由下面 DB_START_TIME/DB_END_TIME 精确筛出能匹配 db 的会话。
JSONL_FILTER  = []                    # 例: ["candidates", "integration"]  只收这类
JSONL_EXCLUDE = []                    # 例: ["worktrees", "product-repo"]  不要这类

# 按目录【创建时间】过滤(可选)。格式 "YYYY-MM-DD HH:MM" 或 "YYYY-MM-DD HH:MM:SS"
#   TIME_AFTER  : 只保留 创建时间 >= 该时刻 的目录 (左闭)
#   TIME_BEFORE : 只保留 创建时间 <= 该时刻 的目录 (右闭)
#   留空 "" = 不过滤。例如只想要 2026-08-25 12:00 之后创建的:
#       TIME_AFTER = "2026-08-25 12:00:00"
#   创建时间取 filesystem 的 birth(不可用则退回 ctime)。
#   ⚠️ 注意: 这是按【目录创建时间】过滤, 不代表里面会话的时间; 这里关掉,
#            改用 DB_START_TIME/DB_END_TIME 按 db 请求时间精确筛选。
TIME_AFTER  = ""        # 例: "2026-08-25 12:00:00"
TIME_BEFORE = ""        # 例: "2026-08-25 23:59:59"

# 输出/日志都按运行时间戳命名，每次运行生成一份独立结果与日志。
OUT_ROOT = "/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/traces-d1"    # 每次运行生成其下 traces-<时间戳>/ 子目录
LOG_DIR  = "/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/logs-d1"           # 日志目录(留空 "" = 不保留日志)，文件 run_<时间戳>.log

# trace 生成参数
BLOCK_SIZE       = 64        # prompt 分块大小
MIN_REQUESTS     = 1         # 至少多少个请求才生成一个 trace
INCLUDE_SUBAGENTS = True     # 是否包含子代理 (True/False)
INCLUDE_STREAMING = True     # 是否额外纳入 DB 流式请求(stream=true),让 trace 含 type=s 和 type=n
SPLIT_GAP        = None       # 长会话按 N 秒切分; None=不切
DO_VALIDATE      = True       # 是否跑 Step4 validate
USE_LOCAL_HASH_IDS = True    # hash_id 范围: True=local(每会话独立), False=global(跨会话共享)

# 按 requests.db 的请求 timestamp【过滤】参与 trace 的请求(可选)。
#   留空 "" = 不过滤; 填了就只取时间窗口内的请求:
#       DB_START_TIME : 请求 timestamp >= 该时刻
#       DB_END_TIME   : 请求 timestamp <= 该时刻
#   格式 "YYYY-MM-DD HH:MM:SS" 或带时区 "YYYY-MM-DDTHH:MM:SS+08:00"。
#   不带时区时按本机/数据库本地时间理解(+08:00, 与 requests.timestamp 一致)。
#
#   当前 requests.db 中能匹配到本地 JSONL 会话的请求集中在 2026-08-27 16:26:47 ~ 16:46:26 (+08:00),
#   对应 4 个会话:
#       b7212bbf : 16:26:47 ~ 16:35:39 (14 请求)
#       ddf3fe2b : 16:37:02 ~ 16:39:02 (7  请求)
#       36ee6351 : 16:39:59 ~ 16:42:44 (8  请求)
#       1df9106c : 16:43:12 ~ 16:46:26 (8  请求)
#   下方窗口带余量覆盖以上全部; 若只想要其中某段, 按需改窄即可。
DB_START_TIME = ""        # 例: "2026-08-27 00:00:00"
DB_END_TIME   = ""        # 例: "2026-08-27 23:59:59"

# tiktoken 编码缓存(绕过网络下载被墙)
TIKTOKEN_CACHE_DIR = "/tmp/tiktoken-cache"
# ============================================================


def discover_jsonl_dirs(root, include=(), exclude=()):
    """扫描 root 的一级子目录，返回其中“直接含 *.jsonl”的目录列表(自动排序)。
    保留与手动列表一致的稳定顺序；只有真正含 .jsonl 的才算，避免空目录。
    """
    if not os.path.isdir(root):
        print(f"❌ JSONL_ROOT 不存在: {root}")
        return []
    dirs = []
    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if not os.path.isdir(full):
            continue
        # 必须直接含 *.jsonl 才作为一个 jsonl 目录
        if not glob.glob(os.path.join(full, "*.jsonl")):
            continue
        if include and not any(k in entry for k in include):
            continue
        if exclude and any(k in entry for k in exclude):
            continue
        dirs.append(full)
    return dirs


def get_folder_created_time(path):
    """返回目录创建时间(datetime)。优先 filesystem 的 birth(%W)，不可用退回 ctime(%Z)。失败返回 None"""
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
        # birth 与 ctime 几乎重合 => FS 没有真实 birth，视为不可用
        if b is not None and c is not None and abs((b - c).total_seconds()) < 1:
            b = None
        return b if b is not None else c
    except Exception:
        return None


def parse_time(s):
    """把 "YYYY-MM-DD HH:MM[:SS]" 解析为 datetime；含 '/' 也兼容；解析失败返回 None"""
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).strip().replace("/", "-"))
    except ValueError:
        print(f"⚠️ 无法解析时间过滤值: {s!r} (应为 YYYY-MM-DD HH:MM:SS)")
        return None


def filter_by_created(dirs, after="", before=""):
    """按目录创建时间过滤：保留 after <= 创建时间 <= before 的目录。
    取不到创建时间的目录默认保留(不误杀)，同时打印提示。
    """
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
    print(f"\n>>> {cmd[:100]}")
    try:
        r = subprocess.run(cmd, shell=True, cwd=AGENTIC_DIR,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"   ! 超时({timeout}s)")
        return False, ""
    out = (r.stdout or "").strip()
    if out: print(out)
    if r.stderr and r.stderr.strip():
        print("[stderr]", r.stderr.strip()[0:400])
    return True, out


def main():
    # 按运行时间戳生成本次的 输出目录 与 日志文件（每次运行各自独立一份）
    run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR = os.path.join(OUT_ROOT, f"traces-{run_tag}") if OUT_ROOT else OUT_ROOT
    LOG_FILE = os.path.join(LOG_DIR, f"run_{run_tag}.log") if LOG_DIR else ""

    # 自动收集 JSONL 目录（替换原来的手动列表）
    JSONL_DIRS = discover_jsonl_dirs(JSONL_ROOT, JSONL_FILTER, JSONL_EXCLUDE)

    # 按目录创建时间过滤（可选）
    if TIME_AFTER or TIME_BEFORE:
        print(f"\n按创建时间过滤: after={TIME_AFTER or '-'}  before={TIME_BEFORE or '-'}")
        JSONL_DIRS = filter_by_created(JSONL_DIRS, TIME_AFTER, TIME_BEFORE)
        print(f"  过滤后剩 {len(JSONL_DIRS)} 个 jsonl 目录")


    # 前置检查
    if not os.path.exists(DB):
        print(f"❌ 找不到 requests.db: {DB}"); sys.exit(1)
    if not JSONL_DIRS:
        print(f"❌ 在 {JSONL_ROOT} 下没发现任何含 *.jsonl 的一级目录(检查 JSONL_ROOT/过滤)"); sys.exit(1)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.environ["TIKTOKEN_CACHE_DIR"] = TIKTOKEN_CACHE_DIR

    # ---- 保留日志：把后续所有输出同时写进 LOG_FILE(终端照常显示) ----
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
        print(f"\n📝 本次运行日志将保留到: {LOG_FILE}")
    else:
        print("\n(LOG_FILE 为空, 不保留日志; 如需保留请设置 LOG_FILE)")

    print("=" * 66)
    print("agentic-coding-analysis 一键生成 trace  (JSONL 自动发现版)")
    print(f"  DB     : {DB}")
    print(f"  ROOT   : {JSONL_ROOT}")
    print(f"  发现 {len(JSONL_DIRS)} 个 jsonl 目录:")
    for jd in JSONL_DIRS:
        print(f"            - {jd}")
    print(f"  OUT    : {OUT_DIR}")
    print("=" * 66)

    # ---- Step1: 提取 message id ----
    print("\n=== Step1: build_message_index ===")
    ok1, out1 = sh(f'python3 build_message_index.py "{DB}"')
    m1 = re.search(r"Extracted ([\d,]+) unique message IDs", out1)
    n_ids = int(m1.group(1).replace(",", "")) if m1 else 0
    if not n_ids:
        print("❌ 提取 0 个 message id —— 检查是否跑过 collect、以及 db 有无走代理请求")
        sys.exit(1)
    print(f"\n    ✅ 提取 {n_ids} 个 message id")

    # ---- Step2: 会话关联（每个 JSONL 目录各跑一次；该表仅供信息，Step3 不依赖它）----
    print("\n>>> [Step2] build_conversation_index ===")
    mapped_total = 0
    for jd in JSONL_DIRS:
        ok2, out2 = sh(f'python3 build_conversation_index.py "{DB}" --projects-path "{jd}"')
        m2 = re.search(r"Mapped to requests\.db:\s*(\d+)", out2)
        mapped = int(m2.group(1)) if m2 else 0
        mapped_total += mapped
        print(f"\n    [{jd}] 关联到 requests.db: {mapped} 条")
    if mapped_total <= 0:
        print("    ⚠️ 0 关联 —— 这些 jsonl 可能不是走代理采集的;仍继续 trace(可能为空)。")

    # ---- Step3: 生成 trace（每个 JSONL 目录各跑一次，trace 累积到 OUT_DIR）----
    print("\n>>> [Step3] build_minimal_traces ===")
    extra = f"--block-size {BLOCK_SIZE} --min-requests {MIN_REQUESTS}"
    if INCLUDE_SUBAGENTS:
        extra += " --include-subagents"
    if SPLIT_GAP:
        extra += f" --split-at-gap {SPLIT_GAP}"
    if DB_START_TIME:
        extra += f' --start-time "{DB_START_TIME}"'
    if DB_END_TIME:
        extra += f' --end-time "{DB_END_TIME}"'
    if USE_LOCAL_HASH_IDS:
        extra += " --local-hash-ids"
    new = []
    for jd in JSONL_DIRS:
        ok3, out3 = sh(f'python3 build_minimal_traces.py "{DB}" '
                       f'--jsonl-dir "{jd}" --output-dir "{OUT_DIR}" {extra}')
        for f in glob.glob(os.path.join(OUT_DIR, "*.json")):
            if f not in new:
                new.append(f)
    print(f"\n    生成 trace 文件: {len(new)} 个")
    if not new:
        print("    ❌ 未生成任何 trace —— 检查: 这些 jsonl 目录是否匹配 db 的会话;按 Ctrl+C 看日志")
        sys.exit(1)
    for f in new:
        try:
            d = json.load(open(f))
            print(f"      - {os.path.basename(f)}  requests={len(d.get('requests',[]))}  block={d.get('block_size')}  scope={d.get('hash_id_scope')}")
        except Exception:
            print(f"      - {os.path.basename(f)}  ({os.path.getsize(f)}B)")

    # ---- Step4: validate(可选，每个 trace 用其来源 jsonl 目录比对)----
    if DO_VALIDATE:
        print("\n>>> [Step4] validate_trace_cache(每个 trace) ===")
        for t in new:
            tid = os.path.basename(t)
            src_dir = JSONL_DIRS[0]
            for jd in JSONL_DIRS:
                if any(Path(p).stem.startswith(tid.split('.')[0][:12])
                       or tid.split('.')[0].startswith(Path(p).stem[:12])
                       for p in glob.glob(os.path.join(jd, "*.jsonl"))):
                    src_dir = jd
                    break
            sh(f'python3 validate_trace_cache.py "{t}" --db "{DB}" --jsonl-dir "{src_dir}"')

    print("\n✅ 全部完成。trace 在:", OUT_DIR)


if __name__ == "__main__":
    main()
