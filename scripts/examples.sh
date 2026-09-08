#!/bin/bash
# 快速使用示例 - 演示如何使用这些脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "agentic-coding-analysis 脚本使用示例"
echo "========================================================================"
echo ""

# 示例1: 查看数据库统计
echo "示例 1: 查看数据库中的请求统计"
echo "----------------------------------------"
echo "命令: ./count_requests.sh"
echo ""
read -p "按 Enter 继续运行... " -r
./count_requests.sh
echo ""

# 示例2: 查看指定时间段
echo "示例 2: 查看指定时间段的请求"
echo "----------------------------------------"
echo "命令: ./count_requests.sh --start \"2026-08-28T11:00:00+08:00\" --end \"2026-08-28T12:00:00+08:00\""
echo ""
read -p "按 Enter 继续运行... " -r
./count_requests.sh --start "2026-08-28T11:00:00+08:00" --end "2026-08-28T12:00:00+08:00"
echo ""

# 示例3: 生成 trace（需要配置）
echo "示例 3: 生成 trace 文件"
echo "----------------------------------------"
echo "这个示例需要正确配置数据库和 JSONL 路径"
echo ""
echo "命令示例:"
echo "./run_trace_generations.sh \\"
echo "    --db /path/to/requests.db \\"
echo "    --jsonl-root /path/to/projects \\"
echo "    --start-time \"2026-08-28T11:00:00+08:00\" \\"
echo "    --end-time \"2026-08-28T13:00:00+08:00\""
echo ""
echo "(跳过实际执行，避免生成大量文件)"
echo ""

# 示例4: 重标记全局时间线
echo "示例 4: 重标记 traces 为全局时间线"
echo "----------------------------------------"
echo "命令: ./retime_traces_global.sh /path/to/traces-dir --dry-run"
echo ""
echo "(需要先生成 trace 文件，这里仅显示命令)"
echo ""

# 示例5: 提取 hash_ids
echo "示例 5: 提取 Hash ID 信息"
echo "----------------------------------------"
echo "命令: ./extract_hash_ids.sh /path/to/traces.jsonl /path/to/output"
echo ""
echo "(需要先生成 trace 文件，这里仅显示命令)"
echo ""

echo "========================================================================"
echo "✅ 示例演示完成"
echo "========================================================================"
echo ""
echo "更多信息请查看:"
echo "  - README.md - 完整使用说明"
echo "  - 各脚本的 --help 选项"
echo ""
