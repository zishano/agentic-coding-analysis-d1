#!/bin/bash
# 为每个 trace 生成三幅性能特征图（区分主代理和子代理）
#
# 用法:
#   ./scripts/visualize_trace_performance.sh <merged.jsonl> [选项]
#
# 示例:
#   ./scripts/visualize_trace_performance.sh traces/merged.jsonl
#   ./scripts/visualize_trace_performance.sh traces/merged.jsonl --verbose

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="$PROJECT_DIR/trace_performance_visualizer_v3.py"

# 检查 Python 脚本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "ERROR: 找不到 Python 脚本: $PYTHON_SCRIPT" >&2
    exit 1
fi

# 检查参数
if [ $# -lt 1 ]; then
    echo "用法: $0 <merged.jsonl> [--verbose]" >&2
    echo "" >&2
    echo "为每个 trace 生成三幅性能特征图:" >&2
    echo "  1. cached context at turn start" >&2
    echo "  2. uncached input" >&2
    echo "  3. decode output per turn" >&2
    echo "" >&2
    echo "图表保存在 merged.jsonl 同级目录" >&2
    exit 1
fi

# 执行 Python 脚本
python3 "$PYTHON_SCRIPT" "$@"
