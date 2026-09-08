#!/bin/bash
# 导出指定时间段的请求到新数据库
#
# 用法:
#   ./export_db.sh SOURCE_DB OUTPUT_DB [OPTIONS]
#
# 参数:
#   SOURCE_DB              源数据库文件路径
#   OUTPUT_DB              输出数据库文件路径
#
# 选项:
#   --start-time TIME      开始时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00)
#   --end-time TIME        结束时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00)
#   --last N               导出最近 N 条记录
#   --conversation-id ID   导出指定会话的所有请求
#   --only-with-response   只导出有响应的请求
#   --help, -h             显示帮助信息
#
# 示例:
#   # 导出指定时间范围
#   ./export_db.sh source.db output.db \
#       --start-time "2026-08-28T00:00:00+08:00" \
#       --end-time "2026-08-28T23:59:59+08:00"
#
#   # 只导出有响应的请求
#   ./export_db.sh source.db output.db \
#       --start-time "2026-08-28T00:00:00+08:00" \
#       --end-time "2026-08-28T23:59:59+08:00" \
#       --only-with-response
#
#   # 导出最近 1000 条记录
#   ./export_db.sh source.db output.db --last 1000

set -e

# 获取脚本所在目录的父目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================================
# *** 配置区域：根据你的实际路径修改 ***
# ============================================================
# 默认源数据库（可选）
DEFAULT_SOURCE_DB="$PROJECT_DIR/requests_20260828.db"

# 默认输出数据库（可选）
DEFAULT_OUTPUT_DB="$PROJECT_DIR/exported_requests.db"

# 默认时间范围（留空表示不使用默认值）
DEFAULT_START_TIME="2026-08-28T00:00:00+08:00"  # 例: "2026-08-28T00:00:00+08:00"
DEFAULT_END_TIME="2026-08-28T23:59:59+08:00"    # 例: "2026-08-28T23:59:59+08:00"
# ============================================================

# Python脚本路径
PYTHON_SCRIPT="$PROJECT_DIR/tools/analyze_db_quick.py"

# 显示帮助
show_help() {
    cat << EOF
导出指定时间段的请求到新数据库

用法:
  $0 SOURCE_DB OUTPUT_DB [OPTIONS]
  $0 [OPTIONS]  # 使用默认源和输出数据库

参数:
  SOURCE_DB              源数据库文件路径 (默认: $DEFAULT_SOURCE_DB)
  OUTPUT_DB              输出数据库文件路径 (默认: $DEFAULT_OUTPUT_DB)

选项:
  --start-time TIME      开始时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00)
  --end-time TIME        结束时间 (格式: YYYY-MM-DDTHH:MM:SS+08:00)
  --last N               导出最近 N 条记录
  --conversation-id ID   导出指定会话的所有请求
  --only-with-response   只导出有响应的请求
  --help, -h             显示此帮助信息

默认配置:
  SOURCE_DB    : $DEFAULT_SOURCE_DB
  OUTPUT_DB    : $DEFAULT_OUTPUT_DB
  START_TIME   : ${DEFAULT_START_TIME:-<未设置>}
  END_TIME     : ${DEFAULT_END_TIME:-<未设置>}

说明:
  - 时间格式必须使用 ISO 8601 格式带时区: YYYY-MM-DDTHH:MM:SS+08:00
  - 如果不指定 SOURCE_DB 和 OUTPUT_DB，会使用默认值
  - 必须指定以下参数之一：
    * --start-time + --end-time (时间范围)
    * --last N (最近 N 条)
    * --conversation-id (会话 ID)

示例:
  # 使用默认数据库，导出指定时间范围
  $0 --start-time "2026-08-28T00:00:00+08:00" \\
     --end-time "2026-08-28T23:59:59+08:00"

  # 指定数据库路径
  $0 source.db output.db \\
     --start-time "2026-08-28T00:00:00+08:00" \\
     --end-time "2026-08-28T23:59:59+08:00"

  # 只导出有响应的请求
  $0 source.db output.db \\
     --start-time "2026-08-28T00:00:00+08:00" \\
     --end-time "2026-08-28T23:59:59+08:00" \\
     --only-with-response

  # 导出最近 1000 条记录
  $0 source.db output.db --last 1000

  # 导出指定会话
  $0 source.db output.db --conversation-id abc123
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

# 解析位置参数和选项
SOURCE_DB=""
OUTPUT_DB=""
START_TIME=""
END_TIME=""
LAST=""
CONVERSATION_ID=""
ONLY_WITH_RESPONSE=""

# 如果第一个参数不是选项，则为 SOURCE_DB
if [ $# -gt 0 ] && [[ ! "$1" =~ ^-- ]]; then
    SOURCE_DB="$1"
    shift
fi

# 如果第二个参数不是选项，则为 OUTPUT_DB
if [ $# -gt 0 ] && [[ ! "$1" =~ ^-- ]]; then
    OUTPUT_DB="$1"
    shift
fi

# 解析选项
while [[ $# -gt 0 ]]; do
    case $1 in
        --start-time)
            START_TIME="$2"
            shift 2
            ;;
        --end-time)
            END_TIME="$2"
            shift 2
            ;;
        --last)
            LAST="$2"
            shift 2
            ;;
        --conversation-id)
            CONVERSATION_ID="$2"
            shift 2
            ;;
        --only-with-response)
            ONLY_WITH_RESPONSE="--only-with-response"
            shift
            ;;
        *)
            echo "⚠️  未知参数: $1"
            shift
            ;;
    esac
done

# 使用默认值填充
SOURCE_DB="${SOURCE_DB:-$DEFAULT_SOURCE_DB}"
OUTPUT_DB="${OUTPUT_DB:-$DEFAULT_OUTPUT_DB}"
START_TIME="${START_TIME:-$DEFAULT_START_TIME}"
END_TIME="${END_TIME:-$DEFAULT_END_TIME}"

# 检查源数据库
if [ ! -f "$SOURCE_DB" ]; then
    echo "❌ 错误: 源数据库不存在: $SOURCE_DB"
    exit 1
fi

# 显示配置
echo "========================================================================"
echo "📂 导出请求数据库"
echo "========================================================================"
echo "配置参数:"
echo "  SOURCE_DB   : $SOURCE_DB"
echo "  OUTPUT_DB   : $OUTPUT_DB"
echo "  START_TIME  : ${START_TIME:-<未指定>}"
echo "  END_TIME    : ${END_TIME:-<未指定>}"
echo "  LAST        : ${LAST:-<未指定>}"
echo "  CONVERSATION_ID: ${CONVERSATION_ID:-<未指定>}"
echo "  ONLY_WITH_RESPONSE: ${ONLY_WITH_RESPONSE:-false}"
echo "========================================================================"
echo ""

# 构建Python命令
PYTHON_ARGS="\"$SOURCE_DB\" \"$OUTPUT_DB\""

if [ -n "$START_TIME" ] && [ -n "$END_TIME" ]; then
    PYTHON_ARGS="$PYTHON_ARGS --start-time \"$START_TIME\" --end-time \"$END_TIME\""
elif [ -n "$LAST" ]; then
    PYTHON_ARGS="$PYTHON_ARGS --last $LAST"
elif [ -n "$CONVERSATION_ID" ]; then
    PYTHON_ARGS="$PYTHON_ARGS --conversation-id \"$CONVERSATION_ID\""
else
    echo "❌ 错误: 必须指定以下参数之一:"
    echo "   --start-time + --end-time (时间范围)"
    echo "   --last N (最近 N 条)"
    echo "   --conversation-id (会话 ID)"
    echo ""
    echo "使用 --help 查看帮助"
    exit 1
fi

if [ -n "$ONLY_WITH_RESPONSE" ]; then
    PYTHON_ARGS="$PYTHON_ARGS $ONLY_WITH_RESPONSE"
fi

# 执行Python脚本
cd "$PROJECT_DIR"
eval python3 "$PYTHON_SCRIPT" $PYTHON_ARGS

echo ""
echo "========================================================================"
echo "✅ 完成！"
echo "========================================================================"
