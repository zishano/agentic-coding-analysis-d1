#!/bin/bash
# 将多个会话的 traces 重标记为全局时间线
#
# 用法:
#   ./retime_traces_global.sh TRACES_DIR [OPTIONS]
#
# 参数:
#   TRACES_DIR              traces 目录路径 (必需)
#
# 选项:
#   --db PATH               requests.db 路径
#   --jsonl-root PATH       JSONL 根目录路径
#   --start-time TIME       数据库时间过滤（开始）
#   --end-time TIME         数据库时间过滤（结束）
#   --dry-run               预览模式，不实际写入文件
#   --no-merge              不合并输出文件
#   --merge-only            只合并，不重标记
#   --help, -h              显示帮助信息

set -e

# 获取脚本所在目录的父目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================================
# *** 配置区域：根据你的实际路径修改 ***
# ============================================================
# 数据库和 JSONL 配置
DEFAULT_DB="$PROJECT_DIR/requests_20260828.db"
DEFAULT_JSONL_ROOT="$PROJECT_DIR/projects"
DEFAULT_START_TIME=""
DEFAULT_END_TIME=""
DEFAULT_DRY_RUN="False"

# 默认 traces 目录（可选，留空表示必须在命令行指定）
# 示例: DEFAULT_TRACES_DIR="$PROJECT_DIR/traces-d1/traces-20260908_094608"
DEFAULT_TRACES_DIR="/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/traces-d1/traces-20260908_094608"

# 默认是否合并输出
DEFAULT_DO_MERGE=true
# ============================================================

# Python脚本路径
PYTHON_SCRIPT="$PROJECT_DIR/retime_traces_global.py"

# 显示帮助
show_help() {
    cat << EOF
将多个会话的 traces 重标记为全局时间线

用法:
  $0 TRACES_DIR [OPTIONS]

参数:
  TRACES_DIR              traces 目录路径 (如果配置了默认值则可选)

选项:
  --db PATH               requests.db 路径 (默认: $DEFAULT_DB)
  --jsonl-root PATH       JSONL 根目录路径 (默认: $DEFAULT_JSONL_ROOT)
  --start-time TIME       数据库时间过滤（开始，格式: YYYY-MM-DDTHH:MM:SS+08:00）
  --end-time TIME         数据库时间过滤（结束，格式: YYYY-MM-DDTHH:MM:SS+08:00）
  --dry-run               预览模式，不实际写入文件
  --no-merge              不合并输出文件
  --merge-only            只合并，不重标记
  --help, -h              显示此帮助信息

默认配置:
  DEFAULT_TRACES_DIR      : ${DEFAULT_TRACES_DIR:-<未设置，必须在命令行指定>}
  DEFAULT_DO_MERGE        : ${DEFAULT_DO_MERGE}

说明:
  - 将每个 trace 的时间戳重标记为相对于全局起点的时间
  - 全局起点 = 所有会话中最早的请求时间
  - 输出到 <源文件夹>_global/ 新文件夹
  - 默认会合并所有 traces 到 merged.jsonl

示例:
  # 基本使用（使用默认配置）
  $0 /path/to/traces-dir

  # 指定数据库和 JSONL 路径
  $0 /path/to/traces-dir \\
      --db /path/to/requests.db \\
      --jsonl-root /path/to/projects

  # 带时间过滤
  $0 /path/to/traces-dir \\
      --start-time "2026-08-28T11:00:00+08:00" \\
      --end-time "2026-08-28T13:00:00+08:00"

  # 预览模式
  $0 /path/to/traces-dir --dry-run
EOF
}

# 检查Python脚本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ 错误: 找不到 Python 脚本: $PYTHON_SCRIPT"
    exit 1
fi

# 检查是否需要帮助
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    show_help
    exit 0
fi

# 检查是否提供了traces目录
if [ $# -lt 1 ] || [[ "$1" == --* ]]; then
    # 如果没有提供，尝试使用默认值
    if [ -n "$DEFAULT_TRACES_DIR" ]; then
        TRACES_DIR="$DEFAULT_TRACES_DIR"
        echo "ℹ️  使用默认 traces 目录: $TRACES_DIR"
    else
        echo "❌ 错误: 缺少 TRACES_DIR 参数"
        echo ""
        show_help
        exit 1
    fi
else
    TRACES_DIR="$1"
    shift
fi

# 初始化变量
DB=""
JSONL_ROOT=""
START_TIME=""
END_TIME=""
DRY_RUN=""
NO_MERGE=false
MERGE_ONLY=false

# 解析选项
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
        --start-time)
            START_TIME="$2"
            shift 2
            ;;
        --end-time)
            END_TIME="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN="True"
            shift
            ;;
        --no-merge)
            NO_MERGE=true
            shift
            ;;
        --merge-only)
            MERGE_ONLY=true
            shift
            ;;
        *)
            echo "⚠️  未知参数: $1"
            shift
            ;;
    esac
done

# 使用默认值填充未指定的参数
DB="${DB:-$DEFAULT_DB}"
JSONL_ROOT="${JSONL_ROOT:-$DEFAULT_JSONL_ROOT}"
START_TIME="${START_TIME:-$DEFAULT_START_TIME}"
END_TIME="${END_TIME:-$DEFAULT_END_TIME}"
DRY_RUN="${DRY_RUN:-$DEFAULT_DRY_RUN}"

# 检查traces目录是否存在
if [ ! -d "$TRACES_DIR" ]; then
    echo "❌ 错误: traces 目录不存在: $TRACES_DIR"
    exit 1
fi

# 检查数据库文件
if [ ! -f "$DB" ]; then
    echo "❌ 错误: 数据库文件不存在: $DB"
    exit 1
fi

# 检查 JSONL 根目录
if [ ! -d "$JSONL_ROOT" ]; then
    echo "❌ 错误: JSONL 根目录不存在: $JSONL_ROOT"
    exit 1
fi

# 显示配置
echo "========================================================================"
echo "重标记 traces 为全局时间线"
echo "========================================================================"
echo "配置参数:"
echo "  TRACES_DIR  : $TRACES_DIR"
echo "  DB          : $DB"
echo "  JSONL_ROOT  : $JSONL_ROOT"
echo "  START_TIME  : ${START_TIME:-<不限>}"
echo "  END_TIME    : ${END_TIME:-<不限>}"
echo "  DRY_RUN     : $DRY_RUN"
echo "  NO_MERGE    : $NO_MERGE"
echo "  MERGE_ONLY  : $MERGE_ONLY"
echo "========================================================================"
echo ""

# 创建临时配置脚本来修改 Python 脚本的配置
TEMP_WRAPPER=$(mktemp)
cat > "$TEMP_WRAPPER" << EOF
#!/usr/bin/env python3
import sys

# 覆盖配置
DB = "$DB"
JSONL_ROOT = "$JSONL_ROOT"
DB_START_TIME = "$START_TIME"
DB_END_TIME = "$END_TIME"
DRY_RUN = $DRY_RUN

# 加载并执行原始脚本
with open("$PYTHON_SCRIPT", 'r') as f:
    code = f.read()
    # 执行代码
    exec(code)
EOF

chmod +x "$TEMP_WRAPPER"

# 构建 Python 命令参数
PYTHON_ARGS="$TRACES_DIR"
if [ "$MERGE_ONLY" = false ] && [ "$NO_MERGE" = false ]; then
    PYTHON_ARGS="$PYTHON_ARGS --merge"
elif [ "$MERGE_ONLY" = true ]; then
    PYTHON_ARGS="$PYTHON_ARGS --merge-only"
fi

# 执行包装的 Python 脚本
cd "$PROJECT_DIR"
python3 "$TEMP_WRAPPER" $PYTHON_ARGS

# 清理临时文件
rm -f "$TEMP_WRAPPER"

echo ""
echo "========================================================================"
echo "✅ 完成！"
echo "========================================================================"
if [ "$DRY_RUN" = "False" ]; then
    OUTPUT_DIR="${TRACES_DIR}_global"
    echo "  输出目录: $OUTPUT_DIR"
    if [ "$NO_MERGE" = false ] && [ "$MERGE_ONLY" = false ]; then
        echo "  合并文件: $OUTPUT_DIR/merged.jsonl"
    fi
fi
