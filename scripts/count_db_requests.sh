#!/bin/bash
# 统计 requests.db 中指定时间段的请求数量
#
# 用法:
#   ./count_requests.sh                                      # 默认显示按小时统计
#   ./count_requests.sh --start "2026-08-28T11:00:00+08:00"  # 指定开始时间
#   ./count_requests.sh --hourly --detail                    # 按小时统计+详细信息
#   ./scripts/count_db_requests.sh --start "2026-09-07 17:00:00" --end "2026-09-07 18:00:00"

# 参数:
#   --db PATH          数据库路径 (默认: requests_20260828.db)
#   --start TIME       开始时间 (格式: "YYYY-MM-DDTHH:MM:SS+08:00")
#   --end TIME         结束时间 (格式: "YYYY-MM-DDTHH:MM:SS+08:00")
#   --hourly           按小时统计
#   --by-session       按会话统计
#   --detail           显示详细信息
#   --help             显示帮助

set -e

# 获取脚本所在目录的父目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================================
# *** 配置区域：根据你的实际路径修改 ***
# ============================================================
# 默认数据库路径
DEFAULT_DB="/mnt/nvme1n1/data/lmk/PROJECT/claude-code-proxy-p1/requests.db"
# ============================================================

# Python脚本路径
PYTHON_SCRIPT="$PROJECT_DIR/count_db_requests.py"

# 检查Python脚本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ 错误: 找不到 Python 脚本: $PYTHON_SCRIPT"
    exit 1
fi

# 如果没有指定--db参数，添加默认数据库
if [[ ! "$*" =~ "--db" ]]; then
    set -- --db "$DEFAULT_DB" "$@"
fi

# 执行Python脚本
cd "$PROJECT_DIR"
python3 "$PYTHON_SCRIPT" "$@"
