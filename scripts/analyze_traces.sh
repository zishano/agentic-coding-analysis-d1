#!/bin/bash
# 分析 trace 文件并生成可视化图表
#
# 用法:
#   ./scripts/analyze_traces.sh                                          # 使用默认配置
#   ./scripts/analyze_traces.sh --sampling 1.0                           # 指定采样间隔为1秒
#   ./scripts/analyze_traces.sh --sampling 0.5 --update-time-mapping     # 自动更新时间映射再分析
#
# 参数:
#   --traces-dir PATH      trace JSON 文件目录 (默认: 从配置读取)
#   --db PATH              数据库路径 (默认: 从配置读取)
#   --jsonl-root PATH      JSONL 文件根目录 (默认: 从配置读取)
#   --sampling INTERVAL    采样时间间隔(秒)，如 1.0, 0.5, 0.1 (默认: 事件采样)
#   --update-time-mapping  从数据库自动更新 TIME_MAPPING 配置
#   --help                 显示帮助

set -e

# 获取脚本所在目录的父目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================================
# *** 配置区域：根据你的实际路径修改 ***
# ============================================================
# 默认 trace 文件目录
DEFAULT_TRACES_DIR="/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/traces-d1/traces-20260918_134348-2026-09-15T00:00:00+08:00-2026-09-16T09:30:00+08:00"
# 默认数据库路径
DEFAULT_DB="/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/tmp/tmp_20260917/requests.db"
# 默认 JSONL 根目录
DEFAULT_JSONL_ROOT="/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/tmp/tmp_20260918/projects"
# ============================================================

# Python 分析脚本路径
ANALYZE_SCRIPT="$PROJECT_DIR/analyze_all_comprehensive.py"

# 显示帮助信息
show_help() {
    cat << EOF
分析 trace 文件并生成可视化图表

用法:
  $0 [选项]

选项:
  --traces-dir PATH      trace JSON 文件目录
                         (默认: $DEFAULT_TRACES_DIR)

  --db PATH              数据库路径
                         (默认: $DEFAULT_DB)

  --jsonl-root PATH      JSONL 文件根目录
                         (默认: $DEFAULT_JSONL_ROOT)

  --sampling INTERVAL    并发数量统计的采样时间间隔(秒)
                         例如: 1.0 (1秒), 0.5 (0.5秒), 0.1 (0.1秒)
                         不指定则使用事件采样模式

  --update-time-mapping  从数据库自动更新 TIME_MAPPING 配置

  --help                 显示此帮助信息

示例:
  # 使用默认配置运行
  $0

  # 使用1秒采样间隔
  $0 --sampling 1.0

  # 自动更新时间映射再分析(0.5秒采样)
  $0 --update-time-mapping --sampling 0.5

  # 指定自定义路径
  $0 --traces-dir /path/to/traces --db /path/to/db --sampling 0.1

输出:
  生成的图表文件将保存在 trace 文件目录中

EOF
}

# 解析命令行参数
TRACES_DIR="$DEFAULT_TRACES_DIR"
DB="$DEFAULT_DB"
JSONL_ROOT="$DEFAULT_JSONL_ROOT"
SAMPLING=""
UPDATE_MAPPING=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --traces-dir)
            TRACES_DIR="$2"
            shift 2
            ;;
        --db)
            DB="$2"
            shift 2
            ;;
        --jsonl-root)
            JSONL_ROOT="$2"
            shift 2
            ;;
        --sampling)
            SAMPLING="$2"
            shift 2
            ;;
        --update-time-mapping)
            UPDATE_MAPPING=true
            shift
            ;;
        --help)
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

# 检查分析脚本是否存在
if [ ! -f "$ANALYZE_SCRIPT" ]; then
    echo "❌ 错误: 找不到分析脚本: $ANALYZE_SCRIPT"
    exit 1
fi

# 检查 trace 目录是否存在
if [ ! -d "$TRACES_DIR" ]; then
    echo "❌ 错误: trace 目录不存在: $TRACES_DIR"
    exit 1
fi

echo "========================================================================"
echo "Trace 分析工具"
echo "========================================================================"
echo "Traces 目录  : $TRACES_DIR"
echo "数据库       : $DB"
echo "JSONL 根目录 : $JSONL_ROOT"
if [ -n "$SAMPLING" ]; then
    echo "采样间隔     : ${SAMPLING}s"
else
    echo "采样模式     : 事件采样(默认)"
fi
echo "========================================================================"
echo ""

# 构建 Python 命令
cd "$TRACES_DIR"
PYTHON_CMD="python3 $ANALYZE_SCRIPT --traces-dir $TRACES_DIR"

if [ -n "$SAMPLING" ]; then
    PYTHON_CMD="$PYTHON_CMD --sampling $SAMPLING"
fi

if [ "$UPDATE_MAPPING" = true ]; then
    PYTHON_CMD="$PYTHON_CMD --update-time-mapping --db $DB --jsonl-root $JSONL_ROOT"
fi

# 执行分析
echo "🚀 开始分析 trace 文件..."
echo "执行命令: $PYTHON_CMD"
echo ""

$PYTHON_CMD

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================================================"
    echo "✅ 分析完成！"
    echo "========================================================================"
    echo "生成的图表文件位于: $TRACES_DIR"
    echo ""
    echo "生成的文件:"
    ls -lh "$TRACES_DIR"/*.png 2>/dev/null | tail -10
else
    echo ""
    echo "❌ 分析失败"
    exit 1
fi
