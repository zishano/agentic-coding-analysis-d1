#!/bin/bash
# 统计 JSONL 文件数据的脚本
#
# 用法:
#   ./count_jsonl_classification.sh                    # 使用默认时间范围（所有数据）
#   ./scripts/count_jsonl_classification.sh --start "2026-09-07T17:00:00+08:00" --end "2026-09-07T18:00:00+08:00"
#
# 参数:
#   --jsonl-root PATH  JSONL 根目录 (默认: tmp/projects)
#   --start TIME       开始时间 (格式: "YYYY-MM-DDTHH:MM:SS+08:00")
#   --end TIME         结束时间 (格式: "YYYY-MM-DDTHH:MM:SS+08:00")
#   --help             显示帮助

set -e

# 获取脚本所在目录的父目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================================
# *** 配置区域：根据你的实际路径修改 ***
# ============================================================
# 默认 JSONL 根目录
DEFAULT_JSONL_ROOT="/home/ai_lab/.claude/projects/-mnt-nvme1n1-data-lmk-PROJECT-claude-code-proxy-p1"
# ============================================================

# Python脚本路径
PYTHON_SCRIPT="$PROJECT_DIR/count_jsonl.py"

# 检查Python脚本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ 错误: 找不到 Python 脚本: $PYTHON_SCRIPT"
    exit 1
fi

# 显示帮助
if [[ "$*" =~ "--help" ]]; then
    echo "用法: $0 [选项]"
    echo ""
    echo "统计 JSONL 文件数据，显示详细的分类树和统计信息"
    echo ""
    echo "选项:"
    echo "  --jsonl-root PATH  JSONL 根目录 (默认: tmp/projects)"
    echo "  --start TIME       开始时间 (格式: \"YYYY-MM-DDTHH:MM:SS+08:00\")"
    echo "  --end TIME         结束时间 (格式: \"YYYY-MM-DDTHH:MM:SS+08:00\")"
    echo "  --help             显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0"
    echo "  $0 --start \"2026-09-07T17:00:00+08:00\" --end \"2026-09-07T18:00:00+08:00\""
    echo "  $0 --jsonl-root /path/to/jsonl"
    exit 0
fi

# 检查是否指定了 --jsonl-root，如果没有则使用默认值
if [[ "$*" =~ "--jsonl-root" ]]; then
    # 用户指定了 --jsonl-root，直接传递所有参数
    exec python3 "$PYTHON_SCRIPT" "$@"
else
    # 用户没有指定，添加默认的 --jsonl-root
    exec python3 "$PYTHON_SCRIPT" --jsonl-root "$DEFAULT_JSONL_ROOT" "$@"
fi
