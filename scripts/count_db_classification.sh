#!/bin/bash
# 验证请求分类的脚本
#
# 用法:
#   ./count_classification.sh                    # 使用默认时间范围
#   ./scripts/count_classification.sh --start "2026-09-07T17:00:00+08:00" --end "2026-09-07T18:00:00+08:00"
#
# 参数:
#   --db PATH          数据库路径 (默认: tmp/exported_requests.db)
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
# 默认数据库路径
DEFAULT_DB="$PROJECT_DIR/tmp/exported_requests.db"
# ============================================================

# Python脚本路径
PYTHON_SCRIPT="$PROJECT_DIR/count_classification.py"

# 检查Python脚本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ 错误: 找不到 Python 脚本: $PYTHON_SCRIPT"
    exit 1
fi

# 显示帮助
if [[ "$*" =~ "--help" ]]; then
    echo "用法: $0 [选项]"
    echo ""
    echo "验证请求分类，显示详细的分类树和统计信息"
    echo ""
    echo "选项:"
    echo "  --db PATH          数据库路径 (默认: tmp/exported_requests.db)"
    echo "  --start TIME       开始时间 (格式: \"YYYY-MM-DDTHH:MM:SS+08:00\")"
    echo "  --end TIME         结束时间 (格式: \"YYYY-MM-DDTHH:MM:SS+08:00\")"
    echo "  --help             显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0"
    echo "  $0 --start \"2026-09-07T17:00:00+08:00\" --end \"2026-09-07T18:00:00+08:00\""
    echo "  $0 --db custom.db --start \"2026-09-07T17:00:00+08:00\""
    exit 0
fi

# 如果没有指定--db参数，添加默认数据库
if [[ ! "$*" =~ "--db" ]]; then
    set -- --db "$DEFAULT_DB" "$@"
fi

# 执行Python脚本
cd "$PROJECT_DIR"
python3 "$PYTHON_SCRIPT" "$@"
