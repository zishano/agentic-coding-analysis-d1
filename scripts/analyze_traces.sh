#!/bin/bash
# 分析 Claude Code traces 数据并生成分布图
#
# 用法:
#   ./scripts/analyze_traces.sh
#
# 说明:
#   生成7个指标的分布图:
#   1. Input tokens per turn (主会话)
#   2. Output tokens per turn (主会话)
#   3. Uncached input tokens per turn (主会话 + 子代理)
#   4. Turns per conversation
#   5. Subagent request ISL (子代理输入序列长度)
#   6. Subagent request OSL (子代理输出序列长度)
#   7. Cached fraction per turn (主会话 + 子代理)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================================
# *** 配置区域：根据你的实际路径修改 ***
# ============================================================
INPUT_JSONL="/mnt/nvme1n1/data/lmk/Github/tair-kvcache/kv_cache_manager/optimizer/tools/kimi_k3_test/trace_0918/merged_20260918.jsonl"
OUTPUT_DIR="/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/plots/plots_0924_test"
PYTHON_SCRIPT="/mnt/nvme1n1/data/lmk/PROJECT/agentic-coding-analysis-d1/analyze_traces.py"
# ============================================================

# 检查 Python 脚本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "ERROR: 找不到 Python 脚本: $PYTHON_SCRIPT" >&2
    exit 1
fi

# 检查输入文件是否存在
if [ ! -f "$INPUT_JSONL" ]; then
    echo "ERROR: 找不到输入文件: $INPUT_JSONL" >&2
    exit 1
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

echo "========================================================================"
echo "分析 Claude Code traces 数据"
echo "========================================================================"
echo "输入文件: $INPUT_JSONL"
echo "输出目录: $OUTPUT_DIR"
echo "========================================================================"
echo ""

# 执行 Python 脚本
python3 "$PYTHON_SCRIPT" \
    --input "$INPUT_JSONL" \
    --output-dir "$OUTPUT_DIR"

echo ""
echo "========================================================================"
echo "✅ 完成！"
echo "========================================================================"
echo "图表已保存到: $OUTPUT_DIR"
echo ""
