#!/bin/bash
# 从 traces.jsonl 提取所有 Hash ID 分配信息
#
# 用法:
#   ./extract_hash_ids.sh                                    # 使用默认路径
#   ./extract_hash_ids.sh /path/to/traces.jsonl              # 指定输入文件
#   ./extract_hash_ids.sh /path/to/traces.jsonl /path/to/output  # 指定输入和输出
#
# 说明:
#   - 提取每个请求的实际 hash_ids 范围
#   - 对于不连续的 hash_ids，在一行中横向展示多个范围
#   - 对于 subagent，展开其内部的每个 request
#   - 生成两个 CSV 文件：
#     * traces_all_data.csv - 所有请求的详细信息
#     * traces_statistics.csv - 统计摘要

set -e

# 获取脚本所在目录的父目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================================
# *** 配置区域：根据你的实际路径修改 ***
# ============================================================
# 默认路径
DEFAULT_INPUT="$PROJECT_DIR/traces-d1/traces-20260908_094608_global/merged.jsonl"
DEFAULT_OUTPUT="$PROJECT_DIR/hash_ids_merged"
# ============================================================

# Python脚本路径
PYTHON_SCRIPT="$PROJECT_DIR/extract_hash_ids_expanded.py"

# 检查Python脚本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ 错误: 找不到 Python 脚本: $PYTHON_SCRIPT"
    exit 1
fi

# 解析参数
INPUT_FILE="${1:-$DEFAULT_INPUT}"
OUTPUT_DIR="${2:-$DEFAULT_OUTPUT}"

# 检查输入文件
if [ ! -f "$INPUT_FILE" ]; then
    echo "❌ 错误: 输入文件不存在: $INPUT_FILE"
    echo ""
    echo "用法:"
    echo "  $0 [INPUT_JSONL] [OUTPUT_DIR]"
    echo ""
    echo "示例:"
    echo "  $0"
    echo "  $0 /path/to/traces.jsonl"
    echo "  $0 /path/to/traces.jsonl /path/to/output"
    exit 1
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 执行Python脚本
echo "📊 提取 Hash ID 信息..."
echo "   输入: $INPUT_FILE"
echo "   输出: $OUTPUT_DIR"
echo ""

cd "$PROJECT_DIR"
python3 "$PYTHON_SCRIPT" "$INPUT_FILE" "$OUTPUT_DIR"

echo ""
echo "✅ 完成！输出文件:"
echo "   - $OUTPUT_DIR/traces_all_data.csv"
echo "   - $OUTPUT_DIR/traces_statistics.csv"
