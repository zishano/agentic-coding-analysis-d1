#!/bin/bash
# agentic-coding-analysis 一键执行脚本
# 从 requests.db 生成带 hash_ids 的 trace 四步流程
#
# 用法:
#   ./run_trace_generations.sh [OPTIONS]
#
# 选项:
#   --db PATH              requests.db 路径
#   --jsonl-root PATH      JSONL 目录根路径
#   --out-root PATH        输出根目录
#   --log-dir PATH         日志目录
#   --start-time TIME      开始时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00)
#   --end-time TIME        结束时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00)
#   --block-size N         prompt 分块大小 (默认: 64)
#   --min-requests N       最小请求数 (默认: 1)
#   --include-subagents    包含子代理 (默认: true)
#   --no-subagents         不包含子代理
#   --local-hash-ids       使用 local hash_ids (默认: true)
#   --global-hash-ids      使用 global hash_ids
#   --no-validate          跳过验证步骤
#   --help                 显示帮助信息
#
# 示例:
#   # 使用默认配置
#   ./run_trace_generations.sh
#
#   # 指定数据库和时间范围
#   ./run_trace_generations.sh \
#       --db /path/to/requests.db \
#       --start-time "2026-08-28T11:00:00+08:00" \
#       --end-time "2026-08-28T13:00:00+08:00"
#
#   # 完整配置
#   ./run_trace_generations.sh \
#       --db /path/to/requests.db \
#       --jsonl-root /path/to/projects \
#       --out-root /path/to/traces-d1 \
#       --log-dir /path/to/logs-d1 \
#       --start-time "2026-08-28T11:00:00+08:00" \
#       --end-time "2026-08-28T13:00:00+08:00" \
#       --block-size 64 \
#       --include-subagents \
#       --local-hash-ids

set -e

# 获取脚本所在目录的父目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================================
# *** 配置区域：根据你的实际路径修改 ***
# ============================================================
DEFAULT_DB="$PROJECT_DIR/tmp/exported_requests.db"
DEFAULT_JSONL_ROOT="$PROJECT_DIR/tmp/projects"
DEFAULT_OUT_ROOT="$PROJECT_DIR/traces-d1"
DEFAULT_LOG_DIR="$PROJECT_DIR/logs-d1"
DEFAULT_START_TIME="2026-09-07T17:00:00+08:00"  # 例: "2026-08-28T11:00:00+08:00"
DEFAULT_END_TIME="2026-09-08T01:00:00+08:00"    # 例: "2026-08-28T13:00:00+08:00"
DEFAULT_BLOCK_SIZE=64
DEFAULT_MIN_REQUESTS=1
DEFAULT_INCLUDE_SUBAGENTS="true"
DEFAULT_USE_LOCAL_HASH_IDS="true"
DEFAULT_DO_VALIDATE="true"
# ============================================================

# 初始化变量
DB=""
JSONL_ROOT=""
OUT_ROOT=""
LOG_DIR=""
START_TIME=""
END_TIME=""
BLOCK_SIZE=""
MIN_REQUESTS=""
INCLUDE_SUBAGENTS=""
USE_LOCAL_HASH_IDS=""
DO_VALIDATE=""

# 显示帮助
show_help() {
    cat << EOF
agentic-coding-analysis 一键生成 trace

用法:
  $0 [OPTIONS]

选项:
  --db PATH              requests.db 路径
  --jsonl-root PATH      JSONL 目录根路径
  --out-root PATH        输出根目录
  --log-dir PATH         日志目录
  --start-time TIME      开始时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00)
  --end-time TIME        结束时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00)
  --block-size N         prompt 分块大小 (默认: 64)
  --min-requests N       最小请求数 (默认: 1)
  --include-subagents    包含子代理 (默认: true)
  --no-subagents         不包含子代理
  --local-hash-ids       使用 local hash_ids (默认: true)
  --global-hash-ids      使用 global hash_ids
  --no-validate          跳过验证步骤
  --help, -h             显示此帮助信息

默认配置:
  DB              : $DEFAULT_DB
  JSONL_ROOT      : $DEFAULT_JSONL_ROOT
  OUT_ROOT        : $DEFAULT_OUT_ROOT
  LOG_DIR         : $DEFAULT_LOG_DIR
  START_TIME      : ${DEFAULT_START_TIME:-<不限>}
  END_TIME        : ${DEFAULT_END_TIME:-<不限>}
  BLOCK_SIZE      : $DEFAULT_BLOCK_SIZE
  MIN_REQUESTS    : $DEFAULT_MIN_REQUESTS
  INCLUDE_SUBAGENTS: $DEFAULT_INCLUDE_SUBAGENTS
  USE_LOCAL_HASH_IDS: $DEFAULT_USE_LOCAL_HASH_IDS
  DO_VALIDATE     : $DEFAULT_DO_VALIDATE

流程:
  Step 1: build_message_index - 从 DB 提取 message IDs
  Step 2: build_conversation_index - 建立会话关联索引
  Step 3: build_minimal_traces - 生成 trace 文件
  Step 4: validate_trace_cache - 验证 trace 缓存

示例:
  # 使用默认配置
  $0

  # 指定数据库和时间范围
  $0 --db /path/to/requests.db \\
     --start-time "2026-08-28T11:00:00+08:00" \\
     --end-time "2026-08-28T13:00:00+08:00"

  # 完整配置
  $0 --db /path/to/requests.db \\
     --jsonl-root /path/to/projects \\
     --out-root /path/to/traces-d1 \\
     --start-time "2026-08-28T11:00:00+08:00" \\
     --include-subagents \\
     --local-hash-ids
EOF
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --db)
            DB="$2"
            shift 2
            ;;
        --jsonl-root)
            JSONL_ROOT="$2"
            shift 2
            ;;
        --out-root)
            OUT_ROOT="$2"
            shift 2
            ;;
        --log-dir)
            LOG_DIR="$2"
            shift 2
            ;;
        --start-time)
            START_TIME="$2"
            shift 2
            ;;
        --end-time)
            END_TIME="$2"
            shift 2
            ;;
        --block-size)
            BLOCK_SIZE="$2"
            shift 2
            ;;
        --min-requests)
            MIN_REQUESTS="$2"
            shift 2
            ;;
        --include-subagents)
            INCLUDE_SUBAGENTS="true"
            shift
            ;;
        --no-subagents)
            INCLUDE_SUBAGENTS="false"
            shift
            ;;
        --local-hash-ids)
            USE_LOCAL_HASH_IDS="true"
            shift
            ;;
        --global-hash-ids)
            USE_LOCAL_HASH_IDS="false"
            shift
            ;;
        --no-validate)
            DO_VALIDATE="false"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "❌ 未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 使用默认值填充未指定的参数
DB="${DB:-$DEFAULT_DB}"
JSONL_ROOT="${JSONL_ROOT:-$DEFAULT_JSONL_ROOT}"
OUT_ROOT="${OUT_ROOT:-$DEFAULT_OUT_ROOT}"
LOG_DIR="${LOG_DIR:-$DEFAULT_LOG_DIR}"
START_TIME="${START_TIME:-$DEFAULT_START_TIME}"
END_TIME="${END_TIME:-$DEFAULT_END_TIME}"
BLOCK_SIZE="${BLOCK_SIZE:-$DEFAULT_BLOCK_SIZE}"
MIN_REQUESTS="${MIN_REQUESTS:-$DEFAULT_MIN_REQUESTS}"
INCLUDE_SUBAGENTS="${INCLUDE_SUBAGENTS:-$DEFAULT_INCLUDE_SUBAGENTS}"
USE_LOCAL_HASH_IDS="${USE_LOCAL_HASH_IDS:-$DEFAULT_USE_LOCAL_HASH_IDS}"
DO_VALIDATE="${DO_VALIDATE:-$DEFAULT_DO_VALIDATE}"

# 检查数据库文件是否存在
if [ ! -f "$DB" ]; then
    echo "❌ 错误: 数据库文件不存在: $DB"
    exit 1
fi

# 检查 JSONL 根目录是否存在
if [ ! -d "$JSONL_ROOT" ]; then
    echo "❌ 错误: JSONL 根目录不存在: $JSONL_ROOT"
    exit 1
fi

# 创建输出和日志目录
mkdir -p "$OUT_ROOT"
mkdir -p "$LOG_DIR"

# 设置 tiktoken 缓存目录
export TIKTOKEN_CACHE_DIR="/tmp/tiktoken-cache"

# 显示配置
echo "========================================================================"
echo "agentic-coding-analysis 一键生成 trace"
echo "========================================================================"
echo "配置参数:"
echo "  DB              : $DB"
echo "  JSONL_ROOT      : $JSONL_ROOT"
echo "  OUT_ROOT        : $OUT_ROOT"
echo "  LOG_DIR         : $LOG_DIR"
echo "  START_TIME      : ${START_TIME:-<不限>}"
echo "  END_TIME        : ${END_TIME:-<不限>}"
echo "  BLOCK_SIZE      : $BLOCK_SIZE"
echo "  MIN_REQUESTS    : $MIN_REQUESTS"
echo "  INCLUDE_SUBAGENTS: $INCLUDE_SUBAGENTS"
echo "  USE_LOCAL_HASH_IDS: $USE_LOCAL_HASH_IDS"
echo "  DO_VALIDATE     : $DO_VALIDATE"
echo "========================================================================"
echo ""

# 生成时间戳
RUN_TAG=$(date +"%Y%m%d_%H%M%S")
OUT_DIR="$OUT_ROOT/traces-$RUN_TAG"
LOG_FILE="$LOG_DIR/run_$RUN_TAG.log"

mkdir -p "$OUT_DIR"

echo "本次运行："
echo "  输出目录: $OUT_DIR"
echo "  日志文件: $LOG_FILE"
echo ""

# 创建临时 Python 配置脚本
TEMP_SCRIPT=$(mktemp)
cat > "$TEMP_SCRIPT" << 'PYTHON_SCRIPT_END'
#!/usr/bin/env python3
import os, sys, re, subprocess, glob, json
from pathlib import Path
from datetime import datetime

# 从环境变量读取配置
AGENTIC_DIR = os.environ.get('AGENTIC_DIR')
DB = os.environ.get('DB')
JSONL_ROOT = os.environ.get('JSONL_ROOT')
OUT_DIR = os.environ.get('OUT_DIR')
LOG_FILE = os.environ.get('LOG_FILE')
BLOCK_SIZE = int(os.environ.get('BLOCK_SIZE', '64'))
MIN_REQUESTS = int(os.environ.get('MIN_REQUESTS', '1'))
INCLUDE_SUBAGENTS = os.environ.get('INCLUDE_SUBAGENTS', 'true').lower() == 'true'
USE_LOCAL_HASH_IDS = os.environ.get('USE_LOCAL_HASH_IDS', 'true').lower() == 'true'
DO_VALIDATE = os.environ.get('DO_VALIDATE', 'true').lower() == 'true'
DB_START_TIME = os.environ.get('DB_START_TIME', '')
DB_END_TIME = os.environ.get('DB_END_TIME', '')
TIKTOKEN_CACHE_DIR = os.environ.get('TIKTOKEN_CACHE_DIR', '/tmp/tiktoken-cache')

os.environ["TIKTOKEN_CACHE_DIR"] = TIKTOKEN_CACHE_DIR

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

# 自动收集 JSONL 目录
def discover_jsonl_dirs(root):
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
        dirs.append(full)
    return dirs

def main():
    JSONL_DIRS = discover_jsonl_dirs(JSONL_ROOT)

    if not JSONL_DIRS:
        print(f"❌ 在 {JSONL_ROOT} 下没发现任何含 *.jsonl 的一级目录")
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 66)
    print("agentic-coding-analysis 一键生成 trace")
    print(f"  DB     : {DB}")
    print(f"  ROOT   : {JSONL_ROOT}")
    print(f"  发现 {len(JSONL_DIRS)} 个 jsonl 目录:")
    for jd in JSONL_DIRS:
        print(f"            - {jd}")
    print(f"  OUT    : {OUT_DIR}")
    print("=" * 66)

    # Step1: 提取 message id
    print("\n=== Step1: build_message_index ===")
    ok1, out1 = sh(f'python3 build_message_index.py "{DB}"')
    m1 = re.search(r"Extracted ([\d,]+) unique message IDs", out1)
    n_ids = int(m1.group(1).replace(",", "")) if m1 else 0
    if not n_ids:
        print("❌ 提取 0 个 message id")
        sys.exit(1)
    print(f"\n    ✅ 提取 {n_ids} 个 message id")

    # Step2: 会话关联
    print("\n>>> [Step2] build_conversation_index ===")
    mapped_total = 0
    for jd in JSONL_DIRS:
        ok2, out2 = sh(f'python3 build_conversation_index.py "{DB}" --projects-path "{jd}"')
        m2 = re.search(r"Mapped to requests\.db:\s*(\d+)", out2)
        mapped = int(m2.group(1)) if m2 else 0
        mapped_total += mapped
        print(f"\n    [{jd}] 关联到 requests.db: {mapped} 条")

    # Step3: 生成 trace
    print("\n>>> [Step3] build_minimal_traces ===")
    extra = f"--block-size {BLOCK_SIZE} --min-requests {MIN_REQUESTS}"
    if INCLUDE_SUBAGENTS:
        extra += " --include-subagents"
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
        print("    ❌ 未生成任何 trace")
        sys.exit(1)
    for f in new:
        try:
            d = json.load(open(f))
            print(f"      - {os.path.basename(f)}  requests={len(d.get('requests',[]))}  block={d.get('block_size')}  scope={d.get('hash_id_scope')}")
        except Exception:
            print(f"      - {os.path.basename(f)}  ({os.path.getsize(f)}B)")

    # Step4: validate
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
PYTHON_SCRIPT_END

chmod +x "$TEMP_SCRIPT"

# 设置环境变量并执行Python脚本
export AGENTIC_DIR="$PROJECT_DIR"
export DB
export JSONL_ROOT
export OUT_DIR
export LOG_FILE
export BLOCK_SIZE
export MIN_REQUESTS
export INCLUDE_SUBAGENTS
export USE_LOCAL_HASH_IDS
export DO_VALIDATE
export DB_START_TIME="$START_TIME"
export DB_END_TIME="$END_TIME"
export TIKTOKEN_CACHE_DIR

cd "$PROJECT_DIR"

# 执行并保存日志
if [ -n "$LOG_FILE" ]; then
    python3 "$TEMP_SCRIPT" 2>&1 | tee "$LOG_FILE"
else
    python3 "$TEMP_SCRIPT"
fi

# 清理临时文件
rm -f "$TEMP_SCRIPT"

echo ""
echo "========================================================================"
echo "✅ 全部完成！"
echo "========================================================================"
echo "  输出目录: $OUT_DIR"
if [ -n "$LOG_FILE" ]; then
    echo "  日志文件: $LOG_FILE"
fi
